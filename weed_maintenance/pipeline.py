"""WeedLocations maintenance: region, district, effective status, and visit sync."""

import json
import os
from datetime import datetime

from arcgis.features import FeatureLayer, Table
from arcgis.gis import GIS
from tenacity import retry, stop_after_attempt, wait_fixed

from actions.spatial_codes import plan_spatial_updates
from actions.visit_sync import (
  SYNC_WEED_FIELDS,
  VISIT_FIELDS,
  build_visit_where,
  chunked,
  format_preview,
  in_clause,
  plan_visit_sync,
)
from audit import PREVIOUS_PROCESS_NAME, PROCESS_NAME, resolve_audit
from effective_status import NZT, plan_effective_status, require_effective_status_field
from merge import merge_attribute_updates
from query import build_where


def select_actions(actions):
  """Which updates to run, and whether this run may move LastRunTimestamp.

  A status-only or visits-only run leaves the timestamp at the last full run.
  The next full run still finds weeds edited since then.
  """
  if actions == "all":
    return {"status": True, "spatial": True, "visits": True, "save_last_run": True}
  if actions == "status":
    return {"status": True, "spatial": False, "visits": False, "save_last_run": False}
  if actions == "visits":
    return {"status": False, "spatial": False, "visits": True, "save_last_run": False}
  raise ValueError(f"Unknown actions '{actions}'. Choose all, status, or visits.")


def should_persist(preview, save_last_run):
  """Whether this run writes features and moves LastRunTimestamp."""
  if preview:
    return False, False
  return True, save_last_run


OUT_FIELDS = [
  "OBJECTID",
  "GlobalID",
  "RegionCode",
  "DistrictCode",
  "EditDate_1",
  "ParentStatusWithDomain",
  "DateForNextVisitFromLastVisit",
  "EffectiveStatus",
]


def _script_dir():
  return os.path.dirname(os.path.abspath(__file__))


def load_environment(environment):
  """Layer ids for a named environment."""
  path = os.path.join(_script_dir(), "config", "environment_config.json")
  with open(path, "r", encoding="utf-8") as handle:
    config = json.load(handle)
  if environment not in config:
    available = ", ".join(sorted(config))
    raise ValueError(f"Environment '{environment}' not found. Available: {available}")
  return config[environment]


@retry(stop=stop_after_attempt(3), wait=wait_fixed(5))
def connect_arcgis():
  """Connect to ArcGIS using environment variables."""
  username = os.getenv("ARCGIS_USERNAME")
  password = os.getenv("ARCGIS_PASSWORD")
  portal_url = os.getenv("ARCGIS_PORTAL_URL", "https://www.arcgis.com")
  return GIS(portal_url, username, password, verify_cert=True)


def visits_table_from_item(item):
  """Visits_Table on the WeedLocations feature service."""
  tables = list(getattr(item, "tables", None) or [])
  if not tables:
    raise ValueError("No tables found in WeedLocations feature service")
  for table in tables:
    name = table.properties.name
    if "visit" in name.lower():
      print(f"Found Visits_Table: {name}")
      return table
  print(f"Using first table: {tables[0].properties.name}")
  return tables[0]


def get_layers(gis, environment):
  """Weed locations, region and district boundaries, the audit table, and the service item."""
  settings = load_environment(environment)
  weed_item = gis.content.get(settings["weed_locations_layer_id"])
  weed_layer = FeatureLayer.fromitem(weed_item)
  region_layer = FeatureLayer.fromitem(gis.content.get(settings["region_layer_id"]))
  district_layer = FeatureLayer.fromitem(gis.content.get(settings["district_layer_id"]))
  audit_table = Table.fromitem(gis.content.get(settings["audit_table_id"]))
  return weed_layer, region_layer, district_layer, audit_table, weed_item


def _audit_where(process_name, environment):
  return f"ProcessName = '{process_name}' AND Environment = '{environment}'"


def _find_audit_row(audit_table, process_name, environment):
  result = audit_table.query(where=_audit_where(process_name, environment), return_all_records=False)
  if result.features:
    return result.features[0]
  return None


@retry(stop=stop_after_attempt(3), wait=wait_fixed(5))
def ensure_last_run(audit_table, environment):
  """Last run for this environment, copying the spatial updater row once if needed."""
  current = _find_audit_row(audit_table, PROCESS_NAME, environment)
  previous = _find_audit_row(audit_table, PREVIOUS_PROCESS_NAME, environment)
  current_timestamp = current.attributes.get("LastRunTimestamp") if current else None
  previous_timestamp = previous.attributes.get("LastRunTimestamp") if previous else None
  last_run, copy_from_old = resolve_audit(current_timestamp, previous_timestamp)
  if copy_from_old:
    audit_table.edit_features(adds=[{
      "attributes": {
        "ProcessName": PROCESS_NAME,
        "Environment": environment,
        "LastRunTimestamp": previous.attributes["LastRunTimestamp"],
      }
    }])
    print(f"Copied last run timestamp from {PREVIOUS_PROCESS_NAME} for {environment}")
  return last_run


@retry(stop=stop_after_attempt(3), wait=wait_fixed(5))
def save_last_run(audit_table, environment):
  """Record that this environment was checked."""
  existing = _find_audit_row(audit_table, PROCESS_NAME, environment)
  timestamp = datetime.now().isoformat()
  if existing:
    audit_table.edit_features(updates=[{
      "attributes": {
        "OBJECTID": existing.attributes["OBJECTID"],
        "LastRunTimestamp": timestamp,
      }
    }])
    print(f"Updated last run timestamp for {environment} environment")
    return
  audit_table.edit_features(adds=[{
    "attributes": {
      "ProcessName": PROCESS_NAME,
      "Environment": environment,
      "LastRunTimestamp": timestamp,
    }
  }])
  print(f"Created new audit record for {environment} environment")


@retry(stop=stop_after_attempt(3), wait=wait_fixed(5))
def query_weeds(weed_layer, where, return_geometry):
  """Load the weed locations selected by the shared where clause."""
  # Reason: a full query is paged on a thread pool that shares one SSL context.
  # truststore briefly sets that context to CERT_NONE during each handshake, so
  # overlapping requests make urllib3 report a false InsecureRequestWarning.
  # order_by_fields selects ArcGIS's single-thread paging instead.
  return weed_layer.query(
    where=where,
    out_fields=OUT_FIELDS,
    return_geometry=return_geometry,
    order_by_fields="OBJECTID",
  )


@retry(stop=stop_after_attempt(3), wait=wait_fixed(5))
def update_batch(weed_layer, batch):
  """Apply one batch of attribute updates. Returns the number that succeeded."""
  result = weed_layer.edit_features(updates=batch)
  if result and "updateResults" in result:
    return sum(1 for item in result["updateResults"] if item.get("success"))
  return 0


@retry(stop=stop_after_attempt(3), wait=wait_fixed(5))
def query_attributes(layer, where, out_fields):
  """Load attributes. order_by_fields keeps ArcGIS paging on one thread."""
  return layer.query(
    where=where,
    out_fields=out_fields,
    return_geometry=False,
    order_by_fields="OBJECTID",
  )


def _attribute_rows(feature_set):
  return [feature.attributes for feature in feature_set.features]


def _unique(rows, field):
  values = []
  seen = set()
  for row in rows:
    value = row.get(field)
    if value and value not in seen:
      seen.add(value)
      values.append(value)
  return values


def load_visits_for_sync(visits_table, where):
  """Changed visits choose the weeds. The latest visit still comes from every visit for those weeds."""
  print(f"Visit query: {where}")
  if where == "1=1":
    rows = _attribute_rows(query_attributes(visits_table, where, VISIT_FIELDS))
    print(f"Loaded {len(rows)} visits")
    return rows

  changed = _attribute_rows(query_attributes(visits_table, where, ["OBJECTID", "GUID_visits"]))
  guids = _unique(changed, "GUID_visits")
  print(f"Visits edited since last run: {len(changed)} ({len(guids)} weeds)")
  rows = []
  for chunk in chunked(guids):
    rows.extend(_attribute_rows(query_attributes(
      visits_table,
      in_clause("GUID_visits", chunk),
      VISIT_FIELDS,
    )))
  print(f"Loaded {len(rows)} visits for those weeds")
  return rows


def load_sync_weeds(weed_layer, visits, process_all):
  """Weed rows the visit sync compares. A full scan reads every weed."""
  if process_all:
    rows = _attribute_rows(query_attributes(weed_layer, "1=1", SYNC_WEED_FIELDS))
    print(f"Loaded {len(rows)} weed locations for visit sync")
    return rows
  guids = _unique(visits, "GUID_visits")
  rows = []
  for chunk in chunked(guids):
    rows.extend(_attribute_rows(query_attributes(
      weed_layer,
      in_clause("GlobalID", chunk),
      SYNC_WEED_FIELDS,
    )))
  print(f"Loaded {len(rows)} weed locations for visit sync")
  return rows


def apply_updates(weed_layer, updates):
  """Write merged attribute updates in batches of 100."""
  if not updates:
    print("Applied 0 updates")
    return 0

  total_updated = 0
  batch_size = 100
  for start in range(0, len(updates), batch_size):
    batch = updates[start:start + batch_size]
    try:
      successful = update_batch(weed_layer, batch)
      total_updated += successful
      print(f"Updated batch {start // batch_size + 1}: {successful}/{len(batch)} successful")
    except Exception as error:
      print(f"Batch update failed after retries: {error}")
  print(f"Applied {total_updated} updates")
  return total_updated


def run(environment, process_all=False, actions="all", preview=False):
  """Plan the selected actions and write the merged result, unless this is a preview."""
  selected = select_actions(actions)
  write, save_timestamp = should_persist(preview, selected["save_last_run"])
  scope = "all features" if process_all else "changed features only"
  print(f"Starting weed maintenance on '{environment}' ({scope}, actions: {actions})...")

  gis = connect_arcgis()
  weed_layer, region_layer, district_layer, audit_table, weed_item = get_layers(gis, environment)
  field_names = {field["name"] for field in weed_layer.properties.fields}
  require_effective_status_field(field_names)

  last_run = ensure_last_run(audit_table, environment)
  today = datetime.now(NZT)
  where = build_where(last_run, today, process_all)
  print(f"Today (NZT): {today.strftime('%Y-%m-%d')}")
  print(f"Query: {where}")

  if selected["status"] or selected["spatial"]:
    print("Loading weed locations...")
    feature_set = query_weeds(weed_layer, where, return_geometry=selected["spatial"])
    count = len(feature_set.features)
    print(f"Processing {count} weed locations...")
    rows = [feature.attributes for feature in feature_set.features]
  else:
    feature_set = None
    rows = []

  if selected["status"]:
    status_plan = plan_effective_status(rows, today)
  else:
    status_plan = {}
  print(f"Effective status updates: {len(status_plan)}")
  if selected["spatial"]:
    spatial_plan = plan_spatial_updates(feature_set, region_layer, district_layer)
  else:
    spatial_plan = {}
    print("Skipping region and district updates")
  print(f"Spatial updates: {len(spatial_plan)}")

  if selected["visits"]:
    visits_table = visits_table_from_item(weed_item)
    visit_rows = load_visits_for_sync(visits_table, build_visit_where(last_run, process_all))
    sync_weeds = load_sync_weeds(weed_layer, visit_rows, process_all)
    visit_plan = plan_visit_sync(sync_weeds, visit_rows, today)
  else:
    sync_weeds = []
    visit_plan = {}
    print("Skipping visit sync")
  print(f"Visit sync updates: {len(visit_plan)}")

  updates = merge_attribute_updates(spatial_plan, status_plan, visit_plan)
  if not write:
    current_by_id = {}
    for row in list(rows) + list(sync_weeds):
      object_id = row.get("OBJECTID")
      if object_id is not None:
        current_by_id.setdefault(object_id, {}).update(row)
    for line in format_preview(updates, current_by_id):
      print(line)
    print("Preview only. Left LastRunTimestamp unchanged")
    return
  apply_updates(weed_layer, updates)
  if save_timestamp:
    save_last_run(audit_table, environment)
  else:
    print("Left LastRunTimestamp unchanged")
