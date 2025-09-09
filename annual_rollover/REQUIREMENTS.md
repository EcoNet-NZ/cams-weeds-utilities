# Annual Weed Instance Rollover - Requirements Document

## Overview
Automate annual status updates for weed instance records in ArcGIS Feature Layer based on business rules, with comprehensive logging and error handling.

## Configuration
- **Layer ID**: Use existing `weed_locations_layer_id` from `spatial_field_updater/config/environment_config.json`
- **Environment Support**: Development/production environment selection
- **Authentication**: ArcGIS credentials via environment variables

## Target Species
Process records where `SpeciesDropDown` equals:
- MothPlant
- OldMansBeard  
- CathedralBells
- BananaPassionfruit
- BluePassionFlower
- Jasmine
- JapaneseHoneysuckle
- BlueMorningGlory
- WoollyNightshade
- Elaeagnus

## Target Status Values
Process records where `ParentStatusWithDomain` equals:
- YellowKilledThisYear
- GreenNoRegrowthThisYear
- OrangeDeadHeaded
- PinkOccupantWillKillGrowth

## Business Logic
For each qualifying record, update to **PurpleHistoric** when ALL conditions are met:

1. **Basic Eligibility**:
   - `SpeciesDropDown` in target species list
   - `ParentStatusWithDomain` in target status list
   - Next visit is due/overdue: `DateForNextVisitFromLastVisit` ≤ October 1st OR `DateForNextVisitFromLastVisit` is null
   - Last visit date > 2 months before October 1st

**Field Logic**:
- **Next Visit Date**: `DateForNextVisitFromLastVisit`
  - If date ≤ October 1st: weed is due for visit (eligible for rollover)
  - If null: weed should be visited (eligible for rollover)
  - If date > October 1st: visit not due yet (not eligible)
- **Last Visit Date**: First non-null value from:
  1. `DateVisitMadeFromLastVisit` 
  2. `DateOfLastCreateFromLastVisit`
  3. `DateDiscovered`
  4. If all null BUT status is Yellow/Green/Orange/Pink: treat as "visited but date unknown" (eligible for rollover)
  5. If all null AND status is not target status: treat as "never visited" (not eligible)

2. **Status-Specific Rules**:
   - **YellowKilledThisYear**: Update immediately (if basic eligibility met)
   - **OrangeDeadHeaded**: Update immediately (if basic eligibility met)
   - **GreenNoRegrowthThisYear**: Update only if last visit > 2 years before October 1st or is not set
   - **PinkOccupantWillKillGrowth**: Update only if last visit > 2 years before October 1st or is not set

3. **Update Actions**:
   - Set `ParentStatusWithDomain` = "PurpleHistoric"
   - Append to `audit_log`: `"{YYYY-MM-DD} Annual rollover from {PreviousStatus} to Purple; {Previous audit_log content}"`
   - **TBD**: Create backup column with original status before update

## Test Cases
*Reference Date: October 1st, 2025*

| Test Case | Species | Current Status | DateForNextVisitFromLastVisit | Last Visit Date (Resolved) | Expected Result | Reason |
|-----------|---------|---------------|-------------------------------|----------------------------|-----------------|---------|
| TC01 | MothPlant | YellowKilledThisYear | 2025-01-01 | 2025-06-01 | Update to PurpleHistoric | All conditions met |
| TC02 | MothPlant | YellowKilledThisYear | 2026-01-01 | 2025-06-01 | No update | Next visit in future |
| TC03 | MothPlant | YellowKilledThisYear | 2025-01-01 | 2025-08-15 | No update | Last visit < 2 months ago |
| TC04 | OldMansBeard | OrangeDeadHeaded | 2025-01-01 | 2025-06-01 | Update to PurpleHistoric | All conditions met |
| TC05 | CathedralBells | GreenNoRegrowthThisYear | 2025-01-01 | 2024-06-01 | No update | Last visit < 2 years ago |
| TC06 | CathedralBells | GreenNoRegrowthThisYear | 2025-01-01 | 2023-06-01 | Update to PurpleHistoric | Last visit > 2 years ago |
| TC07 | Jasmine | PinkOccupantWillKillGrowth | 2025-01-01 | 2024-06-01 | No update | Last visit < 2 years ago |
| TC08 | Jasmine | PinkOccupantWillKillGrowth | 2025-01-01 | 2023-06-01 | Update to PurpleHistoric | Last visit > 2 years ago |
| TC09 | NonTargetSpecies | YellowKilledThisYear | 2025-01-01 | 2025-06-01 | No update | Species not in target list |
| TC10 | MothPlant | NonTargetStatus | 2025-01-01 | 2025-06-01 | No update | Status not in target list |
| TC11 | MothPlant | YellowKilledThisYear | 2025-12-01 | 2025-08-01 | No update | Last visit exactly 2 months ago |
| TC12 | MothPlant | GreenNoRegrowthThisYear | 2025-01-01 | 2023-10-01 | No update | Last visit exactly 2 years ago |
| TC13 | CathedralBells | GreenNoRegrowthThisYear | 2025-01-01 | 2023-09-30 | Update to PurpleHistoric | Last visit 1 day > 2 years ago |
| TC14 | Jasmine | PinkOccupantWillKillGrowth | 2025-01-01 | 2023-10-01 | No update | Last visit exactly 2 years ago |
| TC15 | Jasmine | PinkOccupantWillKillGrowth | 2025-01-01 | 2023-09-30 | Update to PurpleHistoric | Last visit 1 day > 2 years ago |
| TC16 | WoollyNightshade | GreenNoRegrowthThisYear | 2025-01-01 | 2023-10-02 | No update | Last visit 1 day < 2 years ago |
| TC17 | Elaeagnus | PinkOccupantWillKillGrowth | 2025-01-01 | 2023-10-02 | No update | Last visit 1 day < 2 years ago |
| TC18 | MothPlant | YellowKilledThisYear | null | 2025-06-01 | Update to PurpleHistoric | Null next visit = eligible |
| TC19 | OldMansBeard | OrangeDeadHeaded | null | 2025-06-01 | Update to PurpleHistoric | Null next visit = eligible |
| TC20 | MothPlant | YellowKilledThisYear | 2025-01-01 | null (no visit dates) | Update to PurpleHistoric | Yellow status = visited, treat as eligible |
| TC21 | CathedralBells | GreenNoRegrowthThisYear | null | null (no visit dates) | Update to PurpleHistoric | Green status = visited, treat as eligible |

## Last Visit Date Resolution Test Cases
*Testing the coalesce logic for determining the effective last visit date*

| Test Case | DateVisitMadeFromLastVisit | DateOfLastCreateFromLastVisit | DateDiscovered | Expected Last Visit Date | Reason |
|-----------|---------------------------|------------------------------|----------------|-------------------------|---------|
| LV01 | 2025-06-01 | 2025-05-01 | 2025-04-01 | 2025-06-01 | First field takes priority |
| LV02 | null | 2025-05-01 | 2025-04-01 | 2025-05-01 | Second field when first is null |
| LV03 | null | null | 2025-04-01 | 2025-04-01 | Third field when first two null |
| LV04 | null | null | null | null | All fields null = never visited |
| LV05 | 2025-06-01 | null | null | 2025-06-01 | Only first field populated |
| LV06 | null | 2025-05-01 | null | 2025-05-01 | Only second field populated |
| LV07 | null | null | 2025-04-01 | 2025-04-01 | Only third field populated |
| LV08 | 2025-06-01 | null | 2025-04-01 | 2025-06-01 | First field wins over third |
| LV09 | null | 2025-05-01 | 2025-04-01 | 2025-05-01 | Second field wins over third |
| LV10 | 2025-06-01 | 2025-07-01 | 2025-04-01 | 2025-06-01 | First field wins even if older |

## Combined Logic Test Cases
*Testing complete rollover logic with various last visit date combinations*

| Test Case | Species | Status | DateForNextVisit | DateVisitMade | DateOfLastCreate | DateDiscovered | Expected Result | Reason |
|-----------|---------|--------|------------------|---------------|------------------|----------------|-----------------|---------|
| CL01 | MothPlant | YellowKilledThisYear | 2025-01-01 | 2025-06-01 | null | null | Update to PurpleHistoric | Uses DateVisitMade, > 2 months |
| CL02 | MothPlant | YellowKilledThisYear | 2025-01-01 | null | 2025-06-01 | null | Update to PurpleHistoric | Uses DateOfLastCreate, > 2 months |
| CL03 | MothPlant | YellowKilledThisYear | 2025-01-01 | null | null | 2025-06-01 | Update to PurpleHistoric | Uses DateDiscovered, > 2 months |
| CL04 | MothPlant | YellowKilledThisYear | 2025-01-01 | null | null | null | Update to PurpleHistoric | Yellow status = visited, treat as eligible |
| CL05 | MothPlant | YellowKilledThisYear | 2025-01-01 | 2025-08-15 | 2025-06-01 | 2025-05-01 | No update | Uses DateVisitMade, < 2 months |
| CL06 | MothPlant | YellowKilledThisYear | 2025-01-01 | null | 2025-08-15 | 2025-06-01 | No update | Uses DateOfLastCreate, < 2 months |
| CL07 | MothPlant | YellowKilledThisYear | 2025-01-01 | null | null | 2025-08-15 | No update | Uses DateDiscovered, < 2 months |
| CL08 | CathedralBells | GreenNoRegrowthThisYear | 2025-01-01 | 2023-06-01 | null | null | Update to PurpleHistoric | Uses DateVisitMade, > 2 years |
| CL09 | CathedralBells | GreenNoRegrowthThisYear | 2025-01-01 | null | 2023-06-01 | null | Update to PurpleHistoric | Uses DateOfLastCreate, > 2 years |
| CL10 | CathedralBells | GreenNoRegrowthThisYear | 2025-01-01 | null | null | 2023-06-01 | Update to PurpleHistoric | Uses DateDiscovered, > 2 years |
| CL11 | CathedralBells | GreenNoRegrowthThisYear | 2025-01-01 | 2024-06-01 | 2023-06-01 | 2022-06-01 | No update | Uses DateVisitMade, < 2 years |
| CL12 | CathedralBells | GreenNoRegrowthThisYear | 2025-01-01 | null | 2024-06-01 | 2023-06-01 | No update | Uses DateOfLastCreate, < 2 years |
| CL13 | CathedralBells | GreenNoRegrowthThisYear | 2025-01-01 | null | null | 2024-06-01 | No update | Uses DateDiscovered, < 2 years |
| CL14 | MothPlant | YellowKilledThisYear | null | 2025-06-01 | 2025-05-01 | 2025-04-01 | Update to PurpleHistoric | Null next visit + DateVisitMade > 2 months |
| CL15 | MothPlant | YellowKilledThisYear | null | null | null | null | Update to PurpleHistoric | Yellow status = visited, null next visit = eligible |

## Technical Requirements

### Performance
- **Batch Processing**: Handle ~50,000 records efficiently
- **Error Handling**: Log failures, continue processing remaining records
- **Retry Logic**: Use tenacity decorators for ArcGIS operations

### Execution Modes
- **Dry Run**: Preview changes without updating (`--dry-run`)
- **Record Limit**: Process fixed number for testing (`--limit N`)
- **Environment Selection**: `--env development|production`

### Logging & Output
- **Console Logging**: Progress, errors, summary statistics
- **Spreadsheet Export**: Excel file with all updated records containing:
  - OBJECTID
  - SpeciesDropDown
  - iNatURL
  - RegionCode
  - DistrictCode
  - Initial status (ParentStatusWithDomain before update)
  - Calculation fields used (resolved last visit date, next visit date)
  - Resultant field values (new ParentStatusWithDomain, updated audit_log)
  - Update timestamp

### Scheduling
- **Run Frequency**: Annually on October 1st
- **Execution**: Manual trigger with proper environment selection

## Error Handling
- Continue processing on individual record failures
- Log all errors with record details
- Generate summary report of successes/failures
- Maintain data integrity with transaction-safe updates

## Dependencies
- ArcGIS API for Python (>=2.4.0)
- pandas for data manipulation
- tenacity for retry logic
- openpyxl for Excel export
- Existing environment configuration pattern 