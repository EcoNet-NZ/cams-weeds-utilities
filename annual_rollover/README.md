# Annual Weed Instance Rollover Tool

## Overview

Automates annual status updates for weed instance records in ArcGIS Feature Layer. Updates qualifying records from Yellow/Green/Orange/Pink status to PurpleHistoric for annual re-checking.

**Reference Date**: October 1st (hardcoded to current year)

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Set up environment variables
export ARCGIS_USERNAME="your_username"
export ARCGIS_PASSWORD="your_password"
export ARCGIS_PORTAL_URL="https://your-portal.arcgis.com"

# Dry run on development (preview changes)
python annual_rollover/annual_rollover.py --env development --dry-run

# Live run on development
python annual_rollover/annual_rollover.py --env development

# Limited test run (first 100 records)
python annual_rollover/annual_rollover.py --env development --limit 100
```

## Business Logic

### Target Species
- MothPlant, OldMansBeard, CathedralBells, BananaPassionfruit
- BluePassionFlower, Jasmine, JapaneseHoneysuckle, BlueMorningGlory  
- WoollyNightshade, Elaeagnus

### Target Status Values
- **YellowKilledThisYear** - Update immediately (if basic eligibility met)
- **OrangeDeadHeaded** - Update immediately (if basic eligibility met)
- **GreenNoRegrowthThisYear** - Update only if last visit > 2 years or not set
- **PinkOccupantWillKillGrowth** - Update only if last visit > 2 years or not set

### Eligibility Criteria

A record is updated to **PurpleHistoric** when ALL conditions are met:

1. **Species**: Must be in target species list
2. **Status**: Must be in target status list
3. **Next Visit Due**: `DateForNextVisitFromLastVisit` ≤ October 1st OR null
4. **Time Criteria**: Based on status type and last visit date

### Last Visit Date Resolution

Uses coalesce logic to determine effective last visit date:
1. `DateVisitMadeFromLastVisit` (highest priority)
2. `DateOfLastCreateFromLastVisit`
3. `DateDiscovered`
4. If all null BUT target status: treat as "visited but date unknown" (eligible)
5. If all null AND non-target status: treat as "never visited" (not eligible)

## Safety Features

### Production Safeguards
- **Automatic protection**: Production updates blocked before October 1st
- **Clear error messages**: Shows days remaining until October 1st
- **Development unrestricted**: No date restrictions on development environment

### Audit Trail
- **Backup field**: Original status saved to `StatusAt202510` 
- **Audit log**: Appends rollover entry with date and previous status
- **Process tracking**: Records stored in CAMS Process Audit table

## Command Line Options

```bash
python annual_rollover/annual_rollover.py [options]

Required:
  --env {development,production}    Environment to process

Optional:
  --dry-run                        Preview changes without updating
  --limit N                        Process only first N records (testing)
```

## Output Files

### Excel Export
Generated for every run with updated records:
- **Filename**: `annual_rollover_{environment}_{timestamp}.xlsx`
- **Location**: Current directory
- **Contents**: All updated records with before/after values

**Fields included**:
- OBJECTID, SpeciesDropDown, iNatURL, RegionCode, DistrictCode
- InitialStatus, NewStatus, LastVisitDate, LastVisitSource
- NextVisitCheck, TimeCheck, NewAuditLog, UpdateTimestamp

### Console Output
```
🔄 Starting Annual Rollover on 'development' environment
📅 Reference date: 2025-10-01
✅ Safeguard check passed for development environment
🔍 Querying weed locations...
📊 Found 1,247 records with target species and status

📈 Processing Summary:
   Records queried: 1,247
   Records processed: 1,247  
   Records eligible for update: 342

🔄 Applying updates in batches of 100...
   Batch 1: 100/100 successful
   Batch 2: 100/100 successful
   Batch 3: 100/100 successful
   Batch 4: 42/42 successful

✅ Completed: 342/342 records updated successfully
📊 Exported 342 updated records to annual_rollover_development_2025-10-01_143022.xlsx
```

## Testing

### Unit Tests
```bash
# Run all tests
python annual_rollover/test_annual_rollover.py

# Run specific test
python annual_rollover/test_annual_rollover.py TestAnnualRollover.test_tc01_all_conditions_met
```

**Test Coverage**:
- 36 comprehensive test cases from requirements
- All business logic scenarios
- Edge cases and error conditions
- Date resolution logic
- Audit log formatting

### Dry Run Testing
```bash
# Preview changes on development
python annual_rollover/annual_rollover.py --env development --dry-run --limit 10

# Output shows what would be updated:
🔍 DRY RUN - Would update 8 records:
   OBJECTID 12345: YellowKilledThisYear → PurpleHistoric
   OBJECTID 12346: GreenNoRegrowthThisYear → PurpleHistoric
   ...
```

## Error Handling

- **Individual record failures**: Continue processing remaining records
- **Batch failures**: Retry with exponential backoff (3 attempts)
- **Network issues**: Automatic retry with 5-second delays
- **Detailed logging**: All errors logged with record details
- **Transaction safety**: Updates applied in batches for data integrity

## Configuration

Uses existing `spatial_field_updater/config/environment_config.json`:
```json
{
  "development": {
    "weed_locations_layer_id": "f1d9e7c7a95a4583bb3aa9918822db26",
    "audit_table_id": "eb9b12249d794244ad82e54ad42dd58e"
  },
  "production": {
    "weed_locations_layer_id": "f529d7f1928b485d8fbf5b8a8de85799",
    "audit_table_id": "eb9b12249d794244ad82e54ad42dd58e"
  }
}
```

## Dependencies

```txt
arcgis>=2.0.0              # ArcGIS API for Python
tenacity>=8.0.0            # Retry logic for robust operations
pandas>=1.3.0              # Data manipulation and Excel export
python-dateutil>=2.8.0     # Calendar date arithmetic
openpyxl>=3.0.0            # Excel file generation
```

## Scheduling

**Recommended**: Run annually on October 1st via:
- Manual execution with proper environment selection
- GitHub Actions workflow (future enhancement)
- Cron job or task scheduler

## Troubleshooting

### Common Issues

**"Production updates not allowed before October 1st"**
- This is intentional protection
- Use `--env development` for testing
- Wait until October 1st for production runs

**"Environment 'X' not found in configuration"**
- Check `spatial_field_updater/config/environment_config.json`
- Ensure environment has required `weed_locations_layer_id`

**"No features to process"**
- Normal if no records meet criteria
- Use `--dry-run` to see what would be processed
- Check species and status filtering

**"StatusAt202510 field not found"**
- Backup field needs to be created in ArcGIS layer
- Contact admin to add field to weed locations layer

### Debug Commands

```bash
# Check what records would be processed
python annual_rollover/annual_rollover.py --env development --dry-run

# Process small sample for testing  
python annual_rollover/annual_rollover.py --env development --limit 10

# Run unit tests to verify logic
python annual_rollover/test_annual_rollover.py -v
```

---

*This tool provides automated annual rollover of weed management records, ensuring consistent re-checking of treated locations while maintaining comprehensive audit trails and safety protections.*
