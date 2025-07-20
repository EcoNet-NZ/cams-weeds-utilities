#!/usr/bin/env python3
"""
Simple spatial update script - populates RegionCode and DistrictCode for weed locations.
Minimal implementation for comparison with full enterprise solution.
"""

import os
import json
import argparse
from datetime import datetime
from tenacity import retry, stop_after_attempt, wait_fixed
from arcgis.gis import GIS
from arcgis.features import FeatureLayer

# Configuration
LAST_RUN_FILE = "scripts/.last_run"

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

def get_last_run_date():
    """Get the last run date from file, return None if not found"""
    try:
        if os.path.exists(LAST_RUN_FILE):
            with open(LAST_RUN_FILE, 'r') as f:
                return datetime.fromisoformat(f.read().strip())
    except Exception:
        pass
    return None

def save_last_run_date():
    """Save current datetime as last run date"""
    try:
        os.makedirs(os.path.dirname(LAST_RUN_FILE), exist_ok=True)
        with open(LAST_RUN_FILE, 'w') as f:
            f.write(datetime.now().isoformat())
    except Exception as e:
        print(f"Warning: Could not save last run date: {e}")

def build_where_clause(process_all):
    """Build WHERE clause for querying features"""
    if process_all:
        return "1=1"  # All features
    
    last_run = get_last_run_date()
    if not last_run:
        print("No previous run found, processing all features")
        return "1=1"
    
    # Format for ArcGIS SQL
    last_run_str = last_run.strftime('%Y-%m-%d %H:%M:%S')
    return f"EditDate_1 > timestamp '{last_run_str}'"

@retry(stop=stop_after_attempt(3), wait=wait_fixed(5))
def find_spatial_code(point_geometry, boundary_layer, code_field):
    result = boundary_layer.query(
        geometry=point_geometry,
        spatial_relationship='intersects',
        out_fields=[code_field],
        return_geometry=False
    )
    if result.features:
        return result.features[0].attributes.get(code_field)
    return None

@retry(stop=stop_after_attempt(3), wait=wait_fixed(5))
def update_batch(weed_layer, batch):
    result = weed_layer.edit_features(updates=batch)
    if result and 'updateResults' in result:
        return sum(1 for r in result['updateResults'] if r.get('success'))
    return 0

def update_spatial_codes(environment, process_all=True):
    print(f"Starting spatial update on '{environment}' ({'all features' if process_all else 'changed features only'})...")
    
    gis = connect_arcgis()
    weed_layer, region_layer, district_layer = get_layers(gis, environment)
    
    # Build query to get features
    where_clause = build_where_clause(process_all)
    print(f"Query: {where_clause}")
    
    # Get weed locations
    weed_features = weed_layer.query(
        where=where_clause,
        out_fields=["OBJECTID", "GlobalID", "RegionCode", "DistrictCode", "EditDate_1"],
        return_geometry=True
    )
    
    print(f"Processing {len(weed_features.features)} weed locations...")
    
    if len(weed_features.features) == 0:
        print("No features to process")
        return
    
    updates = []
    processed = 0
    
    for feature in weed_features.features:
        try:
            # Find intersecting region and district
            region_code = find_spatial_code(feature.geometry, region_layer, "REGC_code")
            district_code = find_spatial_code(feature.geometry, district_layer, "TALB_code")
            
            # Update codes if found
            updated = False
            if region_code and feature.attributes.get('RegionCode') != region_code:
                feature.attributes['RegionCode'] = region_code
                updated = True
            if district_code and feature.attributes.get('DistrictCode') != district_code:
                feature.attributes['DistrictCode'] = district_code
                updated = True
            
            if updated:
                updates.append(feature)
            
            processed += 1
            
            if processed % 100 == 0:
                print(f"Processed {processed} features...")
                
        except Exception as e:
            print(f"Error processing feature {feature.attributes.get('OBJECTID')}: {e}")
    
    print(f"Found {len(updates)} features needing updates")
    
    if len(updates) == 0:
        print("No updates needed")
        save_last_run_date()
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
        save_last_run_date()

def main():
    parser = argparse.ArgumentParser(description="Update spatial codes for weed locations")
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
    
    update_spatial_codes(args.environment, process_all)

if __name__ == "__main__":
    main() 