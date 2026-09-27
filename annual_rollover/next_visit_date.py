"""Next-visit date rules shared with CAMS Easy Editor.

The October calculation matches cams-easy-editor/src/nextVisitDate.js.
Calendar dates are Pacific/Auckland so the 1 August and 1 October cutoffs do not
shift when this runs on a UTC machine.
"""

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

AUCKLAND = ZoneInfo("Pacific/Auckland")

TARGET_SPECIES = [
  "MothPlant",
  "OldMansBeard",
  "CathedralBells",
  "BananaPassionfruit",
  "BluePassionFlower",
  "Jasmine",
  "JapaneseHoneysuckle",
  "BlueMorningGlory",
  "WoollyNightshade",
  "Elaeagnus",
]

STATUS_COLOUR = {
  "YellowKilledThisYear": "yellow",
  "OrangeDeadHeaded": "orange",
  "GreenNoRegrowthThisYear": "green",
  "PinkOccupantWillKillGrowth": "pink",
}

TARGET_STATUSES = list(STATUS_COLOUR.keys())

DATE_FIELDS = (
  ("DateVisitMadeFromLastVisit", "DateVisitMade"),
  ("DateOfLastCreateFromLastVisit", "DateOfLastCreate"),
  ("DateDiscovered", "DateDiscovered"),
)


def as_auckland(value):
  """Return an aware Pacific/Auckland datetime, or None."""
  if value is None or value == "":
    return None
  if isinstance(value, datetime):
    if value.tzinfo is None:
      return value.replace(tzinfo=AUCKLAND)
    return value.astimezone(AUCKLAND)
  if isinstance(value, (int, float)):
    return datetime.fromtimestamp(value / 1000, tz=AUCKLAND)
  return None


def october_first(year):
  return datetime(year, 10, 1, tzinfo=AUCKLAND)


def suggest_next_visit_date(visit_date, status, species, today):
  """1 October for a listed species and yellow, orange, green, or pink status.

  Returns None when no suggestion applies, including when the result would be
  more than five years after today. The result is midnight in Pacific/Auckland
  and is always after today.
  """
  if species not in TARGET_SPECIES:
    return None
  colour = STATUS_COLOUR.get(status)
  if colour not in ("yellow", "orange", "green", "pink"):
    return None

  visit = as_auckland(visit_date)
  now = as_auckland(today)
  if visit is None or now is None:
    return None

  if colour in ("yellow", "orange"):
    suggested_year = visit.year if visit.month < 8 else visit.year + 1
  else:
    before_1_october = visit.month < 10
    suggested_year = visit.year + 1 if before_1_october else visit.year + 2

  suggested = october_first(suggested_year)
  tomorrow = now.date() + timedelta(days=1)
  earliest = datetime(tomorrow.year, tomorrow.month, tomorrow.day, tzinfo=AUCKLAND)
  latest = datetime(now.year + 5, now.month, now.day, tzinfo=AUCKLAND)
  while suggested < earliest:
    suggested = october_first(suggested.year + 1)
  if suggested > latest:
    return None
  return suggested


def resolve_last_visit_date(record):
  """First available visit date: visit made, then created, then discovered."""
  for field_name, source in DATE_FIELDS:
    resolved = as_auckland(record.get(field_name))
    if resolved is not None:
      return resolved, source
  return None, "NoVisitDate"


def stored_epoch(value):
  """Epoch milliseconds already stored, left unchanged when copying."""
  if value is None or value == "":
    return None
  if isinstance(value, (int, float)):
    return int(value)
  resolved = as_auckland(value)
  if resolved is None:
    return None
  return int(resolved.timestamp() * 1000)


def select_latest_visits(visits):
  """Latest visit per GUID_visits.

  DateCheck wins over CreationDate_1. The higher OBJECTID breaks a tie.
  A visit with neither date is ignored.
  """
  grouped = {}
  for visit in visits:
    guid = visit.get("GUID_visits")
    rank = _visit_rank(visit)
    if not guid or rank[0] < 0:
      continue
    current = grouped.get(guid)
    if current is None or rank > _visit_rank(current):
      grouped[guid] = visit
  return grouped


def _visit_rank(visit):
  date_check = stored_epoch(visit.get("DateCheck"))
  created = stored_epoch(visit.get("CreationDate_1"))
  objectid = visit.get("OBJECTID") or 0
  if date_check is not None:
    return (1, date_check, objectid)
  if created is not None:
    return (0, created, objectid)
  return (-1, 0, -1)


def plan_updates(record, latest_visit, today):
  """Decide which next-visit fields to write. A stored date is never replaced.

  When one side is set, that value is copied to the empty side. When both are
  empty, both receive the suggested 1 October. No visit row means only the
  weed field can be set.
  """
  species = record.get("SpeciesDropDown")
  status = record.get("ParentStatusWithDomain")
  last_visit, source = resolve_last_visit_date(record)
  weed_existing = stored_epoch(record.get("DateForNextVisitFromLastVisit"))
  visit_existing = None
  visit_objectid = None
  if latest_visit is not None:
    visit_existing = stored_epoch(latest_visit.get("DateForReturnVisit"))
    visit_objectid = latest_visit.get("OBJECTID")

  decision = {
    "objectid": record.get("OBJECTID"),
    "species": species,
    "status": status,
    "weed_epoch": None,
    "visit_epoch": None,
    "visit_objectid": visit_objectid,
    "suggested": None,
    "weed_action": "left",
    "visit_action": "no_visit" if latest_visit is None else "left",
    "last_visit_date": last_visit,
    "last_visit_source": source,
  }

  if species not in TARGET_SPECIES or status not in STATUS_COLOUR:
    return decision

  weed_set = weed_existing is not None
  visit_set = visit_existing is not None

  if weed_set and (latest_visit is None or visit_set):
    return decision

  if weed_set and latest_visit is not None and not visit_set:
    decision["visit_epoch"] = weed_existing
    decision["visit_action"] = "copied_from_weed"
    return decision

  if not weed_set and visit_set:
    decision["weed_epoch"] = visit_existing
    decision["weed_action"] = "copied_from_visit"
    return decision

  suggested = suggest_next_visit_date(last_visit, status, species, today)
  decision["suggested"] = suggested
  if suggested is None:
    return decision

  suggestion_epoch = int(suggested.timestamp() * 1000)
  decision["weed_epoch"] = suggestion_epoch
  decision["weed_action"] = "set"
  if latest_visit is not None:
    decision["visit_epoch"] = suggestion_epoch
    decision["visit_action"] = "set"
  return decision
