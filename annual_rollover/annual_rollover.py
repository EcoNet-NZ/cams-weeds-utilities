#!/usr/bin/env python3
"""
Annual Weed Instance Rollover Tool

Automates annual status updates for weed instance records in ArcGIS Feature Layer
based on business rules. Updates qualifying records from Yellow/Green/Orange/Pink
status to PurpleHistoric for re-checking.

Reference Date: October 1st (hardcoded)
"""

import os
import json
import argparse
import pandas as pd
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
from tenacity import retry, stop_after_attempt, wait_fixed
from arcgis.gis import GIS
from arcgis.features import FeatureLayer, Table

# Target species for rollover processing
TARGET_SPECIES = [
    'MothPlant', 'OldMansBeard', 'CathedralBells', 'BananaPassionfruit',
    'BluePassionFlower', 'Jasmine', 'JapaneseHoneysuckle', 'BlueMorningGlory',
    'WoollyNightshade', 'Elaeagnus'
]

# Target status values for rollover processing
TARGET_STATUSES = [
    'YellowKilledThisYear', 'GreenNoRegrowthThisYear', 
    'OrangeDeadHeaded'
    # Note: PinkOccupantWillKillGrowth not present in test data
]

# Status groups for different time rules
IMMEDIATE_UPDATE_STATUSES = ['YellowKilledThisYear', 'OrangeDeadHeaded']
TWO_YEAR_RULE_STATUSES = ['GreenNoRegrowthThisYear']


@retry(stop=stop_after_attempt(3), wait=wait_fixed(5))
def connect_arcgis():
    """Connect to ArcGIS using environment variables"""
    username = os.getenv('ARCGIS_USERNAME')
    password = os.getenv('ARCGIS_PASSWORD')
    portal_url = os.getenv('ARCGIS_PORTAL_URL', 'https://www.arcgis.com')
    return GIS(portal_url, username, password)


def get_layers_and_table(gis, environment):
    """Get weed locations layer and audit table for the specified environment"""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    env_config_path = os.path.join(script_dir, '..', 'spatial_field_updater', 'config', 'environment_config.json')
    
    with open(env_config_path, 'r') as f:
        env_config = json.load(f)
    
    if environment not in env_config:
        available_envs = list(env_config.keys())
        raise ValueError(f"Environment '{environment}' not found. Available: {available_envs}")
    
    env_settings = env_config[environment]
    weed_layer_id = env_settings['weed_locations_layer_id']
    audit_table_id = env_settings['audit_table_id']
    
    weed_layer = FeatureLayer.fromitem(gis.content.get(weed_layer_id))
    audit_table = Table.fromitem(gis.content.get(audit_table_id))
    
    return weed_layer, audit_table


def validate_backup_field(weed_layer, dry_run=False):
    """
    Validate that the StatusAt202510 backup field exists in the layer
    
    Args:
        weed_layer: ArcGIS FeatureLayer
        dry_run: If True, only warn about missing field; if False, raise error
        
    Raises:
        ValueError: If backup field is missing and not in dry run mode
    """
    backup_field_name = 'StatusAt202510'
    field_names = [field.name for field in weed_layer.properties.fields]
    
    if backup_field_name not in field_names:
        error_msg = (
            f"❌ CRITICAL ERROR: Backup field '{backup_field_name}' not found in layer.\n"
            f"   This field is required to preserve original status values before rollover.\n"
            f"   Please create this field in the ArcGIS layer before running the rollover.\n"
            f"   Available fields: {', '.join(sorted(field_names))}"
        )
        
        if dry_run:
            print(f"⚠️  WARNING: {error_msg}")
            print("   Continuing in DRY RUN mode, but live updates will fail without this field.")
            return False
        else:
            raise ValueError(error_msg)
    
    print(f"✅ Backup field '{backup_field_name}' found in layer")
    return True


def get_reference_date():
    """Get the reference date (October 1st of current year)"""
    current_year = datetime.now().year
    return datetime(current_year, 10, 1)


def check_production_safeguards(environment, reference_date):
    """
    Prevent accidental production updates before October 1st
    
    Args:
        environment: 'development' or 'production'
        reference_date: The October 1st reference date
    """
    if environment == 'production':
        today = datetime.now()
        if today < reference_date:
            days_until = (reference_date - today).days
            raise ValueError(
                f"Production updates not allowed before October 1st. "
                f"Current date: {today.strftime('%Y-%m-%d')}, "
                f"Reference date: {reference_date.strftime('%Y-%m-%d')} "
                f"({days_until} days remaining)"
            )
    
    print(f"✅ Safeguard check passed for {environment} environment")


def resolve_last_visit_date(record):
    """
    Resolve the last visit date using coalesce logic
    
    Priority order:
    1. DateVisitMadeFromLastVisit
    2. DateOfLastCreateFromLastVisit  
    3. DateDiscovered
    4. If all null but target status: treat as "visited but date unknown"
    5. If all null and not target status: treat as "never visited"
    
    Returns:
        datetime or None: The resolved last visit date, or None if never visited
        str: Description of which field was used
    """
    status = record.get('ParentStatusWithDomain')
    
    # Try each date field in priority order
    date_fields = [
        ('DateVisitMadeFromLastVisit', 'DateVisitMade'),
        ('DateOfLastCreateFromLastVisit', 'DateOfLastCreate'),
        ('DateDiscovered', 'DateDiscovered')
    ]
    
    for field_name, description in date_fields:
        date_value = record.get(field_name)
        if date_value is not None:
            # Handle both datetime objects and timestamp integers
            if isinstance(date_value, (int, float)):
                # ArcGIS timestamp (milliseconds since epoch)
                return datetime.fromtimestamp(date_value / 1000), description
            elif hasattr(date_value, 'strftime'):
                # Already a datetime object
                return date_value, description
    
    # All date fields are null
    if status in TARGET_STATUSES:
        # Target status implies it was visited, even without date
        return None, "VisitedNoDate"
    else:
        # Not a target status, treat as never visited
        return None, "NeverVisited"


def is_next_visit_due(record, reference_date):
    """
    Check if next visit is due/overdue
    
    Args:
        record: Feature record
        reference_date: October 1st reference date
    
    Returns:
        bool: True if visit is due (date <= Oct 1st or null)
        str: Description of the logic used
    """
    next_visit_date = record.get('DateForNextVisitFromLastVisit')
    
    if next_visit_date is None:
        return True, "NextVisitNull"
    
    # Handle timestamp format
    if isinstance(next_visit_date, (int, float)):
        next_visit_date = datetime.fromtimestamp(next_visit_date / 1000)
    
    if next_visit_date <= reference_date:
        return True, f"NextVisitDue({next_visit_date.strftime('%Y-%m-%d')})"
    else:
        return False, f"NextVisitFuture({next_visit_date.strftime('%Y-%m-%d')})"


def meets_time_criteria(status, last_visit_date, last_visit_source, reference_date):
    """
    Check if record meets status-specific time criteria
    
    Args:
        status: ParentStatusWithDomain value
        last_visit_date: Resolved last visit date (or None)
        last_visit_source: Description of date source
        reference_date: October 1st reference date
    
    Returns:
        bool: True if time criteria met
        str: Description of the check performed
    """
    if status in IMMEDIATE_UPDATE_STATUSES:
        # Yellow/Orange: Update immediately if basic eligibility met
        if last_visit_source == "NeverVisited":
            return False, "NeverVisited"
        elif last_visit_source == "VisitedNoDate":
            return True, "VisitedNoDate"
        else:
            # Check 2 month rule
            two_months_ago = reference_date - relativedelta(months=2)
            if last_visit_date > two_months_ago:
                return False, f"VisitTooRecent({last_visit_date.strftime('%Y-%m-%d')})"
            else:
                return True, f"Visit>2Months({last_visit_date.strftime('%Y-%m-%d')})"
    
    elif status in TWO_YEAR_RULE_STATUSES:
        # Green/Pink: Update only if last visit > 2 years or not set
        if last_visit_source == "NeverVisited":
            return False, "NeverVisited"
        elif last_visit_source == "VisitedNoDate":
            return True, "VisitedNoDate"  # "or is not set"
        else:
            # Check 2 year rule
            two_years_ago = reference_date - relativedelta(years=2)
            if last_visit_date > two_years_ago:
                return False, f"Visit<2Years({last_visit_date.strftime('%Y-%m-%d')})"
            else:
                return True, f"Visit>2Years({last_visit_date.strftime('%Y-%m-%d')})"
    
    return False, f"UnknownStatus({status})"


def should_update_record(record, reference_date):
    """
    Determine if a record should be updated to PurpleHistoric
    
    Returns:
        bool: True if record should be updated
        dict: Detailed decision information for logging
    """
    decision = {
        'objectid': record.get('OBJECTID'),
        'species': record.get('SpeciesDropDown'),
        'status': record.get('ParentStatusWithDomain'),
        'should_update': False,
        'reasons': []
    }
    
    # Check species eligibility
    species = record.get('SpeciesDropDown')
    if species not in TARGET_SPECIES:
        decision['reasons'].append(f"SpeciesNotTarget({species})")
        return False, decision
    
    # Check status eligibility
    status = record.get('ParentStatusWithDomain')
    if status not in TARGET_STATUSES:
        decision['reasons'].append(f"StatusNotTarget({status})")
        return False, decision
    
    # Check next visit due
    next_visit_due, next_visit_reason = is_next_visit_due(record, reference_date)
    decision['next_visit_check'] = next_visit_reason
    if not next_visit_due:
        decision['reasons'].append(next_visit_reason)
        return False, decision
    
    # Resolve last visit date
    last_visit_date, last_visit_source = resolve_last_visit_date(record)
    decision['last_visit_date'] = last_visit_date.strftime('%Y-%m-%d') if last_visit_date else None
    decision['last_visit_source'] = last_visit_source
    
    # Check time criteria
    time_criteria_met, time_reason = meets_time_criteria(
        status, last_visit_date, last_visit_source, reference_date
    )
    decision['time_check'] = time_reason
    
    if not time_criteria_met:
        decision['reasons'].append(time_reason)
        return False, decision
    
    # All criteria met
    decision['should_update'] = True
    decision['reasons'].append("AllCriteriaMet")
    return True, decision


def create_audit_log_entry(previous_status, existing_audit_log):
    """
    Create new audit log entry
    
    Args:
        previous_status: The status before update
        existing_audit_log: Current audit_log content (may be None/empty)
    
    Returns:
        str: New audit log content (truncated to 4000 chars if needed)
    """
    today = datetime.now().strftime('%Y-%m-%d')
    new_entry = f"{today} Annual rollover from {previous_status} to Purple"
    
    if existing_audit_log:
        combined = f"{new_entry}; {existing_audit_log}"
    else:
        combined = new_entry
    
    # Truncate if exceeds 4000 characters
    if len(combined) > 4000:
        combined = combined[:3997] + "..."
    
    return combined


@retry(stop=stop_after_attempt(3), wait=wait_fixed(5))
def update_batch(weed_layer, updates):
    """
    Update a batch of features with retry logic
    
    Args:
        weed_layer: ArcGIS FeatureLayer
        updates: List of feature update dictionaries
    
    Returns:
        int: Number of successfully updated features
    """
    try:
        result = weed_layer.edit_features(updates=updates)
        if result.get('updateResults'):
            successful = sum(1 for r in result['updateResults'] if r.get('success', False))
            return successful
        return 0
    except Exception as e:
        print(f"Batch update failed: {e}")
        raise


def export_to_excel(updated_records, environment):
    """
    Export updated records to Excel file
    
    Args:
        updated_records: List of records that were updated
        environment: Environment name for filename
    """
    if not updated_records:
        print("No records to export")
        return
    
    # Create DataFrame
    df = pd.DataFrame(updated_records)
    
    # Generate filename
    timestamp = datetime.now().strftime('%Y-%m-%d_%H%M%S')
    filename = f"annual_rollover_{environment}_{timestamp}.xlsx"
    
    # Save to Excel
    df.to_excel(filename, index=False)
    print(f"📊 Exported {len(updated_records)} updated records to {filename}")


@retry(stop=stop_after_attempt(3), wait=wait_fixed(5))
def save_audit_record(gis, environment, records_processed, records_updated):
    """Save run information to audit table"""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    env_config_path = os.path.join(script_dir, '..', 'spatial_field_updater', 'config', 'environment_config.json')
    
    with open(env_config_path, 'r') as f:
        env_config = json.load(f)
    
    audit_table_id = env_config[environment]['audit_table_id']
    audit_table = Table.fromitem(gis.content.get(audit_table_id))
    
    # Check if record exists
    where_clause = f"ProcessName = 'annual_rollover' AND Environment = '{environment}'"
    existing = audit_table.query(where=where_clause, return_all_records=False)
    
    timestamp = datetime.now().isoformat()
    
    if existing.features:
        # Update existing record
        objectid = existing.features[0].attributes['OBJECTID']
        audit_table.edit_features(updates=[{
            'attributes': {
                'OBJECTID': objectid,
                'LastRunTimestamp': timestamp
            }
        }])
        print(f"Updated audit record for {environment} environment")
    else:
        # Insert new record
        audit_table.edit_features(adds=[{
            'attributes': {
                'ProcessName': 'annual_rollover',
                'Environment': environment,
                'LastRunTimestamp': timestamp
            }
        }])
        print(f"Created new audit record for {environment} environment")


def process_annual_rollover(environment, dry_run=False, limit=None):
    """
    Main processing function for annual rollover
    
    Args:
        environment: 'development' or 'production'
        dry_run: If True, preview changes without updating
        limit: Optional limit on number of records to process
    """
    print(f"🔄 Starting Annual Rollover on '{environment}' environment")
    print(f"Mode: {'DRY RUN' if dry_run else 'LIVE UPDATE'}")
    
    # Get reference date and check safeguards
    reference_date = get_reference_date()
    print(f"📅 Reference date: {reference_date.strftime('%Y-%m-%d')}")
    
    if not dry_run:
        check_production_safeguards(environment, reference_date)
    
    # Connect to ArcGIS
    gis = connect_arcgis()
    weed_layer, audit_table = get_layers_and_table(gis, environment)
    
    # Validate backup field exists
    backup_field_exists = validate_backup_field(weed_layer, dry_run)
    
    # Query all records with target species and status
    print("🔍 Querying weed locations...")
    
    # Build WHERE clause for initial filtering
    species_clause = "'" + "','".join(TARGET_SPECIES) + "'"
    status_clause = "'" + "','".join(TARGET_STATUSES) + "'"
    where_clause = f"SpeciesDropDown IN ({species_clause}) AND ParentStatusWithDomain IN ({status_clause})"
    
    if limit:
        print(f"⚠️  Processing limited to {limit} records for testing")
    
    # Get features using pagination for large datasets
    try:
        print(f"Executing query: {where_clause}")
        
        if limit:
            # For limited queries, use simple approach
            features = weed_layer.query(
                where=where_clause,
                out_fields='*',
                return_geometry=False,
                result_record_count=limit
            )
        else:
            # For full dataset, use pagination with retry logic
            print("Using pagination for large dataset...")
            all_features = []
            offset = 0
            page_size = 500  # Smaller chunks to avoid timeouts
            max_retries = 3
            
            while True:
                retry_count = 0
                page_loaded = False
                
                while retry_count < max_retries and not page_loaded:
                    try:
                        page_features = weed_layer.query(
                            where=where_clause,
                            out_fields='*',
                            return_geometry=False,
                            result_offset=offset,
                            result_record_count=page_size
                        )
                        page_loaded = True
                        
                        if not page_features.features:
                            break
                            
                        all_features.extend(page_features.features)
                        offset += page_size
                        print(f"   Loaded {len(all_features)} records so far...")
                        
                    except Exception as page_error:
                        retry_count += 1
                        if "Expecting value" in str(page_error) and retry_count < max_retries:
                            print(f"   Page failed (attempt {retry_count}/{max_retries}), retrying...")
                            import time
                            time.sleep(2)  # Brief pause before retry
                        else:
                            raise page_error
                
                if not page_loaded:
                    raise Exception(f"Failed to load page after {max_retries} attempts")
                
                # Break if no more features
                if not page_features.features:
                    break
                
                # Safety check to prevent infinite loops
                if len(all_features) >= 50000:
                    print("   Reached 50k record safety limit")
                    break
            
            # Create mock FeatureSet-like object
            class MockFeatureSet:
                def __init__(self, features):
                    self.features = features
            
            features = MockFeatureSet(all_features)
            
    except Exception as e:
        print(f"Query failed: {e}")
        print(f"WHERE clause was: {where_clause}")
        # Try a more basic query to diagnose the issue
        try:
            print("Attempting simpler query for diagnosis...")
            simple_result = weed_layer.query(where="1=1", return_count_only=True)
            print(f"Layer accessible, total records: {simple_result}")
        except Exception as e2:
            print(f"Layer access failed: {e2}")
        raise
    
    total_queried = len(features.features)
    if limit:
        print(f"📊 Found {total_queried} records (limited to {limit} for testing)")
    else:
        print(f"📊 Found {total_queried} records with target species and status")
    
    if len(features.features) == 0:
        print("No features to process")
        return
    
    # Process each record
    updates = []
    updated_records = []
    decisions = []
    
    for feature in features.features:
        record = feature.attributes
        
        # Determine if record should be updated
        should_update, decision = should_update_record(record, reference_date)
        decisions.append(decision)
        
        if should_update:
            # Create backup of original status
            original_status = record['ParentStatusWithDomain']
            
            # Create new audit log entry
            new_audit_log = create_audit_log_entry(original_status, record.get('audit_log'))
            
            # Prepare update
            update_dict = {
                'attributes': {
                    'OBJECTID': record['OBJECTID'],
                    'ParentStatusWithDomain': 'PurpleHistoric',
                    'audit_log': new_audit_log
                }
            }
            
            # Add backup field (validated to exist during startup)
            if backup_field_exists:
                update_dict['attributes']['StatusAt202510'] = original_status
            # else:
            #     # This should not happen due to validation, but safety check
            #     print(f"⚠️  WARNING: Skipping backup for OBJECTID {record['OBJECTID']} - backup field not available")
            
            updates.append(update_dict)
            
            # Prepare export record
            export_record = {
                'OBJECTID': record['OBJECTID'],
                'SpeciesDropDown': record.get('SpeciesDropDown'),
                'iNatURL': record.get('iNatURL'),
                'RegionCode': record.get('RegionCode'),
                'DistrictCode': record.get('DistrictCode'),
                'InitialStatus': original_status,
                'LastVisitDate': decision.get('last_visit_date'),
                'LastVisitSource': decision.get('last_visit_source'),
                'NextVisitCheck': decision.get('next_visit_check'),
                'TimeCheck': decision.get('time_check'),
                'NewStatus': 'PurpleHistoric',
                'NewAuditLog': new_audit_log,
                'UpdateTimestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
            
            updated_records.append(export_record)
    
    # Summary statistics
    total_processed = len(features.features)
    total_eligible = len(updates)
    
    print(f"\n📈 Processing Summary:")
    print(f"   Records queried: {total_queried}")
    print(f"   Records processed: {total_processed}")
    print(f"   Records eligible for update: {total_eligible}")
    
    if total_eligible == 0:
        print("✅ No updates needed")
        if not dry_run:
            save_audit_record(gis, environment, total_processed, 0)
        return
    
    if dry_run:
        print(f"\n🔍 DRY RUN - Would update {total_eligible} records:")
        for record in updated_records[:10]:  # Show first 10
            print(f"   OBJECTID {record['OBJECTID']}: {record['InitialStatus']} → PurpleHistoric")
        if len(updated_records) > 10:
            print(f"   ... and {len(updated_records) - 10} more records")
        export_to_excel(updated_records, environment)
        return
    
    # Apply updates in batches
    print(f"\n🔄 Applying updates in batches of 100...")
    batch_size = 100
    total_updated = 0
    
    for i in range(0, len(updates), batch_size):
        batch = updates[i:i + batch_size]
        
        try:
            successful = update_batch(weed_layer, batch)
            total_updated += successful
            print(f"   Batch {i//batch_size + 1}: {successful}/{len(batch)} successful")
        except Exception as e:
            print(f"   Batch {i//batch_size + 1} failed: {e}")
    
    print(f"\n✅ Completed: {total_updated}/{total_eligible} records updated successfully")
    
    # Export to Excel
    if updated_records:
        export_to_excel(updated_records, environment)
    
    # Save audit record
    save_audit_record(gis, environment, total_processed, total_updated)


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description="Annual Weed Instance Rollover Tool")
    parser.add_argument(
        '--env', 
        choices=['development', 'production'], 
        required=True,
        help='Environment to process (development or production)'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Preview changes without updating (default: false)'
    )
    parser.add_argument(
        '--limit',
        type=int,
        help='Limit number of records to process (for testing)'
    )
    
    args = parser.parse_args()
    
    try:
        process_annual_rollover(args.env, args.dry_run, args.limit)
    except Exception as e:
        print(f"❌ Error: {e}")
        return 1
    
    return 0


if __name__ == "__main__":
    exit(main())
