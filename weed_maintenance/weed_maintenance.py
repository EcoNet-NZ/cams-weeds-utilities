#!/usr/bin/env python3
"""Update WeedLocations region, district, and effective status."""

import argparse

from pipeline import run


def main():
  parser = argparse.ArgumentParser(
    description="Update WeedLocations region, district, and effective status",
  )
  parser.add_argument(
    "--mode",
    choices=["all", "changed"],
    default="changed",
    help="Process all features or only changed ones (default: changed)",
  )
  parser.add_argument(
    "--actions",
    choices=["all", "status"],
    default="all",
    help="all runs effective status and spatial codes. status runs effective status only and leaves LastRunTimestamp unchanged (default: all)",
  )
  parser.add_argument(
    "--env",
    "--environment",
    dest="environment",
    required=True,
    help="Environment to use (development or production)",
  )
  args = parser.parse_args()
  run(args.environment, process_all=(args.mode == "all"), actions=args.actions)


if __name__ == "__main__":
  main()
