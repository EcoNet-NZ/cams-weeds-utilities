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
   - `DateForNextVisitFromLastVisit` ≤ October 1st (visit is due/overdue)
   - Last visit date > 2 months before October 1st

2. **Status-Specific Rules**:
   - **YellowKilledThisYear**: Update immediately (if basic eligibility met)
   - **OrangeDeadHeaded**: Update immediately (if basic eligibility met)
   - **GreenNoRegrowthThisYear**: Update only if last visit > 2 years before October 1st
   - **PinkOccupantWillKillGrowth**: Update only if last visit > 2 years before October 1st

3. **Update Actions**:
   - Set `ParentStatusWithDomain` = "PurpleHistoric"
   - Append to `audit_log`: `"{YYYY-MM-DD} Annual rollover from {PreviousStatus} to Purple; {Previous audit_log content}"`
   - **TBD**: Create backup column with original status before update

## Test Cases
*Reference Date: October 1st, 2024*

| Test Case | Species | Current Status | Next Visit Date | Last Visit Date | Expected Result | Reason |
|-----------|---------|---------------|-----------------|-----------------|-----------------|---------|
| TC01 | MothPlant | YellowKilledThisYear | 2024-01-01 | 2024-06-01 | Update to PurpleHistoric | All conditions met |
| TC02 | MothPlant | YellowKilledThisYear | 2025-01-01 | 2024-06-01 | No update | Next visit in future |
| TC03 | MothPlant | YellowKilledThisYear | 2024-01-01 | 2024-08-15 | No update | Last visit < 2 months ago |
| TC04 | OldMansBeard | OrangeDeadHeaded | 2024-01-01 | 2024-06-01 | Update to PurpleHistoric | All conditions met |
| TC05 | CathedralBells | GreenNoRegrowthThisYear | 2024-01-01 | 2023-06-01 | No update | Last visit < 2 years ago |
| TC06 | CathedralBells | GreenNoRegrowthThisYear | 2024-01-01 | 2022-06-01 | Update to PurpleHistoric | Last visit > 2 years ago |
| TC07 | Jasmine | PinkOccupantWillKillGrowth | 2024-01-01 | 2023-06-01 | No update | Last visit < 2 years ago |
| TC08 | Jasmine | PinkOccupantWillKillGrowth | 2024-01-01 | 2022-06-01 | Update to PurpleHistoric | Last visit > 2 years ago |
| TC09 | NonTargetSpecies | YellowKilledThisYear | 2024-01-01 | 2024-06-01 | No update | Species not in target list |
| TC10 | MothPlant | NonTargetStatus | 2024-01-01 | 2024-06-01 | No update | Status not in target list |
| TC11 | MothPlant | YellowKilledThisYear | 2024-12-01 | 2024-08-01 | No update | Last visit exactly 2 months ago |
| TC12 | MothPlant | GreenNoRegrowthThisYear | 2024-01-01 | 2022-10-01 | No update | Last visit exactly 2 years ago |
| TC13 | CathedralBells | GreenNoRegrowthThisYear | 2024-01-01 | 2022-09-30 | Update to PurpleHistoric | Last visit 1 day > 2 years ago |
| TC14 | Jasmine | PinkOccupantWillKillGrowth | 2024-01-01 | 2022-10-01 | No update | Last visit exactly 2 years ago |
| TC15 | Jasmine | PinkOccupantWillKillGrowth | 2024-01-01 | 2022-09-30 | Update to PurpleHistoric | Last visit 1 day > 2 years ago |
| TC16 | WoollyNightshade | GreenNoRegrowthThisYear | 2024-01-01 | 2022-10-02 | No update | Last visit 1 day < 2 years ago |
| TC17 | Elaeagnus | PinkOccupantWillKillGrowth | 2024-01-01 | 2022-10-02 | No update | Last visit 1 day < 2 years ago |

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
  - Initial status
  - Calculation fields used
  - Resultant field values
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