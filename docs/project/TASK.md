# Tasks

## 2026-10-02 — Effective status on WeedLocations

Daily `EffectiveStatus` on WeedLocations, in the same read and write as region and district assignment.

- [x] Tests for the overdue rule, the incremental query, merged updates, and audit carry-over
- [x] `weed_maintenance` pipeline, one query and one write, audit process `weed_maintenance`
- [x] GitHub Actions at 00:15 NZT, production on the schedule
- [x] Schema and README updates

### Discovered during work

- [ ] Create `EffectiveStatus` on WeedLocations in ArcGIS (development, then production) before the job writes. String, length 100, nullable, with a domain that includes every parent status code. `PurpleHistoric` displays as "Purple - please check".
- [x] `--actions status` runs effective status only and leaves `LastRunTimestamp` unchanged
