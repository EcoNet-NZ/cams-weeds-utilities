#!/usr/bin/env python3
"""Tests for WeedLocations / Visits report formatting."""

import os
import sys
import unittest

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from weed_visits_analyzer import prefix_masked_values


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


if __name__ == "__main__":
  unittest.main()
