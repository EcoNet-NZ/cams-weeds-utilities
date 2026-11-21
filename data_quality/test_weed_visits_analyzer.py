#!/usr/bin/env python3
"""Tests for WeedLocations / Visits report formatting."""

import os
import sys
import unittest
from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from weed_visits_analyzer import check_field_mismatches, parent_status_ignored, prefix_masked_values


class PrefixMaskedValuesTests(unittest.TestCase):
  def test_numeric_mismatch_is_prefixed_without_upcast_error(self):
    df = pd.DataFrame({
      "DifficultyChild": [1.0, 2.0, 3.0],
      "Urgency_Mismatch": ["X", "", "X"],
    })
    mask = (df["Urgency_Mismatch"] == "X") & df["DifficultyChild"].notna()

    prefix_masked_values(df, "DifficultyChild", mask)

    self.assertEqual(df["DifficultyChild"].tolist(), ["← 1.0", 2.0, "← 3.0"])

  def test_null_numeric_value_is_left_unchanged(self):
    df = pd.DataFrame({
      "DifficultyChild": [1.0, None],
      "Urgency_Mismatch": ["X", "X"],
    })
    mask = (df["Urgency_Mismatch"] == "X") & df["DifficultyChild"].notna()

    prefix_masked_values(df, "DifficultyChild", mask)

    self.assertEqual(df["DifficultyChild"].iloc[0], "← 1.0")
    self.assertTrue(pd.isna(df["DifficultyChild"].iloc[1]))

  def test_string_date_mismatch_is_prefixed(self):
    df = pd.DataFrame({
      "DateCheck": ["2026-01-02 00:00:00", "2026-03-04 00:00:00"],
      "DateVisitMade_Mismatch": ["X", ""],
    })
    mask = (df["DateVisitMade_Mismatch"] == "X") & df["DateCheck"].notna()

    prefix_masked_values(df, "DateCheck", mask)

    self.assertEqual(
      df["DateCheck"].tolist(),
      ["← 2026-01-02 00:00:00", "2026-03-04 00:00:00"],
    )


class ParentStatusIgnoreTests(unittest.TestCase):
  def test_recent_visit_is_a_status_mismatch(self):
    compared, _columns, _rules = check_field_mismatches(pd.DataFrame([
      _status_row(created=_epoch(2026, 11, 8, 17, 1), edited=_epoch(2026, 11, 8, 17, 2)),
      _status_row(created=_epoch(2026, 9, 30, 23, 59), edited=_epoch(2025, 6, 1)),
    ]))
    self.assertEqual(compared["Status_Mismatch"].tolist(), ["X", ""])

  def test_either_audit_date_on_the_cutoff_allows_the_copy(self):
    cutoff = _epoch(2026, 11, 1)
    crossover = _epoch(2026, 10, 31, 23, 59)
    self.assertFalse(parent_status_ignored("PurpleHistoric", "YellowKilledThisYear", cutoff, None))
    self.assertFalse(parent_status_ignored("PurpleHistoric", "YellowKilledThisYear", None, cutoff))
    self.assertTrue(parent_status_ignored("PurpleHistoric", "YellowKilledThisYear", crossover, crossover))
    self.assertTrue(parent_status_ignored("PurpleHistoric", "YellowKilledThisYear", None, None))
    self.assertFalse(parent_status_ignored("YellowKilledThisYear", "OrangeDeadHeaded", None, None))


def _epoch(year, month, day, hour=0, minute=0):
  moment = datetime(year, month, day, hour, minute, tzinfo=ZoneInfo("Pacific/Auckland"))
  return int(moment.timestamp() * 1000)


def _status_row(created, edited):
  return {
    "Visit_OBJECTID": 1,
    "DateCheck": created,
    "visit_CreationDate_1": created,
    "visit_EditDate_1": edited,
    "ParentStatusWithDomain": "PurpleHistoric",
    "WeedVisitStatus": "YellowKilledThisYear",
    "Urgency": 1,
    "DifficultyChild": 1,
    "DateVisitMadeFromLastVisit": created,
    "DateForNextVisitFromLastVisit": None,
    "DateForReturnVisit": None,
    "LatestVisitStage": None,
    "VisitStage": None,
    "LatestArea": 0,
    "Area": 0,
  }


if __name__ == "__main__":
  unittest.main()
