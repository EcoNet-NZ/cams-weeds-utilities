"""Copy the latest visit onto WeedLocations.

The latest visit and the field rules come from the weed visits analyzer.
Audit dates stay out, and a purple parent status is left unchanged.
"""

import math
import os
import sys

import pandas as pd

from effective_status import as_auckland, effective_status
from query import _utc_literal

_DATA_QUALITY = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "data_quality"))
if _DATA_QUALITY not in sys.path:
  sys.path.insert(0, _DATA_QUALITY)

from weed_visits_analyzer import get_active_rules, get_latest_visit_per_location


VISIT_FIELDS = [
  "OBJECTID",
  "GUID_visits",
  "DifficultyChild",
  "WeedVisitStatus",
  "DateCheck",
  "DateForReturnVisit",
  "VisitStage",
  "Area",
  "CreationDate_1",
  "EditDate_1",
]

SYNC_WEED_FIELDS = [
  "OBJECTID",
  "GlobalID",
  "Urgency",
  "ParentStatusWithDomain",
  "DateVisitMadeFromLastVisit",
  "DateForNextVisitFromLastVisit",
  "LatestVisitStage",
  "LatestArea",
  "EffectiveStatus",
]

# Reason: an IN list of global IDs has to stay inside the ArcGIS where-clause limit.
GUID_CHUNK = 100

_STATUS_INPUTS = ("ParentStatusWithDomain", "DateForNextVisitFromLastVisit")


def build_visit_where(last_run, process_all):
  """Visits edited since last run. A full scan, or a missing timestamp, is 1=1."""
  if process_all or last_run is None:
    return "1=1"
  return f"EditDate_1 > timestamp '{_utc_literal(last_run)}'"


def in_clause(field, values):
  """SQL IN list. Single quotes in a value are escaped."""
  quoted = ", ".join("'" + str(value).replace("'", "''") + "'" for value in values)
  return f"{field} IN ({quoted})"


def chunked(values, size=GUID_CHUNK):
  """Yield successive slices of values."""
  for start in range(0, len(values), size):
    yield values[start:start + size]


DATE_FIELDS = {
  "DateVisitMadeFromLastVisit",
  "DateForNextVisitFromLastVisit",
}


def display_value(name, value):
  """Text for a preview cell. Date fields are NZT calendar times, not epoch milliseconds."""
  if _is_missing(value):
    return "null"
  if name in DATE_FIELDS:
    moment = as_auckland(value)
    if moment is not None:
      if (moment.hour, moment.minute, moment.second, moment.microsecond) == (0, 0, 0, 0):
        return moment.strftime("%Y-%m-%d")
      return moment.strftime("%Y-%m-%d %H:%M:%S")
  return str(value)


def format_preview(updates, current_by_id):
  """One line per WeedLocations row, each field as old->new, then the count."""
  lines = []
  for item in updates:
    attributes = item["attributes"]
    current = current_by_id.get(attributes["OBJECTID"], {})
    fields = ", ".join(
      f"{name}={display_value(name, current.get(name))}->{display_value(name, attributes[name])}"
      for name in attributes
      if name != "OBJECTID"
    )
    lines.append(f"OBJECTID {attributes['OBJECTID']}: {fields}")
  lines.append(f"{len(updates)} updates")
  return lines


def _is_missing(value):
  return value is None or (isinstance(value, float) and math.isnan(value))


def _differs(weed_value, visit_value):
  if _is_missing(weed_value) and _is_missing(visit_value):
    return False
  if _is_missing(weed_value) or _is_missing(visit_value):
    return True
  return weed_value != visit_value


def _stored_value(value):
  if _is_missing(value):
    return None
  return value


def _object_id(value):
  if _is_missing(value):
    return None
  return int(value)


def _latest_visits(visits):
  """GUID to the original visit dict chosen by the analyzer's latest-visit rule."""
  if not visits:
    return {}
  frame = pd.DataFrame([{
    "GUID_visits": visit.get("GUID_visits"),
    "Visit_OBJECTID": visit.get("OBJECTID"),
    "DifficultyChild": visit.get("DifficultyChild"),
    "WeedVisitStatus": visit.get("WeedVisitStatus"),
    "DateCheck": visit.get("DateCheck"),
    "DateForReturnVisit": visit.get("DateForReturnVisit"),
    "VisitStage": visit.get("VisitStage"),
    "Area": visit.get("Area"),
    "visit_CreationDate_1": visit.get("CreationDate_1"),
    "visit_EditDate_1": visit.get("EditDate_1"),
    "VisitDataSource": visit.get("VisitDataSource"),
  } for visit in visits])
  latest = get_latest_visit_per_location(frame)
  by_objectid = {}
  for visit in visits:
    object_id = _object_id(visit.get("OBJECTID"))
    if object_id is not None:
      by_objectid[object_id] = visit
  chosen = {}
  for _, row in latest.iterrows():
    object_id = _object_id(row["Visit_OBJECTID"])
    guid = row["GUID_visits"]
    if object_id is None or _is_missing(guid):
      continue
    visit = by_objectid.get(object_id)
    if visit is not None:
      chosen[guid] = visit
  return chosen


def plan_visit_sync(weeds, visits, today):
  """Attribute changes that copy each weed's latest visit. Audit dates are skipped."""
  rules = get_active_rules(ignore_creation_edit_dates=True)
  latest_by_guid = _latest_visits(visits)
  planned = {}
  for weed in weeds:
    object_id = weed.get("OBJECTID")
    if object_id is None:
      raise ValueError("Weed location row is missing OBJECTID")
    visit = latest_by_guid.get(weed.get("GlobalID"))
    if visit is None:
      continue
    changes = {}
    for rule in rules:
      weed_field = rule["weed_field"]
      visit_value = visit.get(rule["visit_field"])
      weed_value = weed.get(weed_field)
      ignore = rule.get("ignore_condition")
      if ignore and ignore(weed_value, visit_value):
        continue
      if not _differs(weed_value, visit_value):
        continue
      changes[weed_field] = _stored_value(visit_value)
    if any(field in changes for field in _STATUS_INPUTS):
      parent = changes.get("ParentStatusWithDomain", weed.get("ParentStatusWithDomain"))
      next_visit = changes.get(
        "DateForNextVisitFromLastVisit",
        weed.get("DateForNextVisitFromLastVisit"),
      )
      calculated = effective_status(parent, next_visit, today)
      if weed.get("EffectiveStatus") != calculated:
        changes["EffectiveStatus"] = calculated
    if changes:
      planned[object_id] = changes
  return planned
