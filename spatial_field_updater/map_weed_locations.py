#!/usr/bin/env python3
"""
Create a map visualization of weed locations colored by region code with region boundaries
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

def get_layers(gis, environment, layer_type='regions'):
    """Get the layers for the specified environment"""
    env_config_path = 'config/environment_config.json'
    with open(env_config_path, 'r') as f:
        env_config = json.load(f)
    
    env_settings = env_config[environment]
    weed_layer_id = env_settings['weed_locations_layer_id']
    
    if layer_type == 'districts':
        boundary_layer_id = env_settings['district_layer_id']
    else:
        boundary_layer_id = env_settings['region_layer_id']
    
    weed_layer = FeatureLayer.fromitem(gis.content.get(weed_layer_id))
    boundary_layer = FeatureLayer.fromitem(gis.content.get(boundary_layer_id))
    
    return weed_layer, boundary_layer

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

def create_weed_location_map(environment='development', sample_size=None, layer_type='regions', zoom_region=None):
    """Create a map of weed locations colored by boundary code with boundaries"""
    layer_display = "region" if layer_type == 'regions' else "district"
    print(f"Creating {layer_display} map for '{environment}' environment...")
    
    # Connect and get layers
    gis = connect_arcgis()
    weed_layer, boundary_layer = get_layers(gis, environment, layer_type)
    
    # Determine which field to use for filtering
    if layer_type == 'regions':
        weed_code_field = "RegionCode"
        boundary_code_field = "REGC_code"
        boundary_name_field = "REGC_name"
    else:
        weed_code_field = "DistrictCode"
        boundary_code_field = "TALB_code"
        boundary_name_field = "TALB_name"
    
    # Load weed locations
    print("Loading weed locations...")
    if sample_size:
        weed_query = weed_layer.query(
            where="1=1",
            out_fields=["OBJECTID", "RegionCode", "DistrictCode"],
            return_geometry=True,
            result_record_count=sample_size
        )
        print(f"Loaded {len(weed_query.features)} sample weed locations")
    else:
        weed_query = weed_layer.query(
            where="1=1",
            out_fields=["OBJECTID", "RegionCode", "DistrictCode"],
            return_geometry=True
        )
        print(f"Loaded {len(weed_query.features)} weed locations")
    
    # Load boundaries
    boundary_display = "regions" if layer_type == 'regions' else "districts"
    print(f"Loading {boundary_display}...")
    boundary_query = boundary_layer.query(
        out_fields=[boundary_code_field, boundary_name_field],
        return_geometry=True
    )
    print(f"Loaded {len(boundary_query.features)} {boundary_display}")
    
    # Convert to GeoPandas
    print("Converting to GeoPandas...")
    weeds_gdf = arcgis_to_geopandas(weed_query)
    boundaries_gdf = arcgis_to_geopandas(boundary_query)
    
    # Standardize CRS to NZTM
    target_crs = "EPSG:2193"
    print(f"Converting to {target_crs}...")
    
    if weeds_gdf.crs != target_crs:
        weeds_gdf = weeds_gdf.to_crs(target_crs)
    if boundaries_gdf.crs != target_crs:
        boundaries_gdf = boundaries_gdf.to_crs(target_crs)
    
    # Fix any invalid geometries
    boundaries_gdf.geometry = boundaries_gdf.geometry.apply(lambda geom: geom if geom.is_valid else make_valid(geom))
    
    # Handle null codes
    weeds_gdf['Code_Display'] = weeds_gdf[weed_code_field].fillna('Unassigned')
    
    # Filter boundaries for zoom if specified
    if zoom_region:
        if layer_type == 'regions':
            zoom_boundaries = boundaries_gdf[boundaries_gdf[boundary_code_field] == zoom_region]
            if len(zoom_boundaries) == 0:
                print(f"Warning: Region {zoom_region} not found")
                zoom_boundaries = boundaries_gdf
        else:
            # For districts, filter by region code (zoom_region should be region code)
            # We need to load regions to get districts within that region
            print(f"Loading region boundaries for district filtering...")
            # Reload config to get region layer ID
            env_config_path = 'config/environment_config.json'
            with open(env_config_path, 'r') as f:
                env_config_reload = json.load(f)
            region_layer_id = env_config_reload[environment]['region_layer_id']  
            region_layer_temp = FeatureLayer.fromitem(gis.content.get(region_layer_id))
            region_query_temp = region_layer_temp.query(
                where=f"REGC_code = '{zoom_region}'",
                out_fields=["REGC_code"],
                return_geometry=True
            )
            
            if len(region_query_temp.features) > 0:
                regions_temp_gdf = arcgis_to_geopandas(region_query_temp)
                if regions_temp_gdf.crs != target_crs:
                    regions_temp_gdf = regions_temp_gdf.to_crs(target_crs)
                regions_temp_gdf.geometry = regions_temp_gdf.geometry.apply(lambda geom: geom if geom.is_valid else make_valid(geom))
                
                # Find districts that intersect with the region
                intersecting = gpd.sjoin(boundaries_gdf, regions_temp_gdf, how='inner', predicate='intersects')
                zoom_boundaries = boundaries_gdf[boundaries_gdf[boundary_code_field].isin(intersecting[boundary_code_field])]
            else:
                print(f"Warning: Region {zoom_region} not found for district filtering")
                zoom_boundaries = boundaries_gdf
    else:
        zoom_boundaries = boundaries_gdf
    
    # Create the map
    print("Creating map visualization...")
    
    # Set up the plot
    fig, ax = plt.subplots(1, 1, figsize=(16, 12))
    
    # Plot boundaries first (as background)
    boundaries_gdf.boundary.plot(ax=ax, color='black', linewidth=1.5, alpha=0.7)
    boundaries_gdf.plot(ax=ax, color='lightgray', alpha=0.3, edgecolor='black', linewidth=0.5)
    
    # Get unique codes for color mapping
    unique_codes = weeds_gdf['Code_Display'].unique()
    code_display = "region codes" if layer_type == 'regions' else "district codes"
    print(f"Found {code_display}: {unique_codes}")
    
    # Create a color map
    import matplotlib.cm as cm
    import numpy as np
    
    # Use a qualitative colormap
    colors = cm.Set3(np.linspace(0, 1, len(unique_codes)))
    color_map = dict(zip(unique_codes, colors))
    
    # Special color for unassigned
    if 'Unassigned' in color_map:
        color_map['Unassigned'] = 'red'
    
    # Create a mapping of codes to names for legend
    code_to_name = {}
    for idx, row in boundaries_gdf.iterrows():
        code = row.get(boundary_code_field, '')
        name = row.get(boundary_name_field, '')
        if code:
            code_to_name[code] = name
    
    # Plot weed locations colored by code
    for code in unique_codes:
        code_weeds = weeds_gdf[weeds_gdf['Code_Display'] == code]
        if len(code_weeds) > 0:
            # Create legend label with name
            if code == 'Unassigned':
                legend_label = f"Unassigned ({len(code_weeds)} locations)"
            else:
                code_name = code_to_name.get(code, '')
                prefix = "Region" if layer_type == 'regions' else "District"
                legend_label = f"{prefix} {code} - {code_name} ({len(code_weeds)} locations)"
            
            code_weeds.plot(ax=ax, 
                           color=color_map[code], 
                           markersize=6,
                           alpha=0.8,
                           label=legend_label)
    
    # Customize the map
    title_type = "Region" if layer_type == 'regions' else "District"
    zoom_text = f" - {zoom_region}" if zoom_region else ""
    ax.set_title(f'Weed Locations by {title_type} Code - {environment.title()} Environment{zoom_text}', 
                fontsize=16, fontweight='bold', pad=20)
    ax.set_xlabel('Easting (NZTM)', fontsize=12)
    ax.set_ylabel('Northing (NZTM)', fontsize=12)
    
    # Add legend
    ax.legend(bbox_to_anchor=(1.05, 1), loc='upper left', fontsize=10)
    
    # Add grid
    ax.grid(True, alpha=0.3)
    
    # Set aspect ratio to equal for proper geographic display
    ax.set_aspect('equal')
    
    # Set bounds based on zoom preference
    if zoom_region and len(zoom_boundaries) > 0:
        # Zoom to specific region/districts
        zoom_bounds = zoom_boundaries.total_bounds
        margin = 20000  # 20km margin for zoomed view
        ax.set_xlim(zoom_bounds[0] - margin, zoom_bounds[2] + margin)
        ax.set_ylim(zoom_bounds[1] - margin, zoom_bounds[3] + margin)
    else:
        # Default New Zealand view
        nz_bounds = boundaries_gdf.total_bounds  # [minx, miny, maxx, maxy]
        margin = 50000  # 50km margin in NZTM coordinates
        ax.set_xlim(nz_bounds[0] - margin, nz_bounds[2] + margin)
        ax.set_ylim(nz_bounds[1] - margin, nz_bounds[3] + margin)
    
    # Tight layout to prevent legend cutoff
    plt.tight_layout()
    
    # Save the map
    zoom_suffix = f"_{zoom_region}" if zoom_region else ""
    map_filename = f'weed_locations_{layer_type}_map_{environment}{zoom_suffix}.png'
    plt.savefig(map_filename, dpi=300, bbox_inches='tight')
    print(f"Map saved as: {map_filename}")
    
    # Show statistics
    print(f"\n=== {title_type} Distribution ===")
    code_counts = weeds_gdf['Code_Display'].value_counts()
    for code, count in code_counts.items():
        percentage = (count / len(weeds_gdf)) * 100
        print(f"{code}: {count} locations ({percentage:.1f}%)")
    
    # Show the map
    plt.show()
    
    return weeds_gdf, boundaries_gdf

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Create map of weed locations by region or district')
    parser.add_argument('--env', choices=['development', 'testing', 'production'], 
                       default='development', help='Environment (default: development)')
    parser.add_argument('--sample', type=int, help='Sample size (default: all records)')
    parser.add_argument('--layer', choices=['regions', 'districts'], 
                       default='regions', help='Boundary layer type (default: regions)')
    parser.add_argument('--zoom', type=str, help='Zoom to specific region code (e.g. 02 for Auckland)')
    
    args = parser.parse_args()
    
    try:
        weeds_gdf, boundaries_gdf = create_weed_location_map(
            args.env, args.sample, args.layer, args.zoom
        )
    except KeyboardInterrupt:
        print("\nMap creation cancelled")
    except Exception as e:
        print(f"Error creating map: {e}") 