# Tasks

## 2026-10-07 — Nightly visit sync

Copy the latest Visits_Table row onto WeedLocations during weed maintenance, using the analyzer's latest-visit rule.

- [x] Tests for latest visit, purple skip, null clear, audit exclusion, effective status, and preview
- [x] `plan_visit_sync` uses the analyzer rules
- [x] Pipeline loads changed or all visits, merges one write, `--actions visits` and `--preview`
- [x] Schema and README updates, including the visit-sync flow diagram

### Discovered during work

- [ ] Run `python weed_maintenance/weed_maintenance.py --env production --mode all --preview`, then `--mode all` once, so the backlog is repaired before the nightly changed run

## 2026-10-02 — Effective status on WeedLocations

Daily `EffectiveStatus` on WeedLocations, in the same read and write as region and district assignment.

- [x] Tests for the overdue rule, the incremental query, merged updates, and audit carry-over
- [x] `weed_maintenance` pipeline, one query and one write, audit process `weed_maintenance`
- [x] GitHub Actions at 00:15 NZT, production on the schedule
- [x] Schema and README updates

### Discovered during work

- [ ] Create `EffectiveStatus` on WeedLocations in ArcGIS (development, then production) before the job writes. String, length 100, nullable, with a domain that includes every parent status code. `PurpleHistoric` displays as "Purple - please check".
- [x] `--actions status` runs effective status only and leaves `LastRunTimestamp` unchanged
