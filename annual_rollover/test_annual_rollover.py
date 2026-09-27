#!/usr/bin/env python3
"""Tests for the one-off next-visit date rollover."""

import os
import sys
import unittest
from datetime import datetime
from zoneinfo import ZoneInfo

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from next_visit_date import (
  plan_updates,
  resolve_last_visit_date,
  select_latest_visits,
  suggest_next_visit_date,
)

AUCKLAND = ZoneInfo("Pacific/Auckland")
TODAY = datetime(2026, 9, 27, 12, 0, tzinfo=AUCKLAND)


def akl(year, month, day):
  return datetime(year, month, day, tzinfo=AUCKLAND)


def epoch_ms(year, month, day):
  return int(akl(year, month, day).timestamp() * 1000)


def weed(**kwargs):
  record = {
    "OBJECTID": 10,
    "GlobalID": "{ABC}",
    "SpeciesDropDown": "MothPlant",
    "ParentStatusWithDomain": "YellowKilledThisYear",
    "DateForNextVisitFromLastVisit": None,
    "DateVisitMadeFromLastVisit": epoch_ms(2026, 3, 15),
    "DateOfLastCreateFromLastVisit": None,
    "DateDiscovered": None,
  }
  record.update(kwargs)
  return record


def visit(objectid=99, return_visit=None, date_check=None):
  return {
    "OBJECTID": objectid,
    "DateForReturnVisit": return_visit,
    "DateCheck": date_check if date_check is not None else epoch_ms(2026, 3, 15),
    "CreationDate_1": epoch_ms(2026, 3, 16),
  }


class SuggestNextVisitDateTests(unittest.TestCase):
  def test_yellow_on_or_before_31_july_is_1_october_same_year(self):
    suggested = suggest_next_visit_date(akl(2026, 3, 15), "YellowKilledThisYear", "MothPlant", TODAY)
    self.assertEqual(suggested, akl(2026, 10, 1))
    orange = suggest_next_visit_date(akl(2026, 7, 31), "OrangeDeadHeaded", "Jasmine", TODAY)
    self.assertEqual(orange, akl(2026, 10, 1))

  def test_yellow_or_orange_from_august_is_1_october_next_year(self):
    suggested = suggest_next_visit_date(akl(2026, 8, 1), "YellowKilledThisYear", "MothPlant", TODAY)
    self.assertEqual(suggested, akl(2027, 10, 1))
    december = suggest_next_visit_date(akl(2026, 12, 15), "OrangeDeadHeaded", "OldMansBeard", TODAY)
    self.assertEqual(december, akl(2027, 10, 1))

  def test_green_or_pink_before_1_october_is_1_october_next_year(self):
    green = suggest_next_visit_date(akl(2026, 9, 30), "GreenNoRegrowthThisYear", "Elaeagnus", TODAY)
    self.assertEqual(green, akl(2027, 10, 1))
    pink = suggest_next_visit_date(akl(2026, 1, 1), "PinkOccupantWillKillGrowth", "CathedralBells", TODAY)
    self.assertEqual(pink, akl(2027, 10, 1))

  def test_green_or_pink_from_1_october_is_two_years_out(self):
    green = suggest_next_visit_date(akl(2026, 10, 1), "GreenNoRegrowthThisYear", "MothPlant", TODAY)
    self.assertEqual(green, akl(2028, 10, 1))
    pink = suggest_next_visit_date(akl(2026, 10, 2), "PinkOccupantWillKillGrowth", "JapaneseHoneysuckle", TODAY)
    self.assertEqual(pink, akl(2028, 10, 1))

  def test_past_suggestion_moves_to_the_next_1_october_after_today(self):
    suggested = suggest_next_visit_date(akl(2024, 3, 15), "YellowKilledThisYear", "MothPlant", TODAY)
    self.assertEqual(suggested, akl(2026, 10, 1))

  def test_1_october_today_is_not_after_today(self):
    on_october_first = datetime(2026, 10, 1, 9, 0, tzinfo=AUCKLAND)
    suggested = suggest_next_visit_date(
      akl(2026, 3, 15), "YellowKilledThisYear", "MothPlant", on_october_first
    )
    self.assertEqual(suggested, akl(2027, 10, 1))

  def test_suggestion_more_than_five_years_ahead_is_skipped(self):
    today = datetime(2026, 1, 15, tzinfo=AUCKLAND)
    suggested = suggest_next_visit_date(akl(2030, 8, 1), "YellowKilledThisYear", "MothPlant", today)
    self.assertIsNone(suggested)

  def test_unlisted_species_and_other_statuses_get_no_date(self):
    self.assertIsNone(suggest_next_visit_date(akl(2026, 3, 15), "YellowKilledThisYear", "Gorse", TODAY))
    self.assertIsNone(suggest_next_visit_date(akl(2026, 3, 15), "RedGrowth", "MothPlant", TODAY))
    self.assertIsNone(suggest_next_visit_date(None, "YellowKilledThisYear", "MothPlant", TODAY))

  def test_utc_instant_on_31_july_evening_is_1_august_in_auckland(self):
    # 31 July 2026 14:00 UTC is 1 August 2026 02:00 in New Zealand (UTC+12).
    visit_instant = datetime(2026, 7, 31, 14, 0, tzinfo=ZoneInfo("UTC"))
    suggested = suggest_next_visit_date(visit_instant, "YellowKilledThisYear", "MothPlant", TODAY)
    self.assertEqual(suggested, akl(2027, 10, 1))


class ResolveLastVisitDateTests(unittest.TestCase):
  def test_date_visit_made_wins(self):
    resolved, source = resolve_last_visit_date(weed(
      DateVisitMadeFromLastVisit=epoch_ms(2026, 3, 15),
      DateOfLastCreateFromLastVisit=epoch_ms(2026, 8, 1),
      DateDiscovered=epoch_ms(2024, 1, 1),
    ))
    self.assertEqual(resolved, akl(2026, 3, 15))
    self.assertEqual(source, "DateVisitMade")

  def test_falls_back_to_create_then_discovered(self):
    created, source = resolve_last_visit_date(weed(
      DateVisitMadeFromLastVisit=None,
      DateOfLastCreateFromLastVisit=epoch_ms(2026, 8, 1),
      DateDiscovered=epoch_ms(2024, 1, 1),
    ))
    self.assertEqual(created, akl(2026, 8, 1))
    self.assertEqual(source, "DateOfLastCreate")

    discovered, source = resolve_last_visit_date(weed(
      DateVisitMadeFromLastVisit=None,
      DateOfLastCreateFromLastVisit=None,
      DateDiscovered=epoch_ms(2024, 1, 1),
    ))
    self.assertEqual(discovered, akl(2024, 1, 1))
    self.assertEqual(source, "DateDiscovered")

  def test_all_null_has_no_visit_date(self):
    resolved, source = resolve_last_visit_date(weed(
      DateVisitMadeFromLastVisit=None,
      DateOfLastCreateFromLastVisit=None,
      DateDiscovered=None,
    ))
    self.assertIsNone(resolved)
    self.assertEqual(source, "NoVisitDate")


class PlanUpdatesTests(unittest.TestCase):
  def test_existing_dates_are_left_unchanged(self):
    existing = epoch_ms(2024, 1, 1)
    decision = plan_updates(
      weed(DateForNextVisitFromLastVisit=existing),
      visit(return_visit=epoch_ms(2025, 6, 1)),
      TODAY,
    )
    self.assertIsNone(decision["weed_epoch"])
    self.assertIsNone(decision["visit_epoch"])
    self.assertEqual(decision["weed_action"], "left")
    self.assertEqual(decision["visit_action"], "left")

  def test_null_dates_are_filled_with_the_suggestion(self):
    decision = plan_updates(weed(), visit(), TODAY)
    self.assertEqual(decision["weed_epoch"], epoch_ms(2026, 10, 1))
    self.assertEqual(decision["visit_epoch"], epoch_ms(2026, 10, 1))
    self.assertEqual(decision["visit_objectid"], 99)
    self.assertEqual(decision["weed_action"], "set")
    self.assertEqual(decision["visit_action"], "set")

  def test_weed_date_is_copied_onto_an_empty_visit(self):
    existing = epoch_ms(2025, 10, 1)
    decision = plan_updates(
      weed(DateForNextVisitFromLastVisit=existing),
      visit(return_visit=None),
      TODAY,
    )
    self.assertIsNone(decision["weed_epoch"])
    self.assertEqual(decision["visit_epoch"], existing)
    self.assertEqual(decision["weed_action"], "left")
    self.assertEqual(decision["visit_action"], "copied_from_weed")

  def test_visit_date_is_copied_onto_an_empty_weed(self):
    existing = epoch_ms(2027, 10, 1)
    decision = plan_updates(
      weed(DateForNextVisitFromLastVisit=None),
      visit(return_visit=existing),
      TODAY,
    )
    self.assertEqual(decision["weed_epoch"], existing)
    self.assertIsNone(decision["visit_epoch"])
    self.assertEqual(decision["weed_action"], "copied_from_visit")
    self.assertEqual(decision["visit_action"], "left")

  def test_no_visit_row_sets_only_the_weed(self):
    decision = plan_updates(weed(), None, TODAY)
    self.assertEqual(decision["weed_epoch"], epoch_ms(2026, 10, 1))
    self.assertIsNone(decision["visit_epoch"])
    self.assertEqual(decision["visit_action"], "no_visit")

  def test_no_usable_date_writes_nothing(self):
    decision = plan_updates(weed(
      DateVisitMadeFromLastVisit=None,
      DateOfLastCreateFromLastVisit=None,
      DateDiscovered=None,
    ), visit(), TODAY)
    self.assertIsNone(decision["weed_epoch"])
    self.assertIsNone(decision["visit_epoch"])
    self.assertEqual(decision["weed_action"], "left")
    self.assertEqual(decision["visit_action"], "left")


class SelectLatestVisitTests(unittest.TestCase):
  def test_prefers_date_check_over_creation_date(self):
    older = {
      "OBJECTID": 1,
      "GUID_visits": "{ABC}",
      "DateCheck": epoch_ms(2026, 1, 1),
      "CreationDate_1": epoch_ms(2026, 6, 1),
      "DateForReturnVisit": None,
    }
    newer_create_only = {
      "OBJECTID": 2,
      "GUID_visits": "{ABC}",
      "DateCheck": None,
      "CreationDate_1": epoch_ms(2026, 8, 1),
      "DateForReturnVisit": None,
    }
    latest = select_latest_visits([older, newer_create_only])
    self.assertEqual(latest["{ABC}"]["OBJECTID"], 1)

  def test_uses_creation_date_when_date_check_is_missing(self):
    first = {
      "OBJECTID": 1,
      "GUID_visits": "{ABC}",
      "DateCheck": None,
      "CreationDate_1": epoch_ms(2025, 1, 1),
      "DateForReturnVisit": None,
    }
    second = {
      "OBJECTID": 2,
      "GUID_visits": "{ABC}",
      "DateCheck": None,
      "CreationDate_1": epoch_ms(2026, 1, 1),
      "DateForReturnVisit": epoch_ms(2026, 10, 1),
    }
    latest = select_latest_visits([first, second])
    self.assertEqual(latest["{ABC}"]["OBJECTID"], 2)

  def test_objectid_breaks_a_tie(self):
    low = {
      "OBJECTID": 3,
      "GUID_visits": "{ABC}",
      "DateCheck": epoch_ms(2026, 3, 15),
      "CreationDate_1": None,
      "DateForReturnVisit": None,
    }
    high = {
      "OBJECTID": 8,
      "GUID_visits": "{ABC}",
      "DateCheck": epoch_ms(2026, 3, 15),
      "CreationDate_1": None,
      "DateForReturnVisit": None,
    }
    latest = select_latest_visits([low, high])
    self.assertEqual(latest["{ABC}"]["OBJECTID"], 8)


if __name__ == "__main__":
  unittest.main()
