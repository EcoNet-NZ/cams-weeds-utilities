#!/usr/bin/env python3
"""Update WeedLocations region, district, effective status, and latest-visit fields."""

import argparse

from pipeline import run


def main():
  parser = argparse.ArgumentParser(
    description="Update WeedLocations region, district, effective status, and latest-visit fields",
  )
  parser.add_argument(
    "--mode",
    choices=["all", "changed"],
    default="changed",
    help="Process all features or only changed ones (default: changed)",
  )
  parser.add_argument(
    "--actions",
    choices=["all", "status", "visits"],
    default="all",
    help=(
      "all runs effective status, spatial codes, and visit sync. "
      "status runs effective status only. "
      "visits runs visit sync only. "
      "status and visits leave LastRunTimestamp unchanged (default: all)"
    ),
  )
  parser.add_argument(
    "--preview",
    action="store_true",
    help="Print planned WeedLocations updates and do not write",
  )
  parser.add_argument(
    "--env",
    "--environment",
    dest="environment",
    required=True,
    help="Environment to use (development or production)",
  )
  args = parser.parse_args()
  run(
    args.environment,
    process_all=(args.mode == "all"),
    actions=args.actions,
    preview=args.preview,
  )


if __name__ == "__main__":
  main()
