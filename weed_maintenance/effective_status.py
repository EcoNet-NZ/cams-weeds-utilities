"""Effective status for a weed location.

Calendar dates use NZT (Pacific/Auckland). Epoch values are milliseconds, matching
annual_rollover/next_visit_date.py, so a UTC runner still uses the New Zealand day.
"""

from datetime import datetime
from zoneinfo import ZoneInfo

NZT = ZoneInfo("Pacific/Auckland")
OVERDUE_CODE = "PurpleHistoric"
EXCLUDED_PREFIXES = ("Red", "Black", "Grey")
STATUS_FIELD = "EffectiveStatus"


def as_auckland(value):
  """Return an aware NZT datetime, or None when the value is unset."""
  if value is None or value == "":
    return None
  if isinstance(value, datetime):
    if value.tzinfo is None:
      return value.replace(tzinfo=NZT)
    return value.astimezone(NZT)
  if isinstance(value, (int, float)):
    return datetime.fromtimestamp(value / 1000, tz=NZT)
  return None


def effective_status(parent_status, next_visit, today):
  """Parent status, or PurpleHistoric when the next visit is due and not closed."""
  visit = as_auckland(next_visit)
  current_day = as_auckland(today)
  overdue = visit is not None and current_day is not None and visit.date() <= current_day.date()
  excluded = isinstance(parent_status, str) and parent_status.startswith(EXCLUDED_PREFIXES)
  if overdue and not excluded:
    return OVERDUE_CODE
  return parent_status


def plan_effective_status(rows, today):
  """Attribute changes for rows whose stored effective status differs."""
  planned = {}
  for row in rows:
    if row.get("OBJECTID") is None:
      raise ValueError("Weed location row is missing OBJECTID")
    calculated = effective_status(
      row.get("ParentStatusWithDomain"),
      row.get("DateForNextVisitFromLastVisit"),
      today,
    )
    if row.get(STATUS_FIELD) == calculated:
      continue
    planned[row["OBJECTID"]] = {STATUS_FIELD: calculated}
  return planned


def require_effective_status_field(field_names):
  """Stop before writing when the layer has no EffectiveStatus field."""
  if STATUS_FIELD not in field_names:
    raise RuntimeError(
      "WeedLocations is missing EffectiveStatus. "
      "Add the field in ArcGIS before running weed maintenance."
    )
