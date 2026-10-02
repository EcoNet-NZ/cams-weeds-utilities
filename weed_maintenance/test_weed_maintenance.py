#!/usr/bin/env python3
"""Tests for WeedLocations effective status and the shared update pipeline."""

import os
import sys
import unittest
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from audit import resolve_audit
from effective_status import effective_status, plan_effective_status, require_effective_status_field
from merge import merge_attribute_updates
from pipeline import select_actions
from query import build_where

NZT = ZoneInfo("Pacific/Auckland")
TODAY = datetime(2026, 10, 2, 0, 20, tzinfo=NZT)
LAST_RUN = datetime(2026, 10, 1, 0, 15, tzinfo=NZT)


def epoch_ms(year, month, day, hour=0, minute=0):
  moment = datetime(year, month, day, hour, minute, tzinfo=NZT)
  return int(moment.timestamp() * 1000)


def row(**kwargs):
  record = {
    "OBJECTID": 10,
    "ParentStatusWithDomain": "YellowKilledThisYear",
    "DateForNextVisitFromLastVisit": None,
    "EffectiveStatus": None,
  }
  record.update(kwargs)
  return record


class EffectiveStatusTests(unittest.TestCase):
  def test_overdue_today_becomes_purple_historic(self):
    status = effective_status("YellowKilledThisYear", epoch_ms(2026, 10, 2), TODAY)
    self.assertEqual(status, "PurpleHistoric")

  def test_overdue_in_the_past_becomes_purple_historic(self):
    status = effective_status("GreenNoRegrowthThisYear", epoch_ms(2020, 1, 1), TODAY)
    self.assertEqual(status, "PurpleHistoric")

  def test_future_date_copies_parent_status(self):
    status = effective_status("YellowKilledThisYear", epoch_ms(2026, 10, 3), TODAY)
    self.assertEqual(status, "YellowKilledThisYear")

  def test_null_date_copies_parent_status(self):
    status = effective_status("OrangeDeadHeaded", None, TODAY)
    self.assertEqual(status, "OrangeDeadHeaded")

  def test_excluded_prefixes_stay_on_parent_status_when_overdue(self):
    overdue = epoch_ms(2026, 10, 2)
    for parent in ("RedActive", "BlackGone", "GrayDuplicate"):
      self.assertEqual(effective_status(parent, overdue, TODAY), parent)

  def test_null_parent_with_overdue_date_becomes_purple_historic(self):
    status = effective_status(None, epoch_ms(2026, 10, 1), TODAY)
    self.assertEqual(status, "PurpleHistoric")

  def test_parent_already_purple_historic_is_copied_when_not_overdue(self):
    status = effective_status("PurpleHistoric", epoch_ms(2027, 1, 1), TODAY)
    self.assertEqual(status, "PurpleHistoric")

  def test_lowercase_prefix_is_not_excluded(self):
    status = effective_status("redActive", epoch_ms(2026, 10, 2), TODAY)
    self.assertEqual(status, "PurpleHistoric")

  def test_unparseable_date_is_treated_as_unset(self):
    status = effective_status("YellowKilledThisYear", "not-a-date", TODAY)
    self.assertEqual(status, "YellowKilledThisYear")

  def test_plan_skips_unchanged_value(self):
    planned = plan_effective_status([
      row(EffectiveStatus="YellowKilledThisYear", DateForNextVisitFromLastVisit=epoch_ms(2026, 10, 3)),
    ], TODAY)
    self.assertEqual(planned, {})

  def test_plan_writes_only_a_changed_value(self):
    planned = plan_effective_status([
      row(DateForNextVisitFromLastVisit=epoch_ms(2026, 10, 2), EffectiveStatus="YellowKilledThisYear"),
    ], TODAY)
    self.assertEqual(planned, {10: {"EffectiveStatus": "PurpleHistoric"}})

  def test_plan_rejects_a_row_without_objectid(self):
    with self.assertRaises(ValueError):
      plan_effective_status([{"ParentStatusWithDomain": "YellowKilledThisYear"}], TODAY)

  def test_missing_field_stops_the_run(self):
    with self.assertRaises(RuntimeError):
      require_effective_status_field(["ParentStatusWithDomain"])

  def test_present_field_is_accepted(self):
    require_effective_status_field(["EffectiveStatus", "ParentStatusWithDomain"])


class QueryTests(unittest.TestCase):
  def test_changed_mode_includes_edits_and_newly_due_dates(self):
    where = build_where(LAST_RUN, TODAY, process_all=False)
    self.assertIn("EditDate_1 > timestamp '2026-09-30 11:15:00'", where)
    self.assertIn("DateForNextVisitFromLastVisit > timestamp '2026-09-30 11:15:00'", where)
    self.assertIn("DateForNextVisitFromLastVisit < timestamp '2026-10-02 11:00:00'", where)
    self.assertIn("EffectiveStatus <> 'PurpleHistoric'", where)
    self.assertIn(" NOT LIKE 'Red%'", where)
    self.assertIn(" NOT LIKE 'Black%'", where)
    self.assertIn(" NOT LIKE 'Gray%'", where)
    self.assertIn(" OR ", where)

  def test_mode_all_reads_every_row(self):
    self.assertEqual(build_where(LAST_RUN, TODAY, process_all=True), "1=1")

  def test_missing_last_run_reads_every_row(self):
    self.assertEqual(build_where(None, TODAY, process_all=False), "1=1")


class MergeTests(unittest.TestCase):
  def test_two_actions_merge_into_one_update(self):
    updates = merge_attribute_updates(
      {10: {"RegionCode": "02"}},
      {10: {"EffectiveStatus": "PurpleHistoric"}},
    )
    self.assertEqual(updates, [{
      "attributes": {
        "OBJECTID": 10,
        "RegionCode": "02",
        "EffectiveStatus": "PurpleHistoric",
      },
    }])

  def test_distinct_features_stay_separate(self):
    updates = merge_attribute_updates(
      {10: {"RegionCode": "02"}},
      {11: {"EffectiveStatus": "YellowKilledThisYear"}},
    )
    by_id = {item["attributes"]["OBJECTID"]: item["attributes"] for item in updates}
    self.assertEqual(set(by_id), {10, 11})
    self.assertEqual(by_id[11]["EffectiveStatus"], "YellowKilledThisYear")

  def test_empty_plans_produce_no_writes(self):
    self.assertEqual(merge_attribute_updates({}, {}), [])


class SelectActionsTests(unittest.TestCase):
  def test_all_runs_both_and_saves_the_timestamp(self):
    selected = select_actions("all")
    self.assertTrue(selected["status"])
    self.assertTrue(selected["spatial"])
    self.assertTrue(selected["save_last_run"])

  def test_status_skips_spatial_and_leaves_the_timestamp(self):
    selected = select_actions("status")
    self.assertTrue(selected["status"])
    self.assertFalse(selected["spatial"])
    self.assertFalse(selected["save_last_run"])

  def test_unknown_actions_are_rejected(self):
    with self.assertRaises(ValueError):
      select_actions("spatial")


class AuditTests(unittest.TestCase):
  def test_existing_process_row_is_reused(self):
    last_run, copy_from_old = resolve_audit(epoch_ms(2026, 10, 1, 0, 15), epoch_ms(2026, 9, 1))
    self.assertEqual(last_run, LAST_RUN)
    self.assertFalse(copy_from_old)

  def test_missing_process_row_copies_the_previous_timestamp(self):
    last_run, copy_from_old = resolve_audit(None, epoch_ms(2026, 10, 1, 0, 15))
    self.assertEqual(last_run, LAST_RUN)
    self.assertTrue(copy_from_old)

  def test_no_audit_row_processes_everything(self):
    last_run, copy_from_old = resolve_audit(None, None)
    self.assertIsNone(last_run)
    self.assertFalse(copy_from_old)

  def test_timestamp_from_utc_epoch_matches_nzt_wall_clock(self):
    utc_moment = datetime(2026, 9, 30, 11, 15, tzinfo=timezone.utc)
    last_run, copy_from_old = resolve_audit(int(utc_moment.timestamp() * 1000), None)
    self.assertEqual(last_run, LAST_RUN)
    self.assertFalse(copy_from_old)


if __name__ == "__main__":
  unittest.main()
