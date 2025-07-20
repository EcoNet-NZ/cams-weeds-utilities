#!/usr/bin/env python3
"""
Create a map showing only unassigned weed locations (null RegionCode/DistrictCode)
"""

import os
import json
import matplotlib.pyplot as plt
import geopandas as gpd
import pandas as pd
from arcgis.gis import GIS
from arcgis.features import FeatureLayer
from shapely.geometry import Point, Polygon
from shapely.validation import make_valid

def connect_arcgis():
    """Connect to ArcGIS Online"""
    username = os.getenv('ARCGIS_USERNAME')
    password = os.getenv('ARCGIS_PASSWORD')
    portal_url = os.getenv('ARCGIS_PORTAL_URL', 'https://www.arcgis.com')
    return GIS(portal_url, username, password)

def get_layers(gis, environment):
    """Get the layers for the specified environment"""
    env_config_path = 'config/environment_config.json'
    with open(env_config_path, 'r') as f:
        env_config = json.load(f)
    
    env_settings = env_config[environment]
    weed_layer_id = env_settings['weed_locations_layer_id']
    region_layer_id = env_settings['region_layer_id']
    
    weed_layer = FeatureLayer.fromitem(gis.content.get(weed_layer_id))
    region_layer = FeatureLayer.fromitem(gis.content.get(region_layer_id))
    
    return weed_layer, region_layer

def arcgis_to_geopandas(feature_set):
    """Convert ArcGIS FeatureSet to GeoPandas DataFrame with geometry validation"""
    features = []
    geometries = []
    
    for feature in feature_set.features:
        attrs = feature.attributes.copy()
        features.append(attrs)
        
        geom_dict = feature.geometry
        if geom_dict:
            try:
                if 'x' in geom_dict and 'y' in geom_dict:
                    geom = Point(geom_dict['x'], geom_dict['y'])
                elif 'rings' in geom_dict:
                    rings = geom_dict['rings']
                    if rings and len(rings) > 0:
                        exterior = rings[0]
                        holes = rings[1:] if len(rings) > 1 else None
                        geom = Polygon(exterior, holes)
                        if not geom.is_valid:
                            geom = make_valid(geom)
                    else:
                        geom = None
                else:
                    geom = None
                geometries.append(geom)
            except Exception as e:
                print(f"Error converting geometry: {e}")
                geometries.append(None)
        else:
            geometries.append(None)
    
    df = pd.DataFrame(features)
    gdf = gpd.GeoDataFrame(df, geometry=geometries)
    
    # Set CRS if available
    if feature_set.spatial_reference:
        wkid = feature_set.spatial_reference.get('wkid') or feature_set.spatial_reference.get('latestWkid')
        if wkid:
            try:
                gdf.crs = f"EPSG:{wkid}"
            except:
                pass
    
    return gdf

def create_unassigned_map(environment='development'):
    """Create a map showing only unassigned weed locations"""
    print(f"Creating unassigned points map for '{environment}' environment...")
    
    # Connect and get layers
    gis = connect_arcgis()
    weed_layer, region_layer = get_layers(gis, environment)
    
    # Load unassigned weed locations only
    print("Loading unassigned weed locations...")
    
    # Query for records with null RegionCode OR null DistrictCode
    unassigned_query = weed_layer.query(
        where="RegionCode IS NULL OR DistrictCode IS NULL",
        out_fields=["OBJECTID", "RegionCode", "DistrictCode"],
        return_geometry=True
    )
    
    print(f"Found {len(unassigned_query.features)} unassigned weed locations")
    
    if len(unassigned_query.features) == 0:
        print("No unassigned locations found!")
        return None, None
    
    # Load region boundaries for context
    print("Loading region boundaries...")
    region_query = region_layer.query(
        out_fields=["REGC_code", "REGC_name"],
        return_geometry=True
    )
    print(f"Loaded {len(region_query.features)} regions")
    
    # Convert to GeoPandas
    print("Converting to GeoPandas...")
    weeds_gdf = arcgis_to_geopandas(unassigned_query)
    regions_gdf = arcgis_to_geopandas(region_query)
    
    # Standardize CRS to NZTM
    target_crs = "EPSG:2193"
    print(f"Converting to {target_crs}...")
    
    if weeds_gdf.crs != target_crs:
        weeds_gdf = weeds_gdf.to_crs(target_crs)
    if regions_gdf.crs != target_crs:
        regions_gdf = regions_gdf.to_crs(target_crs)
    
    # Fix any invalid geometries
    regions_gdf.geometry = regions_gdf.geometry.apply(lambda geom: geom if geom.is_valid else make_valid(geom))
    
    # Classify unassigned types
    weeds_gdf['unassigned_type'] = 'Unknown'
    weeds_gdf.loc[weeds_gdf['RegionCode'].isna() & weeds_gdf['DistrictCode'].isna(), 'unassigned_type'] = 'Both Null'
    weeds_gdf.loc[weeds_gdf['RegionCode'].isna() & weeds_gdf['DistrictCode'].notna(), 'unassigned_type'] = 'Region Only'
    weeds_gdf.loc[weeds_gdf['RegionCode'].notna() & weeds_gdf['DistrictCode'].isna(), 'unassigned_type'] = 'District Only'
    
    # Create the map
    print("Creating map visualization...")
    
    # Set up the plot
    fig, ax = plt.subplots(1, 1, figsize=(16, 12))
    
    # Plot region boundaries first (as background)
    regions_gdf.boundary.plot(ax=ax, color='black', linewidth=1.5, alpha=0.7)
    regions_gdf.plot(ax=ax, color='lightgray', alpha=0.2, edgecolor='black', linewidth=0.5)
    
    # Get unique unassigned types for color mapping
    unique_types = weeds_gdf['unassigned_type'].unique()
    print(f"Found unassigned types: {unique_types}")
    
    # Create a color map for different unassigned types
    color_map = {
        'Both Null': 'red',
        'Region Only': 'orange', 
        'District Only': 'yellow'
    }
    
    # Plot unassigned locations with larger dots
    for unassigned_type in unique_types:
        type_weeds = weeds_gdf[weeds_gdf['unassigned_type'] == unassigned_type]
        if len(type_weeds) > 0:
            type_weeds.plot(ax=ax, 
                           color=color_map.get(unassigned_type, 'purple'), 
                           markersize=15,  # Larger dots
                           alpha=0.8,
                           edgecolor='black',
                           linewidth=0.5,
                           label=f"{unassigned_type} ({len(type_weeds)} locations)")
    
    # Customize the map
    ax.set_title(f'Unassigned Weed Locations - {environment.title()} Environment', 
                fontsize=16, fontweight='bold', pad=20)
    ax.set_xlabel('Easting (NZTM)', fontsize=12)
    ax.set_ylabel('Northing (NZTM)', fontsize=12)
    
    # Add legend
    ax.legend(bbox_to_anchor=(1.05, 1), loc='upper left', fontsize=12)
    
    # Add grid
    ax.grid(True, alpha=0.3)
    
    # Set aspect ratio to equal for proper geographic display
    ax.set_aspect('equal')
    
    # Focus on New Zealand with some margin
    nz_bounds = regions_gdf.total_bounds  # [minx, miny, maxx, maxy]
    margin = 50000  # 50km margin in NZTM coordinates
    ax.set_xlim(nz_bounds[0] - margin, nz_bounds[2] + margin)
    ax.set_ylim(nz_bounds[1] - margin, nz_bounds[3] + margin)
    
    # Tight layout to prevent legend cutoff
    plt.tight_layout()
    
    # Save the map
    map_filename = f'unassigned_weed_locations_{environment}.png'
    plt.savefig(map_filename, dpi=300, bbox_inches='tight')
    print(f"Map saved as: {map_filename}")
    
    # Show statistics
    print("\n=== Unassigned Location Analysis ===")
    type_counts = weeds_gdf['unassigned_type'].value_counts()
    for unassigned_type, count in type_counts.items():
        percentage = (count / len(weeds_gdf)) * 100
        print(f"{unassigned_type}: {count} locations ({percentage:.1f}%)")
    
    # Geographic distribution
    print("\n=== Geographic Analysis ===")
    print(f"Latitude range: {weeds_gdf.geometry.y.min():.0f} to {weeds_gdf.geometry.y.max():.0f}")
    print(f"Longitude range: {weeds_gdf.geometry.x.min():.0f} to {weeds_gdf.geometry.x.max():.0f}")
    
    # Show the map
    plt.show()
    
    return weeds_gdf, regions_gdf

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Create map of unassigned weed locations')
    parser.add_argument('--env', choices=['development', 'testing', 'production'], 
                       default='development', help='Environment (default: development)')
    
    args = parser.parse_args()
    
    try:
        weeds_gdf, regions_gdf = create_unassigned_map(args.env)
        if weeds_gdf is not None:
            print(f"\nTotal unassigned locations mapped: {len(weeds_gdf)}")
    except KeyboardInterrupt:
        print("\nMap creation cancelled")
    except Exception as e:
        print(f"Error creating map: {e}") 