"""WeedLocations where clause shared by every maintenance action."""

from datetime import datetime, timedelta, timezone

from effective_status import NZT, OVERDUE_CODE

# Reason: ArcGIS date literals are UTC. Formatting the last-run instant in UTC
# matches the previous script on the GitHub-hosted runner, which is UTC.


def start_of_tomorrow(today):
  """Midnight at the start of the next NZT calendar day."""
  local = today.astimezone(NZT) if today.tzinfo else today.replace(tzinfo=NZT)
  tomorrow = local.date() + timedelta(days=1)
  return datetime(tomorrow.year, tomorrow.month, tomorrow.day, tzinfo=NZT)


def _utc_literal(value):
  if value.tzinfo is None:
    value = value.astimezone()
  return value.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def build_where(last_run, today, process_all):
  """Edits since last run, plus visits that became due after that run.

  A full scan is 1=1. Historical overdue sites that were not edited, and whose
  next-visit date is on or before the last run, are left for --mode all.
  """
  if process_all or last_run is None:
    return "1=1"

  edited = _utc_literal(last_run)
  due_after = _utc_literal(last_run)
  due_before = _utc_literal(start_of_tomorrow(today))
  edit_clause = f"EditDate_1 > timestamp '{edited}'"
  due_clause = (
    f"DateForNextVisitFromLastVisit > timestamp '{due_after}' "
    f"AND DateForNextVisitFromLastVisit < timestamp '{due_before}' "
    f"AND (ParentStatusWithDomain IS NULL OR ("
    f"ParentStatusWithDomain NOT LIKE 'Red%' "
    f"AND ParentStatusWithDomain NOT LIKE 'Black%' "
    f"AND ParentStatusWithDomain NOT LIKE 'Grey%')) "
    f"AND (EffectiveStatus IS NULL OR EffectiveStatus <> '{OVERDUE_CODE}')"
  )
  return f"({edit_clause}) OR ({due_clause})"
