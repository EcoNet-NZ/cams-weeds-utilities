# Next-visit date rollover

One-off fill of a missing next-visit date on existing weed instances. It does not change `ParentStatusWithDomain` to purple. A date that is already set is left unchanged, including a date in the past.

After this run, CAMS Easy Editor applies the same October rules when a visit is logged.

## Configuration

- Layer: `weed_locations_layer_id` in `weed_maintenance/config/environment_config.json`
- Visits table: the related table on that feature service whose name contains "visit"
- Environments: `development` or `production`
- Credentials: `ARCGIS_USERNAME`, `ARCGIS_PASSWORD`, optional `ARCGIS_PORTAL_URL`
- Calendar: Pacific/Auckland

A live production run is refused before 1 October of the current year.

## Records

`SpeciesDropDown` is one of:

- MothPlant
- OldMansBeard
- CathedralBells
- BananaPassionfruit
- BluePassionFlower
- Jasmine (CAMS label "Jasmine (Pink)")
- JapaneseHoneysuckle
- BlueMorningGlory
- WoollyNightshade
- Elaeagnus

`ParentStatusWithDomain` is one of:

- YellowKilledThisYear
- OrangeDeadHeaded
- GreenNoRegrowthThisYear
- PinkOccupantWillKillGrowth

## Visit date

First non-null value:

1. `DateVisitMadeFromLastVisit`
2. `DateOfLastCreateFromLastVisit`
3. `DateDiscovered`

If all three are null, do not suggest a date.

## Suggested 1 October

Cutoffs are 1 August for yellow and orange, and 1 October for green and pink:

- Yellow or orange, before 1 August: 1 October of that year. 31 July 2026 suggests 1 October 2026.
- Yellow or orange, on or after 1 August: 1 October of the next year. 1 August 2026 suggests 1 October 2027.
- Green or pink, before 1 October: 1 October of the next year. 30 September 2026 suggests 1 October 2027.
- Green or pink, on or after 1 October: 1 October two years later. 1 October 2026 suggests 1 October 2028.
- If that date is not after today, move forward one year at a time until it is
- If it would be more than five years after today, write nothing

Store the date as epoch milliseconds for midnight in Pacific/Auckland.

## Writes

Latest visit: most recent `DateCheck` for `GUID_visits` = weed `GlobalID`. If `DateCheck` is null, use `CreationDate_1`. The higher OBJECTID breaks a tie.

- Both `DateForNextVisitFromLastVisit` and the latest visit `DateForReturnVisit` already set: write nothing
- Only the weed date is set: copy it to the latest visit
- Only the visit date is set: copy it to the weed
- Both empty: write the suggestion to both
- No visit row: write the suggestion to the weed only

Do not change status, `audit_log`, or `StatusAt202510`.

## Run

- `--dry-run` previews and writes an Excel file
- `--limit N` caps the weed query
- `--env development` before `--env production`

The Excel file lists weed OBJECTID, visit OBJECTID, species, status, last visit date and source, existing dates, suggested date, and the action and written date on each side.
