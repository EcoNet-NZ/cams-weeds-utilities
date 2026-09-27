# Next-visit date rollover

Fills a missing next-visit date on listed weed instances. It does not change status, and it does not replace a date that is already set.

This is a one-off backfill. After it runs, CAMS Easy Editor sets the date when a visit is logged. A past next-visit date is shown on the map as a purple border. Existing purple dots stay purple until they are visited.

Dates are calculated in Pacific/Auckland.

## Quick start

```bash
pip install -r requirements.txt

export ARCGIS_USERNAME="your_username"
export ARCGIS_PASSWORD="your_password"
export ARCGIS_PORTAL_URL="https://www.arcgis.com"

python annual_rollover/annual_rollover.py --env development --dry-run
python annual_rollover/annual_rollover.py --env development
python annual_rollover/annual_rollover.py --env development --limit 100
```

A live production run is refused before 1 October of the current year.

## What it writes

Only when that field is null:

- WeedLocations `DateForNextVisitFromLastVisit`
- The latest visit's `DateForReturnVisit`

The latest visit is the one with the most recent `DateCheck`, or `CreationDate_1` when `DateCheck` is null. `GUID_visits` matches the weed `GlobalID`.

When one side already has a date, that value is copied to the empty side. When both are empty, both receive the suggested 1 October. When there is no visit row, only the weed field is set. Status, `audit_log`, and `StatusAt202510` are not written.

## Suggested date

Species codes: MothPlant, OldMansBeard, CathedralBells, BananaPassionfruit, BluePassionFlower, Jasmine, JapaneseHoneysuckle, BlueMorningGlory, WoollyNightshade, Elaeagnus.

The visit date is the first of `DateVisitMadeFromLastVisit`, `DateOfLastCreateFromLastVisit`, and `DateDiscovered`. If all three are null, nothing is suggested.

| Status | Visit date | Suggested next visit |
| --- | --- | --- |
| YellowKilledThisYear or OrangeDeadHeaded | Before 1 August | 1 October the same year |
| Yellow or orange | On or after 1 August | 1 October the next year |
| GreenNoRegrowthThisYear or PinkOccupantWillKillGrowth | Before 1 October | 1 October the next year |
| Green or pink | On or after 1 October | 1 October two years later |

If that 1 October is not after today, it moves forward one year at a time. A result more than five years after today is not written.

## Output

Each run that has something to write creates `annual_rollover_{environment}_{timestamp}.xlsx` in the current directory. Columns include the weed and visit OBJECTIDs, species, status, the date used, the existing dates, the suggestion, and what was written on each side.

## Tests

```bash
python annual_rollover/test_annual_rollover.py
```
