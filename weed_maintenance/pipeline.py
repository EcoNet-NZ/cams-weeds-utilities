"""One WeedLocations read, every maintenance action, one write."""

import json
import os
from datetime import datetime

from arcgis.features import FeatureLayer, Table
from arcgis.gis import GIS
from tenacity import retry, stop_after_attempt, wait_fixed

from actions.spatial_codes import plan_spatial_updates
from audit import PREVIOUS_PROCESS_NAME, PROCESS_NAME, resolve_audit
from effective_status import NZT, plan_effective_status, require_effective_status_field
from merge import merge_attribute_updates
from query import build_where


def select_actions(actions):
  """Which updates to run, and whether this run may move LastRunTimestamp.

  A status-only run leaves the timestamp at the last spatial run. The next
  full run still finds weeds edited since then.
  """
  if actions == "all":
    return {"status": True, "spatial": True, "save_last_run": True}
  if actions == "status":
    return {"status": True, "spatial": False, "save_last_run": False}
  raise ValueError(f"Unknown actions '{actions}'. Choose all or status.")


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


def get_layers(gis, environment):
  """Weed locations, region and district boundaries, and the process audit table."""
  settings = load_environment(environment)
  weed_layer = FeatureLayer.fromitem(gis.content.get(settings["weed_locations_layer_id"]))
  region_layer = FeatureLayer.fromitem(gis.content.get(settings["region_layer_id"]))
  district_layer = FeatureLayer.fromitem(gis.content.get(settings["district_layer_id"]))
  audit_table = Table.fromitem(gis.content.get(settings["audit_table_id"]))
  return weed_layer, region_layer, district_layer, audit_table


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


def run(environment, process_all=False, actions="all"):
  """Query WeedLocations once, plan the selected actions, and write the merged result."""
  selected = select_actions(actions)
  scope = "all features" if process_all else "changed features only"
  print(f"Starting weed maintenance on '{environment}' ({scope}, actions: {actions})...")

  gis = connect_arcgis()
  weed_layer, region_layer, district_layer, audit_table = get_layers(gis, environment)
  field_names = {field["name"] for field in weed_layer.properties.fields}
  require_effective_status_field(field_names)

  last_run = ensure_last_run(audit_table, environment)
  today = datetime.now(NZT)
  where = build_where(last_run, today, process_all)
  print(f"Today (NZT): {today.strftime('%Y-%m-%d')}")
  print(f"Query: {where}")

  print("Loading weed locations...")
  feature_set = query_weeds(weed_layer, where, return_geometry=selected["spatial"])
  count = len(feature_set.features)
  print(f"Processing {count} weed locations...")

  rows = [feature.attributes for feature in feature_set.features]
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

  updates = merge_attribute_updates(spatial_plan, status_plan)
  apply_updates(weed_layer, updates)
  if selected["save_last_run"]:
    save_last_run(audit_table, environment)
  else:
    print("Left LastRunTimestamp unchanged")
