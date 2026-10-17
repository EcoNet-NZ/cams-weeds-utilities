#!/usr/bin/env python3
"""Tests for the weed-maintenance instance report."""

import os
import sys
import unittest
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from inspect_instance import (
  changed_mode_selection,
  choose_gdb_layers,
  feature_source,
  fgdb_source,
  format_report,
  from_gdb_value,
  guid_forms,
  source_kind,
)

NZT = ZoneInfo("Pacific/Auckland")
TODAY = datetime(2026, 10, 17, 11, 30, tzinfo=NZT)
LAST_RUN = datetime(2026, 10, 1, 0, 15, tzinfo=NZT)


def epoch_ms(year, month, day, hour=0, minute=0):
  moment = datetime(year, month, day, hour, minute, tzinfo=NZT)
  return int(moment.timestamp() * 1000)


def weed(**kwargs):
  record = {
    "OBJECTID": 55622,
    "GlobalID": "{ABC}",
    "ParentStatusWithDomain": "OrangeDeadHeaded",
    "EffectiveStatus": "OrangeDeadHeaded",
    "DateForNextVisitFromLastVisit": epoch_ms(2026, 10, 1),
    "DateVisitMadeFromLastVisit": epoch_ms(2026, 9, 1),
    "EditDate_1": epoch_ms(2026, 10, 13, 9, 30),
    "Editor_1": "cams-maintenance",
    "CreationDate_1": epoch_ms(2024, 5, 1, 8, 0),
    "Creator_1": "alex",
    "RegionCode": "02",
    "DistrictCode": "023",
  }
  record.update(kwargs)
  return record


def visit(**kwargs):
  record = {
    "OBJECTID": 90,
    "GUID_visits": "{ABC}",
    "WeedVisitStatus": "YellowKilledThisYear",
    "DateCheck": epoch_ms(2026, 10, 12, 14, 0),
    "DateForReturnVisit": epoch_ms(2026, 10, 1),
    "CreationDate_1": epoch_ms(2026, 10, 12, 15, 0),
    "Creator_1": "sam",
    "EditDate_1": epoch_ms(2026, 10, 12, 15, 5),
    "Editor_1": "sam",
    "VisitDataSource": "CAMS",
  }
  record.update(kwargs)
  return record


class ReportTests(unittest.TestCase):
  def test_changed_run_copies_the_latest_visit_when_that_visit_was_edited(self):
    older = visit(
      OBJECTID=10,
      WeedVisitStatus="OrangeDeadHeaded",
      DateCheck=epoch_ms(2026, 9, 1, 10, 0),
      EditDate_1=epoch_ms(2026, 9, 1, 10, 0),
      Editor_1="alex",
    )
    report = format_report(
      weed(),
      [older, visit()],
      TODAY,
      LAST_RUN,
      feature_source("production", "CAMS Weeds", "item-1", "WeedLocations"),
      process_all=False,
    )
    self.assertIn("Changed run would write:", report)
    self.assertIn("ParentStatusWithDomain: OrangeDeadHeaded -> YellowKilledThisYear", report)
    self.assertIn("EffectiveStatus: OrangeDeadHeaded -> PurpleHistoric", report)
    self.assertIn("90 latest  YellowKilledThisYear", report)
    self.assertIn("Edited 2026-10-13 09:30:00 NZDT by cams-maintenance", report)
    self.assertIn("edited 2026-10-12 15:05:00 NZDT by sam", report)
    self.assertNotIn("10 latest", report)
    self.assertNotIn("does not write ParentStatusWithDomain", report)

  def test_stale_visit_is_left_until_a_full_run(self):
    report = format_report(
      weed(
        EditDate_1=epoch_ms(2026, 9, 1),
        DateForNextVisitFromLastVisit=None,
        DateVisitMadeFromLastVisit=epoch_ms(2026, 8, 8),
      ),
      [visit(
        EditDate_1=epoch_ms(2026, 9, 30, 22, 50),
        DateCheck=epoch_ms(2026, 8, 22),
        DateForReturnVisit=epoch_ms(2027, 10, 1),
        Editor_1="ncharman_preprod_econet",
      )],
      TODAY,
      LAST_RUN,
      "ArcGIS feature layer",
    )
    self.assertIn("Changed run would write nothing.", report)
    self.assertIn("Visit sync: newest visit edit 2026-09-30 22:50:00 NZDT is before the last run.", report)
    self.assertIn("Full run would write:", report)
    self.assertIn("ParentStatusWithDomain: OrangeDeadHeaded -> YellowKilledThisYear", report)
    self.assertIn("EffectiveStatus: OrangeDeadHeaded -> YellowKilledThisYear", report)

  def test_closed_status_outside_the_edit_window_is_not_selected(self):
    report = format_report(
      weed(
        ParentStatusWithDomain="RedActive",
        EffectiveStatus="RedActive",
        EditDate_1=epoch_ms(2026, 9, 1),
        DateForNextVisitFromLastVisit=epoch_ms(2026, 10, 16),
      ),
      [],
      TODAY,
      LAST_RUN,
      "ArcGIS feature layer",
    )
    self.assertIn("Changed run would write nothing.", report)
    self.assertIn("Visit sync: no visits.", report)
    self.assertIn("before the last run", report)
    self.assertNotIn("PurpleHistoric", report)

  def test_missing_objectid_is_rejected(self):
    row = weed()
    del row["OBJECTID"]
    with self.assertRaises(ValueError):
      format_report(row, [], TODAY, LAST_RUN, "ArcGIS feature layer")


class SelectionTests(unittest.TestCase):
  def test_newly_due_visit_is_selected_without_an_edit(self):
    result = changed_mode_selection(
      weed(
        EditDate_1=epoch_ms(2026, 9, 1),
        DateForNextVisitFromLastVisit=epoch_ms(2026, 10, 16),
        EffectiveStatus=None,
        ParentStatusWithDomain="YellowKilledThisYear",
      ),
      LAST_RUN,
      TODAY,
      process_all=False,
    )
    self.assertTrue(result["included"])
    self.assertIn("Next visit became due after the last run.", result["reason"])

  def test_mode_all_includes_every_row(self):
    result = changed_mode_selection(weed(EditDate_1=epoch_ms(2020, 1, 1)), LAST_RUN, TODAY, process_all=True)
    self.assertTrue(result["included"])
    self.assertEqual(result["reason"], "Mode all reads every weed.")

  def test_missing_last_run_includes_every_row(self):
    result = changed_mode_selection(weed(), None, TODAY, process_all=False)
    self.assertTrue(result["included"])
    self.assertEqual(result["reason"], "No last run, so every weed is read.")


class ArcGISSourceTests(unittest.TestCase):
  def test_feature_layer_and_file_geodatabase_items_are_accepted(self):
    self.assertEqual(source_kind("Feature Service"), "feature")
    self.assertEqual(source_kind("Feature Layer"), "feature")
    self.assertEqual(source_kind("File Geodatabase"), "fgdb")

  def test_other_item_types_are_rejected(self):
    with self.assertRaises(ValueError):
      source_kind("Web Map")

  def test_gdb_layers_are_chosen_by_name(self):
    layers = [("WeedLocations", "Point"), ("Visits_Table", None), ("WeedLocations__ATTACH", None)]
    self.assertEqual(choose_gdb_layers(layers, None, None), ("WeedLocations", "Visits_Table"))

  def test_ambiguous_gdb_layers_need_an_explicit_name(self):
    layers = [("WeedLocations", "Point"), ("WeedLocations_backup", "Point"), ("Visits_Table", None)]
    with self.assertRaises(ValueError):
      choose_gdb_layers(layers, None, None)

  def test_naive_gdb_datetimes_are_utc(self):
    value = from_gdb_value(datetime(2026, 10, 12, 20, 30))
    self.assertEqual(value, datetime(2026, 10, 12, 20, 30, tzinfo=timezone.utc))

  def test_guid_forms_cover_braces(self):
    self.assertEqual(guid_forms("{abc-def}"), ["{abc-def}", "abc-def"])

  def test_source_labels_name_the_arcgis_item(self):
    self.assertIn("item-9", feature_source("production", "CAMS", "item-9", "WeedLocations"))
    self.assertIn("UTC", fgdb_source("Backup", "item-9"))


if __name__ == "__main__":
  unittest.main()
