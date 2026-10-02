"""Last-run timestamp for weed maintenance.

A missing weed_maintenance row copies the spatial_field_updater timestamp so
the first renamed run does not scan every feature. The old row is left in place.
"""

from datetime import datetime

from effective_status import as_auckland

PROCESS_NAME = "weed_maintenance"
PREVIOUS_PROCESS_NAME = "spatial_field_updater"


def resolve_audit(current_timestamp, previous_timestamp):
  """Return (last_run, copy_from_previous).

  last_run is an aware NZT datetime, or None when neither row exists.
  copy_from_previous is true when the caller should insert a weed_maintenance row.
  """
  if current_timestamp is not None and current_timestamp != "":
    return as_auckland(current_timestamp), False
  if previous_timestamp is not None and previous_timestamp != "":
    return as_auckland(previous_timestamp), True
  return None, False
