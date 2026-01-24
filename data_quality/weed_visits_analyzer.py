#!/usr/bin/env python3
"""
Weed Visits Analyzer

Analyzes WeedLocations feature layer and its relationship with Visits_Table.
Compares multiple fields between WeedLocations and the latest visit record
to identify data synchronization issues.

Field pairs checked:
- Urgency ↔ DifficultyChild
- ParentStatusWithDomain ↔ WeedVisitStatus
- DateVisitMadeFromLastVisit ↔ DateCheck
- DateForNextVisitFromLastVisit ↔ DateForReturnVisit
- LatestVisitStage ↔ VisitStage
- LatestArea ↔ Area
- DateOfLastCreateFromLastVisit ↔ CreationDate_1
- DateOfLastEditFromLastVisit ↔ EditDate_1
"""

import os
import json
import argparse
from datetime import datetime
from tenacity import retry, stop_after_attempt, wait_fixed
from arcgis.gis import GIS
from arcgis.features import FeatureLayer, Table
import pandas as pd


@retry(stop=stop_after_attempt(3), wait=wait_fixed(5))
def connect_arcgis():
  """Connect to ArcGIS Online"""
  username = os.getenv('ARCGIS_USERNAME')
  password = os.getenv('ARCGIS_PASSWORD')
  portal_url = os.getenv('ARCGIS_PORTAL_URL', 'https://www.arcgis.com')
  return GIS(portal_url, username, password)


def get_layers(gis, environment):
  """Get the WeedLocations layer and Visits_Table for the specified environment"""
  script_dir = os.path.dirname(os.path.abspath(__file__))
  env_config_path = os.path.join(script_dir, 'environment_config.json')
  
  with open(env_config_path, 'r') as f:
    env_config = json.load(f)
  
  if environment not in env_config:
    available_envs = list(env_config.keys())
    raise ValueError(f"Environment '{environment}' not found. Available: {available_envs}")
  
  env_settings = env_config[environment]
  weed_layer_id = env_settings['weed_locations_layer_id']
  
  # Get weed layer
  weed_item = gis.content.get(weed_layer_id)
  if not weed_item:
    raise ValueError(f"Could not find WeedLocations layer with ID: {weed_layer_id}")
  weed_layer = FeatureLayer.fromitem(weed_item)
  
  # Get visits table from the feature service
  # The Visits_Table is part of the same feature service as WeedLocations
  if not hasattr(weed_item, 'tables') or len(weed_item.tables) == 0:
    raise ValueError(f"No tables found in WeedLocations feature service: {weed_layer_id}")
  
  # Try to find the Visits_Table by name first
  visits_table = None
  for table in weed_item.tables:
    if 'visit' in table.properties.name.lower():
      visits_table = table
      print(f"Found Visits_Table: {table.properties.name}")
      break
  
  # If not found by name, use the first table (index 0)
  if not visits_table:
    visits_table = weed_item.tables[0]
    print(f"Using first table: {visits_table.properties.name}")
  
  return weed_layer, visits_table


def load_weed_locations(weed_layer):
  """Load all weed locations with relevant fields using manual pagination"""
  print("Loading WeedLocations features...")
  
  out_fields = [
    "OBJECTID", "GlobalID", 
    "Urgency", "ParentStatusWithDomain",
    "DateVisitMadeFromLastVisit", "DateForNextVisitFromLastVisit",
    "LatestVisitStage", "LatestArea",
    "DateOfLastCreateFromLastVisit", "DateOfLastEditFromLastVisit",
    "DateDiscovered", "CreationDate_1"
  ]
  
  features_data = []
  offset = 0
  batch_size = 2000
  max_failed_attempts = 5
  failed_batches = []
  
  while True:
    print(f"  Fetching batch at offset {offset}...")
    
    @retry(stop=stop_after_attempt(3), wait=wait_fixed(2))
    def fetch_batch():
      return weed_layer.query(
        where="1=1",
        out_fields=out_fields,
        return_geometry=False,
        result_offset=offset,
        result_record_count=batch_size,
        return_all_records=False
      )
    
    try:
      result = fetch_batch()
      batch_features = result.features
      
      if not batch_features:
        break
      
      for feature in batch_features:
        attrs = feature.attributes
        features_data.append({
          'WeedLocation_OBJECTID': attrs.get('OBJECTID'),
          'GlobalID': attrs.get('GlobalID'),
          'Urgency': attrs.get('Urgency'),
          'ParentStatusWithDomain': attrs.get('ParentStatusWithDomain'),
          'DateVisitMadeFromLastVisit': attrs.get('DateVisitMadeFromLastVisit'),
          'DateForNextVisitFromLastVisit': attrs.get('DateForNextVisitFromLastVisit'),
          'LatestVisitStage': attrs.get('LatestVisitStage'),
          'LatestArea': attrs.get('LatestArea'),
          'DateOfLastCreateFromLastVisit': attrs.get('DateOfLastCreateFromLastVisit'),
          'DateOfLastEditFromLastVisit': attrs.get('DateOfLastEditFromLastVisit'),
          'DateDiscovered': attrs.get('DateDiscovered'),
          'weed_CreationDate_1': attrs.get('CreationDate_1')
        })
      
      print(f"  Loaded {len(batch_features)} features (total: {len(features_data)})")
      
      if len(batch_features) < batch_size:
        break
      
      offset += batch_size
      
    except Exception as e:
      print(f"  WARNING: Batch at offset {offset} (size {batch_size}) failed: {type(e).__name__}")
      
      smaller_sizes = [1000, 500, 250, 100]
      recovered = False
      
      for smaller_size in smaller_sizes:
        if smaller_size >= batch_size:
          continue
        
        print(f"  Retrying with smaller batch size: {smaller_size}")
        sub_offset = offset
        sub_features = []
        
        try:
          while sub_offset < offset + batch_size:
            @retry(stop=stop_after_attempt(2), wait=wait_fixed(1))
            def fetch_small_batch():
              return weed_layer.query(
                where="1=1",
                out_fields=out_fields,
                return_geometry=False,
                result_offset=sub_offset,
                result_record_count=smaller_size,
                return_all_records=False
              )
            
            result = fetch_small_batch()
            batch_features = result.features
            
            if not batch_features:
              break
            
            for feature in batch_features:
              attrs = feature.attributes
              sub_features.append({
                'WeedLocation_OBJECTID': attrs.get('OBJECTID'),
                'GlobalID': attrs.get('GlobalID'),
                'Urgency': attrs.get('Urgency'),
                'ParentStatusWithDomain': attrs.get('ParentStatusWithDomain'),
                'DateVisitMadeFromLastVisit': attrs.get('DateVisitMadeFromLastVisit'),
                'DateForNextVisitFromLastVisit': attrs.get('DateForNextVisitFromLastVisit'),
                'LatestVisitStage': attrs.get('LatestVisitStage'),
                'LatestArea': attrs.get('LatestArea'),
                'DateOfLastCreateFromLastVisit': attrs.get('DateOfLastCreateFromLastVisit'),
                'DateOfLastEditFromLastVisit': attrs.get('DateOfLastEditFromLastVisit'),
                'DateDiscovered': attrs.get('DateDiscovered'),
                'weed_CreationDate_1': attrs.get('CreationDate_1')
              })
            
            sub_offset += smaller_size
            
            if len(batch_features) < smaller_size:
              break
          
          features_data.extend(sub_features)
          print(f"  Recovered {len(sub_features)} features with smaller batches (total: {len(features_data)})")
          recovered = True
          break
          
        except Exception as sub_e:
          print(f"  Failed with batch size {smaller_size}: {type(sub_e).__name__}")
          continue
      
      if not recovered:
        print(f"  Could not recover batch at offset {offset}, skipping...")
        failed_batches.append(offset)
        
        if len(failed_batches) >= max_failed_attempts:
          print(f"  ERROR: Too many failed batches ({len(failed_batches)}), stopping.")
          break
      
      offset += batch_size
  
  if failed_batches:
    print(f"\nWARNING: Failed to load {len(failed_batches)} batches at offsets: {failed_batches}")
  
  df = pd.DataFrame(features_data)
  print(f"Loaded {len(df)} weed locations total")
  return df


def load_visits_table(visits_table):
  """Load all visits from Visits_Table using manual pagination"""
  print("Loading Visits_Table records...")
  
  out_fields = [
    "OBJECTID", "GUID_visits",
    "DifficultyChild", "WeedVisitStatus",
    "DateCheck", "DateForReturnVisit",
    "VisitStage", "Area",
    "CreationDate_1", "EditDate_1"
  ]
  
  visits_data = []
  offset = 0
  batch_size = 2000
  max_failed_attempts = 5
  failed_batches = []
  
  while True:
    print(f"  Fetching batch at offset {offset}...")
    
    @retry(stop=stop_after_attempt(3), wait=wait_fixed(2))
    def fetch_batch():
      return visits_table.query(
        where="1=1",
        out_fields=out_fields,
        return_geometry=False,
        result_offset=offset,
        result_record_count=batch_size,
        return_all_records=False
      )
    
    try:
      result = fetch_batch()
      batch_features = result.features
      
      if not batch_features:
        break
      
      for feature in batch_features:
        attrs = feature.attributes
        visits_data.append({
          'Visit_OBJECTID': attrs.get('OBJECTID'),
          'GUID_visits': attrs.get('GUID_visits'),
          'DifficultyChild': attrs.get('DifficultyChild'),
          'WeedVisitStatus': attrs.get('WeedVisitStatus'),
          'DateCheck': attrs.get('DateCheck'),
          'DateForReturnVisit': attrs.get('DateForReturnVisit'),
          'VisitStage': attrs.get('VisitStage'),
          'Area': attrs.get('Area'),
          'visit_CreationDate_1': attrs.get('CreationDate_1'),
          'visit_EditDate_1': attrs.get('EditDate_1')
        })
      
      print(f"  Loaded {len(batch_features)} records (total: {len(visits_data)})")
      
      if len(batch_features) < batch_size:
        break
      
      offset += batch_size
      
    except Exception as e:
      print(f"  WARNING: Batch at offset {offset} (size {batch_size}) failed: {type(e).__name__}")
      
      smaller_sizes = [1000, 500, 250, 100]
      recovered = False
      
      for smaller_size in smaller_sizes:
        if smaller_size >= batch_size:
          continue
        
        print(f"  Retrying with smaller batch size: {smaller_size}")
        sub_offset = offset
        sub_visits = []
        
        try:
          while sub_offset < offset + batch_size:
            @retry(stop=stop_after_attempt(2), wait=wait_fixed(1))
            def fetch_small_batch():
              return visits_table.query(
                where="1=1",
                out_fields=out_fields,
                return_geometry=False,
                result_offset=sub_offset,
                result_record_count=smaller_size,
                return_all_records=False
              )
            
            result = fetch_small_batch()
            batch_features = result.features
            
            if not batch_features:
              break
            
            for feature in batch_features:
              attrs = feature.attributes
              sub_visits.append({
                'Visit_OBJECTID': attrs.get('OBJECTID'),
                'GUID_visits': attrs.get('GUID_visits'),
                'DifficultyChild': attrs.get('DifficultyChild'),
                'WeedVisitStatus': attrs.get('WeedVisitStatus'),
                'DateCheck': attrs.get('DateCheck'),
                'DateForReturnVisit': attrs.get('DateForReturnVisit'),
                'VisitStage': attrs.get('VisitStage'),
                'Area': attrs.get('Area'),
                'visit_CreationDate_1': attrs.get('CreationDate_1'),
                'visit_EditDate_1': attrs.get('EditDate_1')
              })
            
            sub_offset += smaller_size
            
            if len(batch_features) < smaller_size:
              break
          
          visits_data.extend(sub_visits)
          print(f"  Recovered {len(sub_visits)} records with smaller batches (total: {len(visits_data)})")
          recovered = True
          break
          
        except Exception as sub_e:
          print(f"  Failed with batch size {smaller_size}: {type(sub_e).__name__}")
          continue
      
      if not recovered:
        print(f"  Could not recover batch at offset {offset}, skipping...")
        failed_batches.append(offset)
        
        if len(failed_batches) >= max_failed_attempts:
          print(f"  ERROR: Too many failed batches ({len(failed_batches)}), stopping.")
          break
      
      offset += batch_size
  
  if failed_batches:
    print(f"\nWARNING: Failed to load {len(failed_batches)} batches at offsets: {failed_batches}")
  
  df = pd.DataFrame(visits_data)
  print(f"Loaded {len(df)} visit records total")
  return df


def get_latest_visit_per_location(visits_df):
  """Get the latest visit (by DateCheck or Creation_Date1) for each weed location"""
  if len(visits_df) == 0:
    expected_columns = [
      'GUID_visits', 'Visit_OBJECTID', 'DifficultyChild', 'WeedVisitStatus',
      'DateCheck', 'DateForReturnVisit', 'VisitStage', 'Area',
      'visit_CreationDate_1', 'visit_EditDate_1'
    ]
    return pd.DataFrame(columns=expected_columns)
  
  # For visits with DateCheck, sort by DateCheck
  visits_with_dates = visits_df[visits_df['DateCheck'].notna()].copy()
  
  if len(visits_with_dates) > 0:
    visits_with_dates = visits_with_dates.sort_values('DateCheck', ascending=False)
    latest_visits_datecheck = visits_with_dates.groupby('GUID_visits').first().reset_index()
  else:
    expected_columns = [
      'GUID_visits', 'Visit_OBJECTID', 'DifficultyChild', 'WeedVisitStatus',
      'DateCheck', 'DateForReturnVisit', 'VisitStage', 'Area',
      'visit_CreationDate_1', 'visit_EditDate_1'
    ]
    latest_visits_datecheck = pd.DataFrame(columns=expected_columns)
  
  # For visits without DateCheck, get the one with latest CreationDate_1
  visits_no_datecheck = visits_df[visits_df['DateCheck'].isna()].copy()
  if len(visits_no_datecheck) > 0 and 'visit_CreationDate_1' in visits_no_datecheck.columns:
    visits_no_datecheck_with_creation = visits_no_datecheck[visits_no_datecheck['visit_CreationDate_1'].notna()].copy()
    if len(visits_no_datecheck_with_creation) > 0:
      visits_no_datecheck_with_creation = visits_no_datecheck_with_creation.sort_values('visit_CreationDate_1', ascending=False)
      latest_visits_creation = visits_no_datecheck_with_creation.groupby('GUID_visits').first().reset_index()
      
      # Combine: prefer DateCheck, but include Creation_Date1 for those without DateCheck
      all_guids_with_datecheck = set(latest_visits_datecheck['GUID_visits'])
      latest_visits_creation_only = latest_visits_creation[~latest_visits_creation['GUID_visits'].isin(all_guids_with_datecheck)]
      latest_visits = pd.concat([latest_visits_datecheck, latest_visits_creation_only], ignore_index=True)
    else:
      latest_visits = latest_visits_datecheck
  else:
    latest_visits = latest_visits_datecheck
  
  return latest_visits


def load_weed_locations_with_visits(weed_layer, visits_table):
  """Load weed locations and join with latest visit data"""
  # Load data
  weeds_df = load_weed_locations(weed_layer)
  visits_df = load_visits_table(visits_table)
  
  # Get latest visit per location
  print("Finding latest visit for each weed location...")
  latest_visits = get_latest_visit_per_location(visits_df)
  
  # Join weed locations with latest visits
  merge_cols = [
    'GUID_visits', 'Visit_OBJECTID',
    'DifficultyChild', 'WeedVisitStatus',
    'DateCheck', 'DateForReturnVisit',
    'VisitStage', 'Area',
    'visit_CreationDate_1', 'visit_EditDate_1'
  ]
  merge_cols = [col for col in merge_cols if col in latest_visits.columns]
  
  merged_df = weeds_df.merge(
    latest_visits[merge_cols],
    left_on='GlobalID',
    right_on='GUID_visits',
    how='left'
  )
  
  merged_df = merged_df.drop(columns=['GUID_visits'], errors='ignore')
  
  print(f"Joined data: {len(merged_df)} weed locations with visit information")
  return merged_df


def convert_arcgis_timestamp_to_iso(timestamp):
  """
  Convert ArcGIS epoch millisecond timestamp to ISO 8601 datetime string
  
  Args:
    timestamp: Epoch milliseconds (int or float) or None
  
  Returns:
    ISO formatted datetime string or None if input is None
  """
  if pd.isna(timestamp):
    return None
  
  try:
    # ArcGIS timestamps are in milliseconds since epoch
    dt = datetime.fromtimestamp(timestamp / 1000.0)
    return dt.strftime('%Y-%m-%d %H:%M:%S')
  except (ValueError, TypeError, OSError):
    return None


def check_field_mismatches(merged_df, ignore_creation_edit_dates=False):
  """
  Check all field pairs between WeedLocations and Visits_Table
  
  Args:
    merged_df: DataFrame with merged WeedLocations and Visits data
    ignore_creation_edit_dates: If True, skip checking CreationDate_1 and EditDate_1 fields
  
  Returns DataFrame with mismatch indicators for each field pair
  """
  # Define field pairs: (WeedLocations field, Visits_Table field, display name)
  field_pairs = [
    ('Urgency', 'DifficultyChild', 'Urgency_Mismatch'),
    ('ParentStatusWithDomain', 'WeedVisitStatus', 'Status_Mismatch'),
    ('DateVisitMadeFromLastVisit', 'DateCheck', 'DateVisitMade_Mismatch'),
    ('DateForNextVisitFromLastVisit', 'DateForReturnVisit', 'DateForNextVisit_Mismatch'),
    ('LatestVisitStage', 'VisitStage', 'VisitStage_Mismatch'),
    ('LatestArea', 'Area', 'Area_Mismatch'),
    ('DateOfLastCreateFromLastVisit', 'visit_CreationDate_1', 'DateOfLastCreate_Mismatch'),
    ('DateOfLastEditFromLastVisit', 'visit_EditDate_1', 'DateOfLastEdit_Mismatch')
  ]
  
  # Filter out creation/edit date fields if requested
  if ignore_creation_edit_dates:
    field_pairs = [
      fp for fp in field_pairs
      if fp[2] not in ['DateOfLastCreate_Mismatch', 'DateOfLastEdit_Mismatch']
    ]
  
  result_df = merged_df.copy()
  mismatch_columns = []
  
  for weed_field, visit_field, mismatch_col in field_pairs:
    # Create mismatch indicator column
    result_df[mismatch_col] = ''
    
    # Check for mismatches
    for idx, row in result_df.iterrows():
      weed_val = row.get(weed_field)
      visit_val = row.get(visit_field)
      
      # Skip if visit value is missing (no visit record)
      if pd.isna(visit_val):
        continue
      
      # Special handling for ParentStatusWithDomain
      if weed_field == 'ParentStatusWithDomain':
        # Ignore differences if ParentStatusWithDomain starts with "Purple"
        if pd.notna(weed_val) and str(weed_val).startswith('Purple'):
          continue
      
      # Check for mismatch
      if weed_val != visit_val:
        result_df.at[idx, mismatch_col] = 'X'
    
    mismatch_columns.append(mismatch_col)
  
  # Add a column indicating if ANY field has a mismatch
  result_df['Has_Any_Mismatch'] = result_df[mismatch_columns].apply(
    lambda row: any(row == 'X'), axis=1
  )
  
  return result_df, mismatch_columns


def generate_mismatch_report(merged_df, output_file='weed_visits_field_comparison.xlsx', ignore_creation_edit_dates=False):
  """
  Generate Excel spreadsheet with summary and detailed mismatch data
  
  Args:
    merged_df: DataFrame with merged data
    output_file: Path to output Excel file
    ignore_creation_edit_dates: If True, skip CreationDate_1 and EditDate_1 comparisons
  """
  # Check field mismatches
  result_df, mismatch_columns = check_field_mismatches(merged_df, ignore_creation_edit_dates)
  
  # Calculate summary statistics
  total_locations = len(result_df)
  locations_with_visits = result_df['Visit_OBJECTID'].notna().sum()
  locations_with_mismatches = result_df['Has_Any_Mismatch'].sum()
  
  # Count mismatches per field pair
  field_pair_summary = []
  field_pairs_info = [
    ('Urgency', 'DifficultyChild', 'Urgency_Mismatch'),
    ('ParentStatusWithDomain', 'WeedVisitStatus', 'Status_Mismatch'),
    ('DateVisitMadeFromLastVisit', 'DateCheck', 'DateVisitMade_Mismatch'),
    ('DateForNextVisitFromLastVisit', 'DateForReturnVisit', 'DateForNextVisit_Mismatch'),
    ('LatestVisitStage', 'VisitStage', 'VisitStage_Mismatch'),
    ('LatestArea', 'Area', 'Area_Mismatch'),
    ('DateOfLastCreateFromLastVisit', 'visit_CreationDate_1', 'DateOfLastCreate_Mismatch'),
    ('DateOfLastEditFromLastVisit', 'visit_EditDate_1', 'DateOfLastEdit_Mismatch')
  ]
  
  # Filter out creation/edit date fields if requested
  if ignore_creation_edit_dates:
    field_pairs_info = [
      fp for fp in field_pairs_info
      if fp[2] not in ['DateOfLastCreate_Mismatch', 'DateOfLastEdit_Mismatch']
    ]
  
  for weed_field, visit_field, mismatch_col in field_pairs_info:
    mismatch_count = (result_df[mismatch_col] == 'X').sum()
    field_pair_summary.append({
      'WeedLocations_Field': weed_field,
      'Visits_Table_Field': visit_field,
      'Mismatch_Count': mismatch_count,
      'Mismatch_Percentage': f"{(mismatch_count / locations_with_visits * 100):.1f}%" if locations_with_visits > 0 else "0%"
    })
  
  summary_df = pd.DataFrame(field_pair_summary)
  
  # Create overall summary
  overall_summary = pd.DataFrame([
    {'Metric': 'Total WeedLocations', 'Value': total_locations},
    {'Metric': 'Locations with Visit Records', 'Value': locations_with_visits},
    {'Metric': 'Locations with Field Mismatches', 'Value': locations_with_mismatches},
    {'Metric': 'Percentage with Mismatches', 
     'Value': f"{(locations_with_mismatches / locations_with_visits * 100):.1f}%" if locations_with_visits > 0 else "0%"}
  ])
  
  # Filter to only rows with mismatches for detailed sheet
  mismatches_df = result_df[result_df['Has_Any_Mismatch']].copy()
  
  # Select columns for detailed output
  detail_columns = [
    'WeedLocation_OBJECTID',
    'Visit_OBJECTID'
  ] + mismatch_columns + [
    'Urgency', 'DifficultyChild',
    'ParentStatusWithDomain', 'WeedVisitStatus',
    'DateVisitMadeFromLastVisit', 'DateCheck',
    'DateForNextVisitFromLastVisit', 'DateForReturnVisit',
    'LatestVisitStage', 'VisitStage',
    'LatestArea', 'Area',
    'DateOfLastCreateFromLastVisit', 'visit_CreationDate_1',
    'DateOfLastEditFromLastVisit', 'visit_EditDate_1'
  ]
  
  # Ensure all columns exist
  detail_columns = [col for col in detail_columns if col in mismatches_df.columns]
  mismatches_detail_df = mismatches_df[detail_columns].copy()
  
  # Convert date columns to ISO format for Excel output
  date_columns = [
    'DateVisitMadeFromLastVisit', 'DateCheck',
    'DateForNextVisitFromLastVisit', 'DateForReturnVisit',
    'DateOfLastCreateFromLastVisit', 'visit_CreationDate_1',
    'DateOfLastEditFromLastVisit', 'visit_EditDate_1',
    'DateDiscovered', 'weed_CreationDate_1'
  ]
  
  for df in [mismatches_detail_df]:
    for col in date_columns:
      if col in df.columns:
        df[col] = df[col].apply(convert_arcgis_timestamp_to_iso)
  
  # Create a copy of result_df for all records output with converted dates
  all_records_df = result_df[detail_columns].copy()
  for col in date_columns:
    if col in all_records_df.columns:
      all_records_df[col] = all_records_df[col].apply(convert_arcgis_timestamp_to_iso)
  
  # Prepare data for formatting: track which Visit fields need bold+prefix
  # Map: field_pairs to (weed_col, visit_col, mismatch_col)
  field_format_map = [
    ('Urgency', 'DifficultyChild', 'Urgency_Mismatch'),
    ('ParentStatusWithDomain', 'WeedVisitStatus', 'Status_Mismatch'),
    ('DateVisitMadeFromLastVisit', 'DateCheck', 'DateVisitMade_Mismatch'),
    ('DateForNextVisitFromLastVisit', 'DateForReturnVisit', 'DateForNextVisit_Mismatch'),
    ('LatestVisitStage', 'VisitStage', 'VisitStage_Mismatch'),
    ('LatestArea', 'Area', 'Area_Mismatch'),
    ('DateOfLastCreateFromLastVisit', 'visit_CreationDate_1', 'DateOfLastCreate_Mismatch'),
    ('DateOfLastEditFromLastVisit', 'visit_EditDate_1', 'DateOfLastEdit_Mismatch')
  ]
  
  # Filter based on ignore_creation_edit_dates flag
  if ignore_creation_edit_dates:
    field_format_map = [
      fm for fm in field_format_map
      if fm[2] not in ['DateOfLastCreate_Mismatch', 'DateOfLastEdit_Mismatch']
    ]
  
  # Prefix Visit field values with ← where there's a mismatch
  for weed_field, visit_field, mismatch_col in field_format_map:
    if visit_field in mismatches_detail_df.columns and mismatch_col in mismatches_detail_df.columns:
      # Add prefix to mismatched Visit field values (skip None values)
      mask = (mismatches_detail_df[mismatch_col] == 'X') & (mismatches_detail_df[visit_field].notna())
      mismatches_detail_df.loc[mask, visit_field] = '← ' + mismatches_detail_df.loc[mask, visit_field].astype(str)
    
    # Also prefix in all_records_df for the All Records sheet
    if visit_field in all_records_df.columns and mismatch_col in all_records_df.columns:
      mask = (all_records_df[mismatch_col] == 'X') & (all_records_df[visit_field].notna())
      all_records_df.loc[mask, visit_field] = '← ' + all_records_df.loc[mask, visit_field].astype(str)
  
  # Create Missing Visit Date sheet - visits where DateCheck is not set
  missing_date_df = result_df[
    (result_df['Visit_OBJECTID'].notna()) & 
    (result_df['DateCheck'].isna())
  ].copy()
  
  missing_date_columns = [
    'WeedLocation_OBJECTID', 'Visit_OBJECTID',
    'DateCheck', 'visit_CreationDate_1',
    'WeedVisitStatus', 'DifficultyChild',
    'VisitStage', 'Area'
  ]
  missing_date_columns = [col for col in missing_date_columns if col in missing_date_df.columns]
  missing_date_export = missing_date_df[missing_date_columns].copy()
  
  # Convert dates to ISO format for Missing Visit Date sheet
  for col in ['DateCheck', 'visit_CreationDate_1']:
    if col in missing_date_export.columns:
      missing_date_export[col] = missing_date_export[col].apply(convert_arcgis_timestamp_to_iso)
  
  # Prefix CreationDate_1 if not "2021-10-09 21:19:26"
  reference_date = "2021-10-09 21:19:26"
  if 'visit_CreationDate_1' in missing_date_export.columns:
    mask = (missing_date_export['visit_CreationDate_1'].notna()) & \
           (missing_date_export['visit_CreationDate_1'] != reference_date)
    missing_date_export.loc[mask, 'visit_CreationDate_1'] = \
      '← ' + missing_date_export.loc[mask, 'visit_CreationDate_1'].astype(str)
  
  # Create Missing Status sheet - visits where WeedVisitStatus is not set
  missing_status_df = result_df[
    (result_df['Visit_OBJECTID'].notna()) & 
    (result_df['WeedVisitStatus'].isna())
  ].copy()
  
  missing_status_columns = [
    'WeedLocation_OBJECTID', 'Visit_OBJECTID',
    'WeedVisitStatus', 'ParentStatusWithDomain',
    'DateCheck', 'visit_CreationDate_1',
    'DifficultyChild', 'VisitStage', 'Area'
  ]
  missing_status_columns = [col for col in missing_status_columns if col in missing_status_df.columns]
  missing_status_export = missing_status_df[missing_status_columns].copy()
  
  # Convert dates to ISO format for Missing Status sheet
  for col in ['DateCheck', 'visit_CreationDate_1']:
    if col in missing_status_export.columns:
      missing_status_export[col] = missing_status_export[col].apply(convert_arcgis_timestamp_to_iso)
  
  # Write to Excel
  print(f"\nGenerating report: {output_file}")
  with pd.ExcelWriter(output_file, engine='openpyxl') as writer:
    overall_summary.to_excel(writer, sheet_name='Overall Summary', index=False)
    summary_df.to_excel(writer, sheet_name='Field Pair Summary', index=False)
    mismatches_detail_df.to_excel(writer, sheet_name='Detailed Mismatches', index=False)
    missing_date_export.to_excel(writer, sheet_name='Missing Visit Date', index=False)
    missing_status_export.to_excel(writer, sheet_name='Missing Status', index=False)
    
    # Also include full data for reference
    all_records_df.to_excel(writer, sheet_name='All Records', index=False)
    
    # Apply bold formatting to Visit fields with mismatches
    from openpyxl.styles import Font
    
    workbook = writer.book
    bold_font = Font(bold=True)
    
    # Format both Detailed Mismatches and All Records sheets
    for sheet_name in ['Detailed Mismatches', 'All Records']:
      sheet = workbook[sheet_name]
      
      # Get column indices for Visit fields
      header_row = [cell.value for cell in sheet[1]]
      visit_field_indices = {}
      for weed_field, visit_field, mismatch_col in field_format_map:
        if visit_field in header_row:
          # openpyxl uses 1-based indexing
          visit_field_indices[visit_field] = header_row.index(visit_field) + 1
      
      # Apply bold formatting to cells with ← prefix
      for row_idx in range(2, sheet.max_row + 1):  # Start from row 2 (skip header)
        for visit_field, col_idx in visit_field_indices.items():
          cell = sheet.cell(row=row_idx, column=col_idx)
          if cell.value and str(cell.value).startswith('← '):
            cell.font = bold_font
    
    # Format Missing Visit Date sheet - bold CreationDate_1 cells with ← prefix
    if 'Missing Visit Date' in workbook.sheetnames:
      missing_date_sheet = workbook['Missing Visit Date']
      header_row = [cell.value for cell in missing_date_sheet[1]]
      
      if 'visit_CreationDate_1' in header_row:
        creation_col_idx = header_row.index('visit_CreationDate_1') + 1
        
        for row_idx in range(2, missing_date_sheet.max_row + 1):
          cell = missing_date_sheet.cell(row=row_idx, column=creation_col_idx)
          if cell.value and str(cell.value).startswith('← '):
            cell.font = bold_font
  
  print(f"Report saved to: {output_file}")
  print(f"\nSummary:")
  print(f"  Total locations: {total_locations:,}")
  print(f"  Locations with visits: {locations_with_visits:,}")
  print(f"  Locations with mismatches: {locations_with_mismatches:,}")
  if locations_with_visits > 0:
    print(f"  Mismatch rate: {(locations_with_mismatches / locations_with_visits * 100):.1f}%")
  print(f"  Missing visit date (DateCheck): {len(missing_date_export):,}")
  print(f"  Missing status (WeedVisitStatus): {len(missing_status_export):,}")
  
  return overall_summary, summary_df, mismatches_detail_df


def analyze_date_matching(merged_df):
  """
  Analyze date matching between WeedLocations and Visits_Table
  
  Returns counts for various date matching scenarios
  """
  total = len(merged_df)
  
  # Category 1: DateVisitMadeFromLastVisit matches latest visit DateCheck
  matching_datecheck = merged_df[
    (merged_df['DateVisitMadeFromLastVisit'].notna()) &
    (merged_df['DateCheck'].notna()) &
    (merged_df['DateVisitMadeFromLastVisit'] == merged_df['DateCheck'])
  ]
  
  # Category 2: Weed date set, visit DateCheck not set
  weed_set_visit_datecheck_not = merged_df[
    (merged_df['DateVisitMadeFromLastVisit'].notna()) &
    (merged_df['DateCheck'].isna())
  ]
  
  # Category 2a: Of those, how many match visit Creation_Date1?
  weed_matches_visit_creation = weed_set_visit_datecheck_not[
    (weed_set_visit_datecheck_not['visit_CreationDate_1'].notna()) &
    (weed_set_visit_datecheck_not['DateVisitMadeFromLastVisit'] == weed_set_visit_datecheck_not['visit_CreationDate_1'])
  ]
  
  # Category 3: Weed date not set
  weed_not_set = merged_df[merged_df['DateVisitMadeFromLastVisit'].isna()]
  
  # Category 4: Both DateCheck set but don't match
  not_matching = merged_df[
    (merged_df['DateVisitMadeFromLastVisit'].notna()) &
    (merged_df['DateCheck'].notna()) &
    (merged_df['DateVisitMadeFromLastVisit'] != merged_df['DateCheck'])
  ]
  
  # New analysis: Date source hierarchy
  # Count features by which date field is set (priority order)
  has_visit_datecheck = merged_df[merged_df['DateCheck'].notna()]
  has_visit_creation_only = merged_df[
    (merged_df['DateCheck'].isna()) &
    (merged_df['visit_CreationDate_1'].notna())
  ]
  has_weed_discovered_only = merged_df[
    (merged_df['DateCheck'].isna()) &
    (merged_df['visit_CreationDate_1'].isna()) &
    (merged_df['DateDiscovered'].notna())
  ]
  has_weed_creation_only = merged_df[
    (merged_df['DateCheck'].isna()) &
    (merged_df['visit_CreationDate_1'].isna()) &
    (merged_df['DateDiscovered'].isna()) &
    (merged_df['weed_CreationDate_1'].notna())
  ]
  has_no_dates = merged_df[
    (merged_df['DateCheck'].isna()) &
    (merged_df['visit_CreationDate_1'].isna()) &
    (merged_df['DateDiscovered'].isna()) &
    (merged_df['weed_CreationDate_1'].isna())
  ]
  
  return {
    'total': total,
    'matching_datecheck': len(matching_datecheck),
    'weed_set_visit_datecheck_not': len(weed_set_visit_datecheck_not),
    'weed_matches_visit_creation': len(weed_matches_visit_creation),
    'weed_not_set': len(weed_not_set),
    'not_matching': len(not_matching),
    # Date source hierarchy
    'has_visit_datecheck': len(has_visit_datecheck),
    'has_visit_creation_only': len(has_visit_creation_only),
    'has_weed_discovered_only': len(has_weed_discovered_only),
    'has_weed_creation_only': len(has_weed_creation_only),
    'has_no_dates': len(has_no_dates)
  }


def format_report(counts):
  """Format analysis results as a readable report"""
  total = counts['total']
  
  report = []
  report.append("\n" + "=" * 80)
  report.append("WEED LOCATIONS vs VISITS TABLE - DATE ANALYSIS REPORT")
  report.append("=" * 80)
  report.append(f"\nTotal Features Analyzed: {total:,}")
  report.append("\n" + "-" * 80)
  report.append("PART 1: DATE SYNCHRONIZATION ANALYSIS")
  report.append("-" * 80)
  
  if total == 0:
    report.append("\nNo features found to analyze.")
    report.append("=" * 80)
    return "\n".join(report)
  
  # Category 1: Matching DateCheck
  matching = counts['matching_datecheck']
  matching_pct = (matching / total * 100) if total > 0 else 0
  report.append(f"\n1. DateVisitMadeFromLastVisit == Latest Visit DateCheck")
  report.append(f"   Count: {matching:,} ({matching_pct:.1f}%)")
  report.append(f"   Status: ✓ Dates are synchronized with visit DateCheck")
  
  # Category 2: Weed set, visit DateCheck not set
  weed_set = counts['weed_set_visit_datecheck_not']
  weed_set_pct = (weed_set / total * 100) if total > 0 else 0
  weed_matches_creation = counts['weed_matches_visit_creation']
  weed_matches_creation_pct = (weed_matches_creation / weed_set * 100) if weed_set > 0 else 0
  report.append(f"\n2. DateVisitMadeFromLastVisit SET, but Latest Visit DateCheck NOT SET")
  report.append(f"   Count: {weed_set:,} ({weed_set_pct:.1f}%)")
  report.append(f"   Status: ⚠ Weed location has date but no related visit DateCheck")
  report.append(f"   → Of these, {weed_matches_creation:,} ({weed_matches_creation_pct:.1f}%) match")
  report.append(f"     Latest Visit Creation_Date1")
  
  # Category 3: Weed not set
  weed_not_set = counts['weed_not_set']
  weed_not_set_pct = (weed_not_set / total * 100) if total > 0 else 0
  report.append(f"\n3. DateVisitMadeFromLastVisit NOT SET")
  report.append(f"   Count: {weed_not_set:,} ({weed_not_set_pct:.1f}%)")
  report.append(f"   Status: ℹ Weed location has no visit date recorded")
  
  # Category 4: Not matching
  not_matching = counts['not_matching']
  not_matching_pct = (not_matching / total * 100) if total > 0 else 0
  report.append(f"\n4. DateVisitMadeFromLastVisit != Latest Visit DateCheck")
  report.append(f"   Count: {not_matching:,} ({not_matching_pct:.1f}%)")
  report.append(f"   Status: ✗ Dates are out of sync")
  
  # Part 2: Date Source Hierarchy
  report.append("\n" + "-" * 80)
  report.append("PART 2: DATE SOURCE HIERARCHY (Priority Order)")
  report.append("-" * 80)
  
  has_visit_datecheck = counts['has_visit_datecheck']
  has_visit_datecheck_pct = (has_visit_datecheck / total * 100) if total > 0 else 0
  report.append(f"\n1. Latest Visit DateCheck is SET")
  report.append(f"   Count: {has_visit_datecheck:,} ({has_visit_datecheck_pct:.1f}%)")
  report.append(f"   Priority: Highest - Use this date")
  
  has_visit_creation = counts['has_visit_creation_only']
  has_visit_creation_pct = (has_visit_creation / total * 100) if total > 0 else 0
  report.append(f"\n2. Latest Visit Creation_Date1 is SET (DateCheck not set)")
  report.append(f"   Count: {has_visit_creation:,} ({has_visit_creation_pct:.1f}%)")
  report.append(f"   Priority: High - Fallback to creation date")
  
  has_weed_discovered = counts['has_weed_discovered_only']
  has_weed_discovered_pct = (has_weed_discovered / total * 100) if total > 0 else 0
  report.append(f"\n3. Weed DateDiscovered is SET (no visit dates)")
  report.append(f"   Count: {has_weed_discovered:,} ({has_weed_discovered_pct:.1f}%)")
  report.append(f"   Priority: Medium - Use weed discovery date")
  
  has_weed_creation = counts['has_weed_creation_only']
  has_weed_creation_pct = (has_weed_creation / total * 100) if total > 0 else 0
  report.append(f"\n4. Weed Creation_Date1 is SET (no other dates)")
  report.append(f"   Count: {has_weed_creation:,} ({has_weed_creation_pct:.1f}%)")
  report.append(f"   Priority: Low - Last resort date")
  
  has_no_dates = counts['has_no_dates']
  has_no_dates_pct = (has_no_dates / total * 100) if total > 0 else 0
  report.append(f"\n5. NO DATES SET")
  report.append(f"   Count: {has_no_dates:,} ({has_no_dates_pct:.1f}%)")
  report.append(f"   Priority: None - No date information available")
  
  # Summary
  report.append("\n" + "-" * 80)
  report.append("SUMMARY")
  report.append("-" * 80)
  in_sync = matching
  out_of_sync = weed_set + not_matching
  no_data = weed_not_set
  
  report.append(f"In Sync:     {in_sync:,} ({in_sync/total*100:.1f}%)")
  report.append(f"Out of Sync: {out_of_sync:,} ({out_of_sync/total*100:.1f}%)")
  report.append(f"No Data:     {no_data:,} ({no_data/total*100:.1f}%)")
  report.append("=" * 80 + "\n")
  
  return "\n".join(report)


def analyze_weed_visits(environment, output_file=None, ignore_creation_edit_dates=False):
  """
  Main analysis function
  
  Args:
    environment: Environment name (e.g., 'production', 'development')
    output_file: Optional output Excel file path
    ignore_creation_edit_dates: If True, skip CreationDate_1 and EditDate_1 comparisons
  """
  print(f"Starting Weed Visits Analysis for '{environment}' environment...")
  
  if ignore_creation_edit_dates:
    print("Note: Ignoring CreationDate_1 and EditDate_1 field comparisons")
  
  # Connect to ArcGIS
  gis = connect_arcgis()
  
  # Get layers
  weed_layer, visits_table = get_layers(gis, environment)
  
  # Load and merge data
  merged_df = load_weed_locations_with_visits(weed_layer, visits_table)
  
  # Generate field comparison report
  if output_file is None:
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    output_file = f'weed_visits_field_comparison_{environment}_{timestamp}.xlsx'
  
  print("\nAnalyzing field mismatches...")
  overall_summary, field_summary, mismatches = generate_mismatch_report(
    merged_df, output_file, ignore_creation_edit_dates
  )
  
  # Also run legacy date matching analysis for backward compatibility
  print("\nAnalyzing date matching (legacy report)...")
  counts = analyze_date_matching(merged_df)
  report = format_report(counts)
  print(report)
  
  return counts, merged_df, overall_summary, field_summary, mismatches


def main():
  parser = argparse.ArgumentParser(
    description="Analyze WeedLocations and Visits_Table field synchronization"
  )
  parser.add_argument(
    '--env',
    '--environment',
    dest='environment',
    required=True,
    help='Environment to analyze (e.g., development, production)'
  )
  parser.add_argument(
    '--output',
    '-o',
    dest='output_file',
    help='Output Excel file path (default: auto-generated with timestamp)'
  )
  parser.add_argument(
    '--ignore-dates',
    '--ignore-creation-edit-dates',
    dest='ignore_creation_edit_dates',
    action='store_true',
    help='Skip comparison of CreationDate_1 and EditDate_1 fields'
  )
  
  args = parser.parse_args()
  
  try:
    analyze_weed_visits(
      args.environment, 
      args.output_file, 
      args.ignore_creation_edit_dates
    )
  except Exception as e:
    print(f"\nError during analysis: {e}")
    raise


if __name__ == "__main__":
  main()

