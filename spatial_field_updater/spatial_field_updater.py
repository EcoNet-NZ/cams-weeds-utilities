#!/usr/bin/env python3
"""
GeoPandas-based Spatial Field Updater - much faster for bulk spatial operations.
Uses GeoPandas and Shapely for efficient spatial joins.
"""

import os
import json
import argparse
from datetime import datetime
from tenacity import retry, stop_after_attempt, wait_fixed
from arcgis.gis import GIS
from arcgis.features import FeatureLayer
import geopandas as gpd
import pandas as pd
from shapely.geometry import Point

# Configuration - timestamp files are environment-specific
def get_last_run_file(environment):
    """Get environment-specific last run file path"""
    return f".last_run_{environment}"

@retry(stop=stop_after_attempt(3), wait=wait_fixed(5))
def connect_arcgis():
    username = os.getenv('ARCGIS_USERNAME')
    password = os.getenv('ARCGIS_PASSWORD')
    portal_url = os.getenv('ARCGIS_PORTAL_URL', 'https://www.arcgis.com')
    return GIS(portal_url, username, password)

def get_layers(gis, environment):
    env_config_path = 'config/environment_config.json'
    with open(env_config_path, 'r') as f:
        env_config = json.load(f)
    
    if environment not in env_config:
        available_envs = list(env_config.keys())
        raise ValueError(f"Environment '{environment}' not found. Available: {available_envs}")
    
    env_settings = env_config[environment]
    weed_layer_id = env_settings['weed_locations_layer_id']
    region_layer_id = env_settings['region_layer_id']
    district_layer_id = env_settings['district_layer_id']
    
    weed_layer = FeatureLayer.fromitem(gis.content.get(weed_layer_id))
    region_layer = FeatureLayer.fromitem(gis.content.get(region_layer_id))
    district_layer = FeatureLayer.fromitem(gis.content.get(district_layer_id))
    
    return weed_layer, region_layer, district_layer

def get_last_run_date(environment):
    """Get the last run date from environment-specific file, return None if not found"""
    last_run_file = get_last_run_file(environment)
    try:
        if os.path.exists(last_run_file):
            with open(last_run_file, 'r') as f:
                return datetime.fromisoformat(f.read().strip())
    except Exception:
        pass
    return None

def save_last_run_date(environment):
    """Save current datetime as last run date for the specified environment"""
    last_run_file = get_last_run_file(environment)
    try:
        with open(last_run_file, 'w') as f:
            f.write(datetime.now().isoformat())
    except Exception as e:
        print(f"Warning: Could not save last run date for {environment}: {e}")

def build_where_clause(environment, process_all):
    """Build WHERE clause for querying features"""
    if process_all:
        return "1=1"  # All features
    
    last_run = get_last_run_date(environment)
    if not last_run:
        print("No previous run found, processing all features")
        return "1=1"
    
    # Format for ArcGIS SQL
    last_run_str = last_run.strftime('%Y-%m-%d %H:%M:%S')
    return f"EditDate_1 > timestamp '{last_run_str}'"

def arcgis_to_geopandas(feature_set, geometry_col='SHAPE'):
    """Convert ArcGIS FeatureSet to GeoPandas DataFrame with geometry validation"""
    from shapely.geometry import Point, Polygon, LineString
    from shapely.validation import make_valid
    
    # Extract features and geometries
    features = []
    geometries = []
    
    for feature in feature_set.features:
        # Get attributes
        attrs = feature.attributes.copy()
        features.append(attrs)
        
        # Convert geometry
        geom_dict = feature.geometry
        if geom_dict:
            try:
                # Handle different ArcGIS geometry types
                if 'x' in geom_dict and 'y' in geom_dict:
                    # Point geometry
                    geom = Point(geom_dict['x'], geom_dict['y'])
                elif 'rings' in geom_dict:
                    # Polygon geometry
                    rings = geom_dict['rings']
                    if rings and len(rings) > 0:
                        # Create polygon from rings (exterior ring first, then holes)
                        exterior = rings[0]
                        holes = rings[1:] if len(rings) > 1 else None
                        geom = Polygon(exterior, holes)
                        
                        # Fix invalid geometries
                        if not geom.is_valid:
                            geom = make_valid(geom)
                    else:
                        geom = None
                elif 'paths' in geom_dict:
                    # Polyline geometry
                    paths = geom_dict['paths']
                    if paths and len(paths) > 0:
                        # Use first path for simplicity
                        geom = LineString(paths[0])
                    else:
                        geom = None
                else:
                    # Unknown geometry type
                    print(f"Warning: Unknown geometry type: {geom_dict}")
                    geom = None
                    
                geometries.append(geom)
            except Exception as e:
                print(f"Warning: Error converting geometry: {e}")
                geometries.append(None)
        else:
            geometries.append(None)
    
    # Create GeoDataFrame
    df = pd.DataFrame(features)
    gdf = gpd.GeoDataFrame(df, geometry=geometries)
    
    # Set CRS if available
    if feature_set.spatial_reference:
        wkid = feature_set.spatial_reference.get('wkid') or feature_set.spatial_reference.get('latestWkid')
        if wkid:
            try:
                gdf.crs = f"EPSG:{wkid}"
            except Exception:
                print(f"Warning: Could not set CRS for EPSG:{wkid}")
    
    return gdf

@retry(stop=stop_after_attempt(3), wait=wait_fixed(5))
def load_boundaries_as_geopandas(region_layer, district_layer):
    """Load boundary layers as GeoPandas DataFrames - SUPER FAST!"""
    print("Loading boundary layers with GeoPandas...")
    
    # Load regions
    print("  Loading regions...")
    regions_result = region_layer.query(out_fields=["REGC_code"], return_geometry=True)
    regions_gdf = arcgis_to_geopandas(regions_result)
    print(f"  Loaded {len(regions_gdf)} region boundaries")
    
    # Load districts  
    print("  Loading districts...")
    districts_result = district_layer.query(out_fields=["TALB_code"], return_geometry=True)
    districts_gdf = arcgis_to_geopandas(districts_result)
    print(f"  Loaded {len(districts_gdf)} district boundaries")
    
    return regions_gdf, districts_gdf

def find_nearest_boundary(point_gdf, boundary_gdf, code_field, max_distance_m=1000):
    """Find nearest boundary for unassigned points within max_distance"""
    import numpy as np
    
    if len(point_gdf) == 0 or len(boundary_gdf) == 0:
        return point_gdf
    
    print(f"    Finding nearest boundaries for {len(point_gdf)} unassigned points...")
    
    # Calculate distance from each point to each boundary
    point_gdf = point_gdf.copy()
    nearest_codes = []
    nearest_distances = []
    
    for idx, point_row in point_gdf.iterrows():
        point_geom = point_row.geometry
        
        # Calculate distances to all boundaries
        distances = boundary_gdf.geometry.distance(point_geom)
        min_distance_idx = distances.idxmin()
        min_distance = distances.loc[min_distance_idx]
        
        if min_distance <= max_distance_m:
            nearest_code = boundary_gdf.loc[min_distance_idx, code_field]
            nearest_codes.append(nearest_code)
            nearest_distances.append(min_distance)
        else:
            nearest_codes.append(None)
            nearest_distances.append(min_distance)
    
    # Add results to dataframe
    point_gdf['nearest_code'] = nearest_codes
    point_gdf['nearest_distance'] = nearest_distances
    
    assigned_count = sum(1 for code in nearest_codes if code is not None)
    if assigned_count > 0:
        print(f"    Assigned {assigned_count} points to nearest boundaries (within {max_distance_m}m)")
    
    return point_gdf

def spatial_join_bulk(weeds_gdf, regions_gdf, districts_gdf):
    """Perform bulk spatial joins using GeoPandas with nearest boundary fallback - VERY FAST!"""
    print("Performing bulk spatial joins with GeoPandas...")
    
    # Ensure CRS match for spatial operations (use NZTM as target)
    target_crs = "EPSG:2193"  # New Zealand Transverse Mercator
    print(f"  Converting all layers to {target_crs}...")
    
    if weeds_gdf.crs != target_crs:
        weeds_gdf = weeds_gdf.to_crs(target_crs)
    if regions_gdf.crs != target_crs:
        regions_gdf = regions_gdf.to_crs(target_crs) 
    if districts_gdf.crs != target_crs:
        districts_gdf = districts_gdf.to_crs(target_crs)
        
    # Ensure all geometries are valid after CRS transformation
    print("  Validating and fixing geometries...")
    from shapely.validation import make_valid
    regions_gdf = regions_gdf.copy()
    districts_gdf = districts_gdf.copy()
    regions_gdf.geometry = regions_gdf.geometry.apply(lambda geom: geom if geom.is_valid else make_valid(geom))
    districts_gdf.geometry = districts_gdf.geometry.apply(lambda geom: geom if geom.is_valid else make_valid(geom))
    
    # Spatial join with regions
    print("  Joining with regions...")
    weeds_with_regions = gpd.sjoin(weeds_gdf, regions_gdf[['REGC_code', 'geometry']], 
                                   how='left', predicate='intersects')
    
    # Find unassigned regions and try nearest boundary assignment
    unassigned_regions = weeds_with_regions[weeds_with_regions['REGC_code'].isna()]
    if len(unassigned_regions) > 0:
        print(f"  Found {len(unassigned_regions)} points without region assignment")
        nearest_regions = find_nearest_boundary(unassigned_regions, regions_gdf, 'REGC_code', max_distance_m=2000)
        
        # Update the main dataframe with nearest assignments
        for idx, row in nearest_regions.iterrows():
            if row['nearest_code'] is not None:
                weeds_with_regions.loc[idx, 'REGC_code'] = row['nearest_code']
    
    # Spatial join with districts  
    print("  Joining with districts...")
    # Drop index columns that might conflict from previous join
    if 'index_right' in weeds_with_regions.columns:
        weeds_with_regions = weeds_with_regions.drop(columns=['index_right'])
    
    weeds_with_all = gpd.sjoin(weeds_with_regions, districts_gdf[['TALB_code', 'geometry']], 
                               how='left', predicate='intersects')
    
    # Find unassigned districts and try nearest boundary assignment
    unassigned_districts = weeds_with_all[weeds_with_all['TALB_code'].isna()]
    if len(unassigned_districts) > 0:
        print(f"  Found {len(unassigned_districts)} points without district assignment")
        nearest_districts = find_nearest_boundary(unassigned_districts, districts_gdf, 'TALB_code', max_distance_m=2000)
        
        # Update the main dataframe with nearest assignments
        for idx, row in nearest_districts.iterrows():
            if row['nearest_code'] is not None:
                weeds_with_all.loc[idx, 'TALB_code'] = row['nearest_code']
    
    # Clean up the results
    weeds_with_all['RegionCode_new'] = weeds_with_all['REGC_code']
    weeds_with_all['DistrictCode_new'] = weeds_with_all['TALB_code']
    
    # Keep only necessary columns
    result_cols = ['OBJECTID', 'RegionCode', 'DistrictCode', 'RegionCode_new', 'DistrictCode_new']
    result_cols = [col for col in result_cols if col in weeds_with_all.columns]
    
    return weeds_with_all[result_cols]

@retry(stop=stop_after_attempt(3), wait=wait_fixed(5))
def update_batch(weed_layer, batch):
    result = weed_layer.edit_features(updates=batch)
    if result and 'updateResults' in result:
        return sum(1 for r in result['updateResults'] if r.get('success'))
    return 0

def update_spatial_codes_geopandas(environment, process_all=True):
    print(f"Starting GeoPandas spatial update on '{environment}' ({'all features' if process_all else 'changed features only'})...")
    
    gis = connect_arcgis()
    weed_layer, region_layer, district_layer = get_layers(gis, environment)
    
    # Build query to get features
    where_clause = build_where_clause(environment, process_all)
    print(f"Query: {where_clause}")
    
    # Get weed locations
    print("Loading weed locations...")
    weed_features = weed_layer.query(
        where=where_clause,
        out_fields=["OBJECTID", "GlobalID", "RegionCode", "DistrictCode", "EditDate_1"],
        return_geometry=True
    )
    
    print(f"Processing {len(weed_features.features)} weed locations...")
    
    if len(weed_features.features) == 0:
        print("No features to process")
        return
    
    # Convert to GeoPandas
    print("Converting to GeoPandas...")
    weeds_gdf = arcgis_to_geopandas(weed_features)
    
    # Load boundaries as GeoPandas
    regions_gdf, districts_gdf = load_boundaries_as_geopandas(region_layer, district_layer)
    
    # Perform bulk spatial join - THIS IS THE MAGIC!
    results_df = spatial_join_bulk(weeds_gdf, regions_gdf, districts_gdf)
    
    # Find features that need updates
    print("Identifying features needing updates...")
    updates = []
    
    for idx, row in results_df.iterrows():
        updated = False
        feature_dict = {
            'attributes': {
                'OBJECTID': row['OBJECTID']
            }
        }
        
        # Check if region code changed
        if (pd.notna(row.get('RegionCode_new')) and 
            row.get('RegionCode_new') != row.get('RegionCode')):
            feature_dict['attributes']['RegionCode'] = row['RegionCode_new']
            updated = True
            
        # Check if district code changed  
        if (pd.notna(row.get('DistrictCode_new')) and 
            row.get('DistrictCode_new') != row.get('DistrictCode')):
            feature_dict['attributes']['DistrictCode'] = row['DistrictCode_new']
            updated = True
        
        if updated:
            updates.append(feature_dict)
    
    print(f"Found {len(updates)} features needing updates")
    
    if len(updates) == 0:
        print("No updates needed")
        save_last_run_date(environment)
        return
    
    # Apply updates in batches
    batch_size = 100
    total_updated = 0
    
    for i in range(0, len(updates), batch_size):
        batch = updates[i:i + batch_size]
        
        try:
            successful = update_batch(weed_layer, batch)
            total_updated += successful
            print(f"Updated batch {i//batch_size + 1}: {successful}/{len(batch)} successful")
        except Exception as e:
            print(f"Batch update failed after retries: {e}")
    
    print(f"Completed: {total_updated} features updated successfully")
    
    # Save last run date only if processing was successful
    if total_updated > 0 or len(updates) == 0:
        save_last_run_date(environment)

def main():
    parser = argparse.ArgumentParser(description="Update spatial codes using GeoPandas (FAST!)")
    parser.add_argument(
        '--mode', 
        choices=['all', 'changed'], 
        default='changed',
        help='Process all features or only changed ones (default: changed)'
    )
    parser.add_argument(
        '--env',
        '--environment',
        dest='environment',
        required=True,
        help='Environment to use (e.g., development, staging, production)'
    )
    
    args = parser.parse_args()
    process_all = (args.mode == 'all')
    
    update_spatial_codes_geopandas(args.environment, process_all)

if __name__ == "__main__":
    main() 