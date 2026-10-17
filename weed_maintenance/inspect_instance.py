#!/usr/bin/env python3
"""Show how CAMS Weed Maintenance would treat one weed instance.

Reads the instance from ArcGIS: the configured feature layer, or a portal
item that is a feature layer or a file geodatabase backup. The script only reads.
"""

import argparse
import os
import sys
import tempfile
import zipfile
from datetime import datetime, timezone

from arcgis.features import FeatureLayer, Table

from audit import PROCESS_NAME
from actions.visit_sync import plan_visit_sync
from effective_status import EXCLUDED_PREFIXES, NZT, OVERDUE_CODE, as_auckland, plan_effective_status
from pipeline import connect_arcgis, load_environment
from query import start_of_tomorrow

_DATA_QUALITY = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data_quality"))
if _DATA_QUALITY not in sys.path:
  sys.path.insert(0, _DATA_QUALITY)

WEED_FIELDS = [
  "OBJECTID",
  "GlobalID",
  "SpeciesDropDown",
  "LocationInfo",
  "Urgency",
  "ParentStatusWithDomain",
  "EffectiveStatus",
  "DateVisitMadeFromLastVisit",
  "DateForNextVisitFromLastVisit",
  "LatestVisitStage",
  "LatestArea",
  "RegionCode",
  "DistrictCode",
  "CreationDate_1",
  "Creator_1",
  "EditDate_1",
  "Editor_1",
  "last_user_edit",
  "last_user_edit_date",
]

VISIT_FIELDS = [
  "OBJECTID",
  "GUID_visits",
  "WeedVisitStatus",
  "DifficultyChild",
  "DateCheck",
  "DateForReturnVisit",
  "VisitStage",
  "Area",
  "VisitDataSource",
  "CreationDate_1",
  "Creator_1",
  "EditDate_1",
  "Editor_1",
]

STATUS_FIELDS = ("ParentStatusWithDomain", "EffectiveStatus", "WeedVisitStatus")
DATE_FIELDS = {
  "DateVisitMadeFromLastVisit",
  "DateForNextVisitFromLastVisit",
  "CreationDate_1",
  "EditDate_1",
  "DateCheck",
  "DateForReturnVisit",
  "last_user_edit_date",
}


def source_kind(item_type):
  """Feature layers are queried in place. A file geodatabase item is downloaded."""
  if item_type in ("Feature Service", "Feature Layer"):
    return "feature"
  if item_type == "File Geodatabase":
    return "fgdb"
  raise ValueError(
    f"Unsupported ArcGIS item type '{item_type}'. Use a feature layer or a file geodatabase."
  )


def feature_source(label, title, item_id, layer_name):
  """One line naming the feature layer that was read."""
  return f"ArcGIS feature layer '{layer_name}' ({label}: {title}, {item_id})"


def fgdb_source(title, item_id):
  """One line naming a file geodatabase item. Its dates are UTC instants."""
  return (
    f"ArcGIS file geodatabase '{title}' ({item_id}). "
    "Dates are stored in UTC and shown in NZT."
  )


def guid_forms(value):
  """Braced and bare GUID spellings used by ArcGIS relationship fields."""
  text = str(value).strip()
  bare = text.strip("{}")
  forms = []
  for form in (text, "{" + bare + "}", bare):
    if form and form not in forms:
      forms.append(form)
  return forms


def _compact(name):
  return "".join(character for character in name.lower() if character.isalnum())


def _is_weed_layer(name):
  compact = _compact(name)
  return "weedlocation" in compact and "attach" not in compact


def _is_visit_layer(name):
  compact = _compact(name)
  return "visit" in compact and "attach" not in compact


def _pick_layer(names, explicit, predicate, label, flag):
  if explicit:
    if explicit not in names:
      available = ", ".join(names) or "none"
      raise ValueError(f"{label} '{explicit}' was not found. Available: {available}")
    return explicit
  matches = [name for name in names if predicate(name)]
  if len(matches) != 1:
    available = ", ".join(names) or "none"
    found = ", ".join(matches) or "none"
    raise ValueError(
      f"Expected one {label}, found {len(matches)} ({found}). Pass {flag}. Available: {available}"
    )
  return matches[0]


def choose_gdb_layers(layers, weed_name, visits_name):
  """Return the weed feature class and visits table inside a file geodatabase."""
  names = [name for name, _geometry in layers]
  weed = _pick_layer(names, weed_name, _is_weed_layer, "weed locations layer", "--weed-layer")
  remaining = [name for name in names if name != weed]
  visits = _pick_layer(remaining, visits_name, _is_visit_layer, "visits table", "--visits-layer")
  return weed, visits


def is_missing(value):
  """True for None, NaN, and NaT. Empty text is a stored value."""
  if value is None:
    return True
  if isinstance(value, str):
    return False
  try:
    import pandas as pd
    missing = pd.isna(value)
  except (TypeError, ValueError):
    return False
  return bool(missing)


def from_gdb_value(value):
  """Convert one file-geodatabase cell. Naive datetimes are UTC.

  Reason: an Esri date field stores a UTC instant and the file has no timezone.
  """
  if is_missing(value):
    return None
  if isinstance(value, datetime):
    if value.tzinfo is None:
      return value.replace(tzinfo=timezone.utc)
    return value
  return value


def format_moment(value):
  """NZT clock time for an epoch millisecond value or a datetime."""
  if is_missing(value):
    return "(null)"
  moment = as_auckland(value)
  if moment is None:
    return str(value)
  return moment.strftime("%Y-%m-%d %H:%M:%S %Z")


def show(value, field=None):
  """Text for a report cell. Only known date fields are formatted as NZT."""
  if is_missing(value):
    return "(null)"
  if field in DATE_FIELDS:
    return format_moment(value)
  return str(value)


def show_coded(value, names):
  """Stored status, with the domain display name when it differs."""
  if is_missing(value):
    return "(null)"
  text = str(value)
  label = (names or {}).get(value)
  if label and label != text:
    return f"{text} ({label})"
  return text


def _scrub(record):
  return {key: None if is_missing(value) else value for key, value in record.items()}


def changed_mode_selection(weed, last_run, today, process_all):
  """Whether the scheduled weed query would read this row."""
  if process_all:
    return {"included": True, "reason": "Mode all reads every weed."}
  if last_run is None:
    return {"included": True, "reason": "No last run, so every weed is read."}

  edited = as_auckland(weed.get("EditDate_1"))
  last = as_auckland(last_run)
  edit_match = edited is not None and last is not None and edited > last
  next_visit = as_auckland(weed.get("DateForNextVisitFromLastVisit"))
  parent = weed.get("ParentStatusWithDomain")
  open_parent = not (isinstance(parent, str) and parent.startswith(EXCLUDED_PREFIXES))
  due = (
    next_visit is not None
    and last is not None
    and next_visit > last
    and next_visit < start_of_tomorrow(today)
    and open_parent
    and weed.get("EffectiveStatus") != OVERDUE_CODE
  )
  if edit_match:
    return {"included": True, "reason": f"Weed edited {format_moment(edited)}, after the last run."}
  if due:
    return {"included": True, "reason": "Next visit became due after the last run."}
  return {
    "included": False,
    "reason": f"Weed edited {format_moment(edited)}, before the last run. Next visit is not newly due.",
  }


def visit_sync_selected(visits, last_run, process_all):
  """Changed mode follows visits edited after the last run."""
  if process_all or last_run is None:
    return True
  last = as_auckland(last_run)
  for visit in visits:
    edited = as_auckland(visit.get("EditDate_1"))
    if edited is not None and last is not None and edited > last:
      return True
  return False


def _aligned_visits(weed, visits):
  """Visits for this weed, keyed the way plan_visit_sync looks them up."""
  global_id = weed.get("GlobalID")
  if not global_id:
    return visits
  aligned = []
  for visit in visits:
    copy = dict(visit)
    copy["GUID_visits"] = global_id
    aligned.append(copy)
  return aligned


def planned_visit_changes(weed, visits, today):
  """Field changes visit sync would copy from the latest visit."""
  if not visits:
    return {}
  planned = plan_visit_sync([weed], _aligned_visits(weed, visits), today)
  return planned.get(weed["OBJECTID"], {})


def latest_visit(visits):
  """The visit the analyzer treats as latest: DateCheck, then CreationDate_1."""
  if not visits:
    return None
  import pandas as pd
  from weed_visits_analyzer import get_latest_visit_per_location

  frame = pd.DataFrame([{
    "GUID_visits": visit.get("GUID_visits"),
    "Visit_OBJECTID": visit.get("OBJECTID"),
    "DateCheck": visit.get("DateCheck"),
    "visit_CreationDate_1": visit.get("CreationDate_1"),
    "DifficultyChild": visit.get("DifficultyChild"),
    "WeedVisitStatus": visit.get("WeedVisitStatus"),
    "DateForReturnVisit": visit.get("DateForReturnVisit"),
    "VisitStage": visit.get("VisitStage"),
    "Area": visit.get("Area"),
    "visit_EditDate_1": visit.get("EditDate_1"),
    "VisitDataSource": visit.get("VisitDataSource"),
  } for visit in visits])
  chosen = get_latest_visit_per_location(frame)
  if len(chosen) == 0:
    return None
  object_id = int(chosen.iloc[0]["Visit_OBJECTID"])
  for visit in visits:
    if int(visit["OBJECTID"]) == object_id:
      return visit
  return None


WRITE_FIELDS = (
  "Urgency",
  "ParentStatusWithDomain",
  "DateVisitMadeFromLastVisit",
  "DateForNextVisitFromLastVisit",
  "LatestVisitStage",
  "LatestArea",
  "EffectiveStatus",
)


def _show_field(field, value, names):
  if field in ("ParentStatusWithDomain", "EffectiveStatus", "WeedVisitStatus"):
    return show_coded(value, names)
  if field in DATE_FIELDS:
    return format_moment(value)
  return show(value)


def _change_lines(changes, current, names):
  lines = []
  ordered = [field for field in WRITE_FIELDS if field in changes]
  ordered.extend(field for field in changes if field not in ordered)
  for field in ordered:
    old = _show_field(field, current.get(field), names)
    new = _show_field(field, changes[field], names)
    lines.append(f"  {field}: {old} -> {new}")
  return lines


def _newest_visit_edit(visits):
  moments = [as_auckland(visit.get("EditDate_1")) for visit in visits]
  moments = [moment for moment in moments if moment is not None]
  if not moments:
    return None
  return max(moments)


def format_report(weed, visits, today, last_run, source, process_all=False, status_names=None):
  """Short report of what maintenance would write, plus the weed and its visits."""
  weed = _scrub(weed)
  visits = [_scrub(visit) for visit in visits]
  if weed.get("OBJECTID") is None:
    raise ValueError("Weed location row is missing OBJECTID")
  names = status_names or {}
  weed_choice = changed_mode_selection(weed, last_run, today, process_all)
  visits_in_run = visit_sync_selected(visits, last_run, process_all)
  visit_changes = planned_visit_changes(weed, visits, today)
  writes = {}
  if weed_choice["included"] and "EffectiveStatus" in weed:
    writes.update(plan_effective_status([weed], today).get(weed["OBJECTID"], {}))
  if visits_in_run:
    writes.update(visit_changes)
  last_text = format_moment(last_run) if last_run is not None else "(none)"
  lines = [
    source,
    f"Instance {weed['OBJECTID']}. Last run {last_text}. Today {format_moment(today)}.",
    "",
  ]
  if writes:
    lines.append("Changed run would write:")
    lines.extend(_change_lines(writes, weed, names))
  else:
    lines.append("Changed run would write nothing.")
  if not visits_in_run:
    newest = _newest_visit_edit(visits)
    if not visits:
      lines.append("Visit sync: no visits.")
    elif newest is None:
      lines.append("Visit sync: no visit has an edit date after the last run.")
    else:
      lines.append(f"Visit sync: newest visit edit {format_moment(newest)} is before the last run.")
  if not weed_choice["included"]:
    lines.append(weed_choice["reason"])
  if not visits_in_run and visit_changes:
    lines.append("Full run would write:")
    lines.extend(_change_lines(visit_changes, weed, names))
  lines.append("Region and district are not checked here.")
  lines.append("")
  parent = weed.get("ParentStatusWithDomain")
  stored = weed.get("EffectiveStatus")
  lines.append(f"Weed: {show_coded(parent, names)}. Effective {show_coded(stored, names)}.")
  lines.append(
    f"Edited {format_moment(weed.get('EditDate_1'))} by {show(weed.get('Editor_1'))}. "
    f"Visit made {format_moment(weed.get('DateVisitMadeFromLastVisit'))}. "
    f"Next visit {format_moment(weed.get('DateForNextVisitFromLastVisit'))}."
  )
  species = weed.get("SpeciesDropDown")
  location = weed.get("LocationInfo")
  if species or location:
    lines.append(
      f"{show(species)}, {show(location)}. Region {show(weed.get('RegionCode'))}, district {show(weed.get('DistrictCode'))}."
    )
  chosen = latest_visit(visits)
  lines.append("")
  lines.append(f"Visits ({len(visits)})")
  if not visits:
    lines.append("  No visits.")
  else:
    chosen_id = None if chosen is None else int(chosen["OBJECTID"])
    for visit in sorted(visits, key=_visit_sort_key, reverse=True):
      marker = " latest" if int(visit["OBJECTID"]) == chosen_id else ""
      lines.append(
        f"  {int(visit['OBJECTID'])}{marker}  {show_coded(visit.get('WeedVisitStatus'), names)}"
        f"  check {format_moment(visit.get('DateCheck'))}"
        f"  return {format_moment(visit.get('DateForReturnVisit'))}"
        f"  edited {format_moment(visit.get('EditDate_1'))} by {show(visit.get('Editor_1'))}"
      )
  return "\n".join(lines)


def _visit_sort_key(visit):
  checked = as_auckland(visit.get("DateCheck"))
  created = as_auckland(visit.get("CreationDate_1"))
  primary = checked.timestamp() if checked else float("-inf")
  secondary = created.timestamp() if created else float("-inf")
  return (primary, secondary, int(visit.get("OBJECTID") or 0))


def _field_names(layer):
  return [field["name"] for field in layer.properties.fields]


def _coded_values(layer, field_name):
  for field in layer.properties.fields:
    if field["name"] != field_name:
      continue
    domain = field["domain"] if "domain" in field else None
    if not domain or "codedValues" not in domain or not domain["codedValues"]:
      return {}
    return {item["code"]: item["name"] for item in domain["codedValues"]}
  return {}


def _query_rows(layer, where, wanted):
  available = set(_field_names(layer))
  fields = [name for name in wanted if name in available]
  result = layer.query(where=where, out_fields=fields, return_geometry=False)
  rows = []
  for feature in result.features:
    attributes = feature.attributes or {}
    rows.append({name: attributes.get(name) for name in fields})
  names = {}
  for field_name in STATUS_FIELDS:
    names.update(_coded_values(layer, field_name))
  return rows, names


def _open_weed_layer(item, weed_name):
  if not weed_name:
    return FeatureLayer.fromitem(item)
  for layer in item.layers:
    if layer.properties.name == weed_name:
      return layer
  available = ", ".join(layer.properties.name for layer in item.layers) or "none"
  raise ValueError(f"Weed layer '{weed_name}' was not found. Available: {available}")


def _open_visits_table(item, visits_name):
  tables = list(getattr(item, "tables", []) or [])
  if visits_name:
    for table in tables:
      if table.properties.name == visits_name:
        return table
    available = ", ".join(table.properties.name for table in tables) or "none"
    raise ValueError(f"Visits table '{visits_name}' was not found. Available: {available}")
  matches = [table for table in tables if "visit" in table.properties.name.lower()]
  if len(matches) == 1:
    return matches[0]
  if not matches and len(tables) == 1:
    return tables[0]
  available = ", ".join(table.properties.name for table in tables) or "none"
  found = len(matches)
  raise ValueError(f"Expected one visits table, found {found}. Pass --visits-layer. Available: {available}")


def _sql_text(value):
  return "'" + str(value).replace("'", "''") + "'"


def load_feature_item(item, object_id, weed_name, visits_name, label):
  """Query one weed instance and its visits from a feature layer item."""
  layer = _open_weed_layer(item, weed_name)
  rows, names = _query_rows(layer, f"OBJECTID = {int(object_id)}", WEED_FIELDS)
  if not rows:
    return None
  weed = rows[0]
  table = _open_visits_table(item, visits_name)
  visits = []
  global_id = weed.get("GlobalID")
  if global_id:
    for form in guid_forms(global_id):
      found, visit_names = _query_rows(table, f"GUID_visits = {_sql_text(form)}", VISIT_FIELDS)
      names.update(visit_names)
      if found:
        visits = found
        break
  source = feature_source(label, item.title, item.id, layer.properties.name)
  return weed, visits, source, names


def _match_columns(schema, wanted):
  lookup = {name.lower(): name for name in schema}
  columns = []
  canonical = {}
  for name in wanted:
    actual = lookup.get(name.lower())
    if actual is not None:
      columns.append(actual)
      canonical[actual] = name
  return columns, canonical


def read_gdb_records(gdb_path, layer, wanted, where):
  """Read rows from one file-geodatabase layer. Missing fields are omitted."""
  import pyogrio

  info = pyogrio.read_info(gdb_path, layer=layer)
  schema = [str(name) for name in info["fields"]]
  columns, canonical = _match_columns(schema, wanted)
  if not columns:
    raise RuntimeError(f"Layer '{layer}' has none of the expected fields")
  frame = pyogrio.read_dataframe(gdb_path, layer=layer, columns=columns, where=where, read_geometry=False)
  records = []
  for raw in frame.to_dict(orient="records"):
    row = {}
    for actual, name in canonical.items():
      value = from_gdb_value(raw.get(actual))
      if name == "OBJECTID" and isinstance(value, float):
        value = int(value)
      row[name] = value
    records.append(row)
  return records


def _read_gdb_visits(gdb_path, layer, global_id):
  for form in guid_forms(global_id):
    found = read_gdb_records(gdb_path, layer, VISIT_FIELDS, f"GUID_visits = {_sql_text(form)}")
    if found:
      return found
  return []


def locate_gdb(directory):
  """Find the single .gdb directory extracted from an ArcGIS download."""
  found = []
  for dirpath, dirnames, _filenames in os.walk(directory):
    if os.path.basename(dirpath).lower().endswith(".gdb"):
      found.append(dirpath)
      dirnames.clear()
  if len(found) == 1:
    return found[0]
  if not found:
    raise RuntimeError(f"No file geodatabase was in the ArcGIS download under {directory}")
  raise RuntimeError("The download contains more than one file geodatabase: " + ", ".join(found))


def materialise_gdb(downloaded, directory):
  """Return the .gdb path from a download, unzipping when ArcGIS sent a zip."""
  if downloaded and os.path.isdir(downloaded) and downloaded.lower().endswith(".gdb"):
    return downloaded
  if downloaded and zipfile.is_zipfile(downloaded):
    with zipfile.ZipFile(downloaded) as archive:
      archive.extractall(directory)
  return locate_gdb(directory)


def load_file_geodatabase_item(item, object_id, weed_name, visits_name):
  """Download one file geodatabase item and read the instance from it."""
  import pyogrio

  with tempfile.TemporaryDirectory(prefix="weed-inspect-") as temp:
    print(f"Downloading ArcGIS file geodatabase '{item.title}'...", flush=True)
    downloaded = item.download(save_path=temp)
    gdb = materialise_gdb(downloaded, temp)
    listed = pyogrio.list_layers(gdb)
    layers = [(str(name), None if geometry is None else str(geometry)) for name, geometry in listed]
    weed_layer, visits_layer = choose_gdb_layers(layers, weed_name, visits_name)
    weeds = read_gdb_records(gdb, weed_layer, WEED_FIELDS, f"OBJECTID = {int(object_id)}")
    if not weeds:
      return None
    weed = weeds[0]
    visits = []
    if weed.get("GlobalID"):
      visits = _read_gdb_visits(gdb, visits_layer, weed["GlobalID"])
    return weed, visits, fgdb_source(item.title, item.id), {}


def read_last_run(gis, environment):
  """Last weed_maintenance timestamp for this environment.

  Reason: ensure_last_run inserts an audit row when one is missing. A report must not write.
  """
  settings = load_environment(environment)
  table = Table.fromitem(gis.content.get(settings["audit_table_id"]))
  where = f"ProcessName = '{PROCESS_NAME}' AND Environment = '{environment}'"
  result = table.query(where=where, out_fields=["LastRunTimestamp"], return_geometry=False)
  if not result.features:
    return None
  return as_auckland(result.features[0].attributes.get("LastRunTimestamp"))


def parse_last_run(text):
  """ISO datetime for --last-run. A value without a timezone is NZT."""
  try:
    parsed = datetime.fromisoformat(text)
  except ValueError as error:
    raise ValueError(f"Could not read --last-run '{text}'. Use an ISO datetime.") from error
  if parsed.tzinfo is None:
    parsed = parsed.replace(tzinfo=NZT)
  return parsed.astimezone(NZT)


def parse_today(text):
  """Calendar day for --today, at NZT midnight."""
  try:
    parsed = datetime.strptime(text, "%Y-%m-%d")
  except ValueError as error:
    raise ValueError(f"Could not read --today '{text}'. Use YYYY-MM-DD.") from error
  return parsed.replace(tzinfo=NZT)


def _load(gis, item, object_id, weed_name, visits_name, label):
  kind = source_kind(item.type)
  if kind == "fgdb":
    return load_file_geodatabase_item(item, object_id, weed_name, visits_name)
  return load_feature_item(item, object_id, weed_name, visits_name, label)


def inspect(object_id, environment, item_id, today, last_run, process_all, weed_name, visits_name):
  """Load one instance from ArcGIS and return the report text."""
  gis = connect_arcgis()
  if item_id:
    item = gis.content.get(item_id)
    if item is None:
      raise ValueError(f"ArcGIS item {item_id} was not found.")
    loaded = _load(gis, item, object_id, weed_name, visits_name, "portal item")
  else:
    settings = load_environment(environment)
    item = gis.content.get(settings["weed_locations_layer_id"])
    if item is None:
      raise ValueError(f"Weed locations item for {environment} was not found.")
    loaded = _load(gis, item, object_id, weed_name, visits_name, environment)
    if last_run is None:
      last_run = read_last_run(gis, environment)
  if loaded is None:
    raise ValueError(f"Weed instance {object_id} was not found.")
  weed, visits, source, names = loaded
  return format_report(weed, visits, today, last_run, source, process_all, names)


def parse_args(argv):
  """Command line for one weed instance id."""
  parser = argparse.ArgumentParser(
    description="Show how CAMS Weed Maintenance would treat one weed instance, read from ArcGIS.",
    epilog=(
      "Examples:\n"
      "  python weed_maintenance/inspect_instance.py 55622\n"
      "  python weed_maintenance/inspect_instance.py 55622 --env development\n"
      "  python weed_maintenance/inspect_instance.py 55622 --item <portal-item-id>\n"
    ),
    formatter_class=argparse.RawDescriptionHelpFormatter,
  )
  parser.add_argument("objectid", type=int, help="WeedLocations OBJECTID")
  parser.add_argument(
    "--env",
    "--environment",
    dest="environment",
    help="Feature layer environment (development or production). Defaults to production. Not used with --item.",
  )
  parser.add_argument(
    "--item",
    dest="item_id",
    help="ArcGIS item id of a feature layer or a file geodatabase backup",
  )
  parser.add_argument(
    "--last-run",
    dest="last_run",
    help="ISO datetime used as LastRunTimestamp. Defaults to the audit table for --env.",
  )
  parser.add_argument("--today", help="NZT calendar day YYYY-MM-DD. Defaults to today.")
  parser.add_argument(
    "--mode",
    choices=["changed", "all"],
    default="changed",
    help="changed matches the scheduled job. all reads every row (default: changed)",
  )
  parser.add_argument("--weed-layer", help="Layer name when an item has more than one weed layer")
  parser.add_argument("--visits-layer", help="Table name when an item has more than one visits table")
  args = parser.parse_args(argv)
  if args.item_id and args.environment:
    parser.error("Pass either --env or --item.")
  return args


def main(argv=None):
  """Print the report. Returns 0 when the instance was read."""
  args = parse_args(argv)
  today = parse_today(args.today) if args.today else datetime.now(NZT)
  last_run = parse_last_run(args.last_run) if args.last_run else None
  environment = args.environment or "production"
  try:
    report = inspect(
      args.objectid,
      environment,
      args.item_id,
      today,
      last_run,
      process_all=args.mode == "all",
      weed_name=args.weed_layer,
      visits_name=args.visits_layer,
    )
  except ValueError as error:
    print(error)
    return 1
  print(report)
  return 0


if __name__ == "__main__":
  sys.exit(main())
