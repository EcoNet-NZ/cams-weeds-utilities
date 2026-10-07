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
from actions.visit_sync import build_visit_where, format_preview, plan_visit_sync
from pipeline import select_actions, should_persist
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

  def test_changed_visits_use_edit_date(self):
    where = build_visit_where(LAST_RUN, process_all=False)
    self.assertEqual(where, "EditDate_1 > timestamp '2026-09-30 11:15:00'")

  def test_all_visits_reads_every_row(self):
    self.assertEqual(build_visit_where(LAST_RUN, process_all=True), "1=1")

  def test_missing_last_run_reads_every_visit(self):
    self.assertEqual(build_visit_where(None, process_all=False), "1=1")


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


def synced_weed(**kwargs):
  record = {
    "OBJECTID": 10,
    "GlobalID": "{WEED}",
    "Urgency": 1,
    "ParentStatusWithDomain": "YellowKilledThisYear",
    "DateVisitMadeFromLastVisit": epoch_ms(2026, 6, 1),
    "DateForNextVisitFromLastVisit": epoch_ms(2026, 12, 1),
    "LatestVisitStage": "Monitoring",
    "LatestArea": 12.5,
    "EffectiveStatus": "YellowKilledThisYear",
    "DateOfLastCreateFromLastVisit": epoch_ms(2026, 6, 1),
    "DateOfLastEditFromLastVisit": epoch_ms(2026, 6, 2),
  }
  record.update(kwargs)
  return record


def synced_visit(**kwargs):
  record = {
    "OBJECTID": 100,
    "GUID_visits": "{WEED}",
    "DifficultyChild": 1,
    "WeedVisitStatus": "YellowKilledThisYear",
    "DateCheck": epoch_ms(2026, 6, 1),
    "DateForReturnVisit": epoch_ms(2026, 12, 1),
    "VisitStage": "Monitoring",
    "Area": 12.5,
    "CreationDate_1": epoch_ms(2026, 6, 1),
    "EditDate_1": epoch_ms(2026, 6, 2),
  }
  record.update(kwargs)
  return record


class VisitSyncTests(unittest.TestCase):
  def test_newest_datecheck_wins_over_a_later_creation_date(self):
    planned = plan_visit_sync([synced_weed()], [
      synced_visit(OBJECTID=2, DateCheck=None, CreationDate_1=epoch_ms(2026, 9, 1), DifficultyChild=9),
      synced_visit(OBJECTID=1, DateCheck=epoch_ms(2026, 1, 1), DifficultyChild=2),
    ], TODAY)
    self.assertEqual(planned[10]["Urgency"], 2)

  def test_missing_datecheck_uses_newest_creation_date_then_objectid(self):
    by_creation = plan_visit_sync([synced_weed()], [
      synced_visit(OBJECTID=1, DateCheck=None, CreationDate_1=epoch_ms(2026, 1, 1), DifficultyChild=2),
      synced_visit(OBJECTID=2, DateCheck=None, CreationDate_1=epoch_ms(2026, 8, 1), DifficultyChild=9),
    ], TODAY)
    self.assertEqual(by_creation[10]["Urgency"], 9)

    by_objectid = plan_visit_sync([synced_weed()], [
      synced_visit(OBJECTID=1, DateCheck=None, CreationDate_1=epoch_ms(2026, 3, 1), DifficultyChild=2),
      synced_visit(OBJECTID=5, DateCheck=None, CreationDate_1=epoch_ms(2026, 3, 1), DifficultyChild=4),
    ], TODAY)
    self.assertEqual(by_objectid[10]["Urgency"], 4)

  def test_purple_parent_status_is_not_replaced(self):
    planned = plan_visit_sync([
      synced_weed(ParentStatusWithDomain="PurpleHistoric", EffectiveStatus="PurpleHistoric"),
    ], [
      synced_visit(WeedVisitStatus="YellowKilledThisYear"),
    ], TODAY)
    self.assertEqual(planned, {})

  def test_non_purple_status_is_replaced(self):
    planned = plan_visit_sync([synced_weed()], [
      synced_visit(WeedVisitStatus="OrangeDeadHeaded"),
    ], TODAY)
    self.assertEqual(planned[10]["ParentStatusWithDomain"], "OrangeDeadHeaded")
    self.assertEqual(planned[10]["EffectiveStatus"], "OrangeDeadHeaded")

  def test_null_visit_value_clears_the_weed_field(self):
    planned = plan_visit_sync([synced_weed()], [
      synced_visit(DateForReturnVisit=None),
    ], TODAY)
    self.assertIsNone(planned[10]["DateForNextVisitFromLastVisit"])

  def test_both_null_is_not_a_write(self):
    planned = plan_visit_sync([
      synced_weed(DateForNextVisitFromLastVisit=None),
    ], [
      synced_visit(DateForReturnVisit=None),
    ], TODAY)
    self.assertEqual(planned, {})

  def test_weed_with_no_visits_is_not_a_write(self):
    planned = plan_visit_sync([synced_weed()], [], TODAY)
    self.assertEqual(planned, {})

  def test_audit_dates_are_absent_from_the_plan(self):
    planned = plan_visit_sync([
      synced_weed(
        DateOfLastCreateFromLastVisit=epoch_ms(2020, 1, 1),
        DateOfLastEditFromLastVisit=epoch_ms(2020, 1, 2),
      ),
    ], [
      synced_visit(CreationDate_1=epoch_ms(2026, 8, 1), EditDate_1=epoch_ms(2026, 8, 2)),
    ], TODAY)
    self.assertEqual(planned, {})

  def test_status_inputs_also_plan_effective_status(self):
    overdue = plan_visit_sync([synced_weed()], [
      synced_visit(DateForReturnVisit=epoch_ms(2026, 10, 2)),
    ], TODAY)
    self.assertEqual(overdue[10]["DateForNextVisitFromLastVisit"], epoch_ms(2026, 10, 2))
    self.assertEqual(overdue[10]["EffectiveStatus"], "PurpleHistoric")

    renamed = plan_visit_sync([synced_weed()], [
      synced_visit(WeedVisitStatus="GreenNoRegrowthThisYear"),
    ], TODAY)
    self.assertEqual(renamed[10]["ParentStatusWithDomain"], "GreenNoRegrowthThisYear")
    self.assertEqual(renamed[10]["EffectiveStatus"], "GreenNoRegrowthThisYear")

  def test_changed_older_visit_still_writes_the_newer_visit(self):
    planned = plan_visit_sync([
      synced_weed(
        Urgency=1,
        DateVisitMadeFromLastVisit=epoch_ms(2026, 1, 1),
        DateForNextVisitFromLastVisit=epoch_ms(2026, 2, 1),
        LatestVisitStage="Inspect",
        LatestArea=1,
      ),
    ], [
      synced_visit(
        OBJECTID=1,
        DateCheck=epoch_ms(2026, 1, 1),
        DateForReturnVisit=epoch_ms(2026, 2, 1),
        DifficultyChild=1,
        VisitStage="Inspect",
        Area=1,
      ),
      synced_visit(
        OBJECTID=2,
        DateCheck=epoch_ms(2026, 8, 1),
        DateForReturnVisit=epoch_ms(2026, 11, 1),
        DifficultyChild=4,
        VisitStage="Control",
        Area=8,
      ),
    ], TODAY)
    self.assertEqual(planned[10]["Urgency"], 4)
    self.assertEqual(planned[10]["DateVisitMadeFromLastVisit"], epoch_ms(2026, 8, 1))
    self.assertEqual(planned[10]["LatestVisitStage"], "Control")
    self.assertEqual(planned[10]["LatestArea"], 8)
    self.assertNotIn("DateOfLastCreateFromLastVisit", planned[10])

  def test_missing_objectid_is_rejected(self):
    with self.assertRaises(ValueError):
      plan_visit_sync([{"GlobalID": "{WEED}"}], [synced_visit()], TODAY)


class SelectActionsTests(unittest.TestCase):
  def test_all_runs_status_spatial_and_visits(self):
    selected = select_actions("all")
    self.assertTrue(selected["status"])
    self.assertTrue(selected["spatial"])
    self.assertTrue(selected["visits"])
    self.assertTrue(selected["save_last_run"])

  def test_status_skips_spatial_and_leaves_the_timestamp(self):
    selected = select_actions("status")
    self.assertTrue(selected["status"])
    self.assertFalse(selected["spatial"])
    self.assertFalse(selected["visits"])
    self.assertFalse(selected["save_last_run"])

  def test_visits_runs_sync_only_and_leaves_the_timestamp(self):
    selected = select_actions("visits")
    self.assertTrue(selected["visits"])
    self.assertFalse(selected["status"])
    self.assertFalse(selected["spatial"])
    self.assertFalse(selected["save_last_run"])

  def test_unknown_actions_are_rejected(self):
    with self.assertRaises(ValueError):
      select_actions("spatial")


class PreviewTests(unittest.TestCase):
  def test_preview_lists_old_and_new_values(self):
    lines = format_preview(
      [{"attributes": {"OBJECTID": 10, "Urgency": 4, "EffectiveStatus": "PurpleHistoric"}}],
      {10: {"Urgency": 1, "EffectiveStatus": "YellowKilledThisYear"}},
    )
    self.assertEqual(lines, [
      "OBJECTID 10: Urgency=1->4, EffectiveStatus=YellowKilledThisYear->PurpleHistoric",
      "1 updates",
    ])

  def test_preview_prints_dates_not_epoch_milliseconds(self):
    lines = format_preview(
      [{"attributes": {"OBJECTID": 10, "DateForNextVisitFromLastVisit": epoch_ms(2026, 10, 2)}}],
      {10: {"DateForNextVisitFromLastVisit": epoch_ms(2026, 12, 1)}},
    )
    self.assertEqual(lines, [
      "OBJECTID 10: DateForNextVisitFromLastVisit=2026-12-01->2026-10-02",
      "1 updates",
    ])

  def test_preview_keeps_a_time_that_is_not_midnight(self):
    lines = format_preview(
      [{"attributes": {"OBJECTID": 10, "DateVisitMadeFromLastVisit": epoch_ms(2026, 6, 1, 15, 30)}}],
      {10: {"DateVisitMadeFromLastVisit": epoch_ms(2026, 6, 1)}},
    )
    self.assertEqual(
      lines[0],
      "OBJECTID 10: DateVisitMadeFromLastVisit=2026-06-01->2026-06-01 15:30:00",
    )

  def test_preview_prints_a_cleared_date_as_null(self):
    lines = format_preview(
      [{"attributes": {"OBJECTID": 10, "DateVisitMadeFromLastVisit": None}}],
      {10: {"DateVisitMadeFromLastVisit": epoch_ms(2026, 6, 1)}},
    )
    self.assertEqual(
      lines[0],
      "OBJECTID 10: DateVisitMadeFromLastVisit=2026-06-01->null",
    )

  def test_preview_of_no_updates_prints_zero(self):
    self.assertEqual(format_preview([], {}), ["0 updates"])

  def test_preview_does_not_write_or_move_the_timestamp(self):
    self.assertEqual(should_persist(preview=True, save_last_run=True), (False, False))

  def test_live_run_writes_and_honours_the_save_flag(self):
    self.assertEqual(should_persist(preview=False, save_last_run=True), (True, True))
    self.assertEqual(should_persist(preview=False, save_last_run=False), (True, False))


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
