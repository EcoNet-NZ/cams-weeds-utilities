#!/usr/bin/env python3
"""Fill a missing next-visit date on weed instances and their latest visit.

Does not change ParentStatusWithDomain. A date that is already set is left
as it is. Run once on development, then production. Later visits take their
date from CAMS Easy Editor.
"""

import argparse
import json
import os
import time
from datetime import datetime

import pandas as pd
from arcgis.features import FeatureLayer
from arcgis.gis import GIS
from tenacity import retry, stop_after_attempt, wait_fixed

from next_visit_date import (
  AUCKLAND,
  TARGET_SPECIES,
  TARGET_STATUSES,
  as_auckland,
  plan_updates,
  select_latest_visits,
)

WEED_FIELDS = [
  "OBJECTID",
  "GlobalID",
  "SpeciesDropDown",
  "ParentStatusWithDomain",
  "DateForNextVisitFromLastVisit",
  "DateVisitMadeFromLastVisit",
  "DateOfLastCreateFromLastVisit",
  "DateDiscovered",
  "iNatURL",
  "RegionCode",
  "DistrictCode",
]

VISIT_FIELDS = [
  "OBJECTID",
  "GUID_visits",
  "DateCheck",
  "DateForReturnVisit",
  "CreationDate_1",
]

GUID_BATCH = 40
EDIT_BATCH = 100


@retry(stop=stop_after_attempt(3), wait=wait_fixed(5))
def connect_arcgis():
  """Connect to ArcGIS using environment variables."""
  username = os.getenv("ARCGIS_USERNAME")
  password = os.getenv("ARCGIS_PASSWORD")
  portal_url = os.getenv("ARCGIS_PORTAL_URL", "https://www.arcgis.com")
  print(f"Connecting to ArcGIS Online with username: {username} and portal_url: {portal_url}")
  return GIS(portal_url, username, password)


def environment_settings(environment):
  script_dir = os.path.dirname(os.path.abspath(__file__))
  env_config_path = os.path.join(script_dir, "..", "spatial_field_updater", "config", "environment_config.json")
  with open(env_config_path, "r", encoding="utf-8") as handle:
    env_config = json.load(handle)
  if environment not in env_config:
    available = ", ".join(sorted(env_config))
    raise ValueError(f"Environment '{environment}' not found. Available: {available}")
  return env_config[environment]


def get_weed_layer_and_visits(gis, environment):
  """WeedLocations layer and the Visits table on the same feature service."""
  weed_layer_id = environment_settings(environment)["weed_locations_layer_id"]
  weed_item = gis.content.get(weed_layer_id)
  if not weed_item:
    raise ValueError(f"Could not find WeedLocations layer with ID: {weed_layer_id}")

  weed_layer = FeatureLayer.fromitem(weed_item)
  tables = list(getattr(weed_item, "tables", []) or [])
  if not tables:
    raise ValueError(f"No tables found in WeedLocations feature service: {weed_layer_id}")

  visits_table = None
  for table in tables:
    if "visit" in table.properties.name.lower():
      visits_table = table
      break
  if visits_table is None:
    visits_table = tables[0]
  print(f"Visits table: {visits_table.properties.name}")
  return weed_layer, visits_table


def check_production_safeguards(environment, today):
  """Block a live production run before 1 October of the current year."""
  if environment != "production":
    print(f"Safeguard check passed for {environment} environment")
    return
  gate = datetime(today.year, 10, 1, tzinfo=AUCKLAND)
  if today < gate:
    days_until = (gate.date() - today.date()).days
    raise ValueError(
      "Production updates not allowed before October 1st. "
      f"Current date: {today.strftime('%Y-%m-%d')}, "
      f"Reference date: {gate.strftime('%Y-%m-%d')} "
      f"({days_until} days remaining)"
    )
  print(f"Safeguard check passed for {environment} environment")


def query_all(layer, where, fields, limit=None):
  """Page through a layer. Shrink the page and retry when the service rejects a request."""
  out_fields = ",".join(fields)
  if limit:
    result = layer.query(
      where=where,
      out_fields=out_fields,
      return_geometry=False,
      result_record_count=limit,
    )
    return list(result.features)

  features = []
  offset = 0
  page_size = 200
  while True:
    loaded = False
    current_page_size = page_size
    for attempt in range(1, 6):
      try:
        page = layer.query(
          where=where,
          out_fields=out_fields,
          return_geometry=False,
          result_offset=offset,
          result_record_count=current_page_size,
        )
        loaded = True
        break
      except Exception as error:
        if attempt == 5:
          print(f"   Failed after 5 attempts at offset {offset}: {error}")
          return features
        current_page_size = max(50, current_page_size // 2)
        print(f"   Page failed (attempt {attempt}/5), retrying with {current_page_size} records...")
        time.sleep(attempt * 2)
    if not loaded or not page.features:
      break
    features.extend(page.features)
    offset += len(page.features)
    if len(page.features) < current_page_size or len(features) >= 50000:
      if len(features) >= 50000:
        print("   Reached 50k record safety limit")
      break
  return features


def quoted_guid(guid):
  return "'" + str(guid).replace("'", "''") + "'"


def query_visits(visits_table, guids):
  """Load visits for the candidate weeds, in batches so the where clause stays short."""
  unique = list(dict.fromkeys(guid for guid in guids if guid))
  attributes = []
  for start in range(0, len(unique), GUID_BATCH):
    batch = unique[start:start + GUID_BATCH]
    where = "GUID_visits IN (" + ",".join(quoted_guid(guid) for guid in batch) + ")"
    for feature in query_all(visits_table, where, VISIT_FIELDS):
      attributes.append(feature.attributes)
    if start and start % (GUID_BATCH * 10) == 0:
      print(f"   Loaded visits for {start} weed instances...")
  return attributes


def guid_key(value):
  if not value:
    return None
  return str(value).replace("{", "").replace("}", "").strip().upper()


def date_text(value):
  resolved = as_auckland(value)
  if resolved is None:
    return None
  return resolved.strftime("%Y-%m-%d")


def export_row(record, decision, latest_visit):
  existing_visit = None if latest_visit is None else latest_visit.get("DateForReturnVisit")
  return {
    "OBJECTID": record.get("OBJECTID"),
    "VisitObjectID": decision["visit_objectid"],
    "SpeciesDropDown": decision["species"],
    "ParentStatusWithDomain": decision["status"],
    "iNatURL": record.get("iNatURL"),
    "RegionCode": record.get("RegionCode"),
    "DistrictCode": record.get("DistrictCode"),
    "LastVisitDate": date_text(decision["last_visit_date"]),
    "LastVisitSource": decision["last_visit_source"],
    "ExistingWeedNextVisit": date_text(record.get("DateForNextVisitFromLastVisit")),
    "ExistingVisitNextVisit": date_text(existing_visit),
    "SuggestedDate": date_text(decision["suggested"]),
    "WeedAction": decision["weed_action"],
    "VisitAction": decision["visit_action"],
    "WrittenWeedDate": date_text(decision["weed_epoch"]),
    "WrittenVisitDate": date_text(decision["visit_epoch"]),
    "UpdateTimestamp": datetime.now(AUCKLAND).strftime("%Y-%m-%d %H:%M:%S"),
  }


def export_to_excel(rows, environment):
  if not rows:
    print("No records to export")
    return None
  timestamp = datetime.now(AUCKLAND).strftime("%Y-%m-%d_%H%M%S")
  filename = f"annual_rollover_{environment}_{timestamp}.xlsx"
  pd.DataFrame(rows).to_excel(filename, index=False)
  print(f"Exported {len(rows)} records to {filename}")
  return filename


@retry(stop=stop_after_attempt(3), wait=wait_fixed(5))
def update_batch(layer, updates):
  result = layer.edit_features(updates=updates)
  results = result.get("updateResults") if isinstance(result, dict) else None
  if not results:
    return 0
  return sum(1 for item in results if item.get("success", False))


def apply_updates(layer, updates, label):
  if not updates:
    return 0
  print(f"Applying {len(updates)} {label} updates in batches of {EDIT_BATCH}...")
  updated = 0
  for start in range(0, len(updates), EDIT_BATCH):
    batch = updates[start:start + EDIT_BATCH]
    try:
      successful = update_batch(layer, batch)
      updated += successful
      print(f"   {label} batch {start // EDIT_BATCH + 1}: {successful}/{len(batch)} successful")
    except Exception as error:
      print(f"   {label} batch {start // EDIT_BATCH + 1} failed: {error}")
  return updated


@retry(stop=stop_after_attempt(3), wait=wait_fixed(5))
def save_audit_record(gis, environment, records_processed, records_updated):
  audit_table_id = environment_settings(environment)["audit_table_id"]
  audit_table = gis.content.get(audit_table_id)
  from arcgis.features import Table
  table = Table.fromitem(audit_table)
  where = f"ProcessName = 'annual_rollover' AND Environment = '{environment}'"
  existing = table.query(where=where, return_all_records=False)
  timestamp = datetime.now(AUCKLAND).isoformat()
  if existing.features:
    objectid = existing.features[0].attributes["OBJECTID"]
    table.edit_features(updates=[{"attributes": {"OBJECTID": objectid, "LastRunTimestamp": timestamp}}])
    print(f"Updated audit record for {environment} environment")
  else:
    table.edit_features(adds=[{
      "attributes": {
        "ProcessName": "annual_rollover",
        "Environment": environment,
        "LastRunTimestamp": timestamp,
      }
    }])
    print(f"Created new audit record for {environment} environment")
  print(f"Processed {records_processed}, updated {records_updated}")


def candidate_where():
  species = "'" + "','".join(TARGET_SPECIES) + "'"
  statuses = "'" + "','".join(TARGET_STATUSES) + "'"
  return f"SpeciesDropDown IN ({species}) AND ParentStatusWithDomain IN ({statuses})"


def build_updates(records, latest_by_guid, today):
  """Return export rows plus weed and visit edit payloads."""
  rows = []
  weed_updates = []
  visit_updates = []
  skipped_set = 0
  skipped_no_date = 0

  for record in records:
    key = guid_key(record.get("GlobalID"))
    latest_visit = latest_by_guid.get(key) if key else None
    decision = plan_updates(record, latest_visit, today)
    will_write = decision["weed_epoch"] is not None or decision["visit_epoch"] is not None
    if not will_write:
      weed_has_date = record.get("DateForNextVisitFromLastVisit") is not None
      visit_has_date = latest_visit is not None and latest_visit.get("DateForReturnVisit") is not None
      if weed_has_date or visit_has_date:
        skipped_set += 1
      else:
        skipped_no_date += 1
      continue

    rows.append(export_row(record, decision, latest_visit))
    if decision["weed_epoch"] is not None:
      weed_updates.append({
        "attributes": {
          "OBJECTID": record["OBJECTID"],
          "DateForNextVisitFromLastVisit": decision["weed_epoch"],
        }
      })
    if decision["visit_epoch"] is not None:
      visit_updates.append({
        "attributes": {
          "OBJECTID": decision["visit_objectid"],
          "DateForReturnVisit": decision["visit_epoch"],
        }
      })

  return rows, weed_updates, visit_updates, skipped_set, skipped_no_date


def index_latest_visits(visits):
  latest = select_latest_visits(visits)
  return {guid_key(guid): visit for guid, visit in latest.items()}


def process_annual_rollover(environment, dry_run=False, limit=None):
  """Fill missing next-visit dates. Status, audit_log, and backup fields are not written."""
  today = datetime.now(AUCKLAND)
  print(f"Starting next-visit date rollover on '{environment}'")
  print(f"Mode: {'DRY RUN' if dry_run else 'LIVE UPDATE'}")
  print(f"Today (Pacific/Auckland): {today.strftime('%Y-%m-%d')}")

  if not dry_run:
    check_production_safeguards(environment, today)

  gis = connect_arcgis()
  weed_layer, visits_table = get_weed_layer_and_visits(gis, environment)

  where = candidate_where()
  if limit:
    print(f"Processing limited to {limit} records for testing")
  print(f"Querying weed locations: {where}")
  weed_features = query_all(weed_layer, where, WEED_FIELDS, limit=limit)
  records = [feature.attributes for feature in weed_features]
  print(f"Found {len(records)} records with target species and status")
  if not records:
    print("No features to process")
    return

  print("Loading latest visits...")
  visit_attributes = query_visits(visits_table, [record.get("GlobalID") for record in records])
  print(f"Loaded {len(visit_attributes)} visit rows")
  latest_by_guid = index_latest_visits(visit_attributes)

  rows, weed_updates, visit_updates, skipped_set, skipped_no_date = build_updates(
    records, latest_by_guid, today
  )
  print("\nProcessing summary:")
  print(f"   Records queried: {len(records)}")
  print(f"   Weed dates to write: {len(weed_updates)}")
  print(f"   Visit dates to write: {len(visit_updates)}")
  print(f"   Left unchanged (date already set): {skipped_set}")
  print(f"   Left unchanged (no date suggested): {skipped_no_date}")

  if not rows:
    print("No updates needed")
    if not dry_run:
      save_audit_record(gis, environment, len(records), 0)
    return

  if dry_run:
    print(f"\nDRY RUN - would update {len(rows)} records:")
    for row in rows[:10]:
      print(
        f"   OBJECTID {row['OBJECTID']}: weed {row['WeedAction']} {row['WrittenWeedDate']}, "
        f"visit {row['VisitAction']} {row['WrittenVisitDate']}"
      )
    if len(rows) > 10:
      print(f"   ... and {len(rows) - 10} more records")
    export_to_excel(rows, environment)
    return

  # Visit first, so a child-to-parent webhook copies the same date onto the weed.
  visits_updated = apply_updates(visits_table, visit_updates, "visit")
  weeds_updated = apply_updates(weed_layer, weed_updates, "weed")
  print(f"\nCompleted: {weeds_updated} weed dates and {visits_updated} visit dates")
  export_to_excel(rows, environment)
  save_audit_record(gis, environment, len(records), len(rows))


def main():
  parser = argparse.ArgumentParser(description="Fill missing next-visit dates on weed instances")
  parser.add_argument("--env", choices=["development", "production"], required=True)
  parser.add_argument("--dry-run", action="store_true", help="Preview changes without updating")
  parser.add_argument("--limit", type=int, help="Limit number of weed records to process")
  args = parser.parse_args()
  try:
    process_annual_rollover(args.env, args.dry_run, args.limit)
  except Exception as error:
    print(f"Error: {error}")
    return 1
  return 0


if __name__ == "__main__":
  raise SystemExit(main())
