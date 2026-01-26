# CAMS Data Quality Tools

## Weed Visits Analyzer

Analyzes and corrects field synchronization issues between WeedLocations and Visits_Table using metadata-driven rules.

### Features

- **Metadata-driven rules**: Easy to add new field comparisons without code changes
- **Three correction modes**: Fix WeedLocations, Visits, or both
- **Smart batching**: Efficient bulk updates (500 records per API call)
- **Preview mode**: See what would change before applying
- **Detailed logging**: Track all changes with before/after values
- **VisitDataSource tracking**: Identify where mismatches originate

### Quick Start

```bash
# Install dependencies
pip install -r ../requirements.txt

# Set credentials
export ARCGIS_USERNAME="your_username"
export ARCGIS_PASSWORD="your_password"

# Analyze only (generate report)
python weed_visits_analyzer.py --env development

# Preview all corrections
python weed_visits_analyzer.py --env development --correct-all --preview

# Apply all corrections
python weed_visits_analyzer.py --env development --correct-all

# List available field rules
python weed_visits_analyzer.py --list-fields
```

### Command Line Options

#### Analysis Options
- `--env ENVIRONMENT`: Environment to analyze (development or production)
- `--output FILE` / `-o FILE`: Custom output file path (default: auto-generated)
- `--ignore-dates`: Skip audit fields (CreationDate_1 and EditDate_1)
- `--list-fields`: List all available field rules and exit

#### Correction Options
- `--correct-weed-from-visits`: Update WeedLocations to match latest Visit data
- `--correct-visits`: Fix Visits_Table internal issues (e.g., set DateCheck from CreationDate_1)
- `--correct-visits-from-weed`: Update latest Visits from WeedLocations (e.g., copy ParentStatusWithDomain → WeedVisitStatus)
- `--correct-all`: Apply all three correction types
- `--preview`: Preview corrections without making changes
- `--fields "Field1,Field2"`: Correct only specific WeedLocations fields (use with --correct-weed-from-visits)

### How "Latest" Visit is Determined

The analyzer identifies the **single latest visit** per weed location using:

**Strategy**: `DateCheck → CreationDate_1`
1. Prefers visits with `DateCheck` set (sorted by most recent)
2. Falls back to `CreationDate_1` if DateCheck is null
3. All field comparisons use this same "latest" visit

### Three Rule Types

#### 1. FIELD_COMPARISON_RULES (WeedLocations ↔ Visits)
Compares WeedLocations fields to their latest visit data:

| Field | WeedLocations | Visits_Table | Special Rules |
|-------|---------------|--------------|---------------|
| Urgency | Urgency | DifficultyChild | - |
| Status | ParentStatusWithDomain | WeedVisitStatus | Ignores Purple* statuses |
| Date Visit Made | DateVisitMadeFromLastVisit | DateCheck | - |
| Date For Next Visit | DateForNextVisitFromLastVisit | DateForReturnVisit | - |
| Visit Stage | LatestVisitStage | VisitStage | - |
| Area | LatestArea | Area | - |
| Creation Date | DateOfLastCreateFromLastVisit | CreationDate_1 | Ignores bulk load date† |
| Edit Date | DateOfLastEditFromLastVisit | EditDate_1 | - |

#### 2. VISIT_CORRECTION_RULES (Internal Visit fixes)
Fixes data quality issues within Visits_Table (all visits):
- **DateCheck from CreationDate**: Sets DateCheck from CreationDate_1 when empty (excludes bulk load date)

#### 3. VISIT_FROM_WEED_RULES (Visits ← WeedLocations)
Updates latest visit fields from WeedLocations data:
- **Status from WeedLocation**: Copies ParentStatusWithDomain → WeedVisitStatus when empty (excludes Purple statuses)

**Special Values:**
- *Purple statuses: Set by Daily/Annual Rollover, intentionally different
- †Bulk load date: `2021-10-09 21:19:26` (initial data migration timestamp)

### Output Files

#### Analysis Report
`weed_visits_field_comparison_{env}_{timestamp}.xlsx` with sheets:
1. **Overall Summary** - Total counts and percentages
2. **Field Pair Summary** - Mismatches per field with reference date strategy
3. **Mismatch by DataSource** - Breakdown by VisitDataSource (shows where issues originate)
4. **Detailed Mismatches** - Rows with differences, includes:
   - Mismatch_Summary: Explanation of all mismatches for each record
   - Visit_Reference_Date_Field: Which date field determined "latest"
   - VisitDataSource: Source of the visit data
5. **Missing Visit Date** - Visits where DateCheck is not set
6. **Missing Status** - Visits where WeedVisitStatus is not set
7. **All Records** - Complete dataset

#### Correction Logs (when using correction flags)
- `visit_corrections_{preview|applied}_{env}_{timestamp}.xlsx` - Visit internal fixes
- `visit_from_weed_corrections_{preview|applied}_{env}_{timestamp}.xlsx` - Visits updated from WeedLocations
- `weed_visits_corrections_{preview|applied}_{env}_{timestamp}.xlsx` - WeedLocations updated from Visits
- `weed_visits_field_comparison_{env}_after_corrections_{timestamp}.xlsx` - Post-correction analysis

**Excel Formatting**:
- All dates in ISO 8601 format (YYYY-MM-DD HH:MM:SS)
- Mismatched Visit values prefixed with **← ** and shown in **bold**
- Correction logs include Update_Status (Success/Failed) and error details

### Configuration

Edit `environment_config.json` to set WeedLocations layer IDs:

```json
{
  "development": {
    "weed_locations_layer_id": "your_dev_layer_id"
  },
  "production": {
    "weed_locations_layer_id": "your_prod_layer_id"
  }
}
```

Visits_Table is automatically discovered from the WeedLocations feature service.

### Correction Modes

#### 1. WeedLocations from Visits (`--correct-weed-from-visits`)
Updates WeedLocations to match latest Visit data
- Uses: FIELD_COMPARISON_RULES
- Supports: `--fields` to correct specific fields only

#### 2. Visits Internal (`--correct-visits`)
Fixes Visits_Table internal issues (all visits)
- Sets DateCheck from CreationDate_1 when empty
- Excludes bulk load date records

#### 3. Visits from WeedLocations (`--correct-visits-from-weed`)
Updates latest Visits from WeedLocations
- Copies ParentStatusWithDomain → WeedVisitStatus when empty
- Excludes Purple statuses

#### 4. All Corrections (`--correct-all`)
Applies all three in optimal order with automatic data reload between steps.

**Safety**: Preview mode (`--preview`), confirmation prompts, detailed logging, post-correction verification

### Typical Workflow

```bash
# 1. Analyze - generate baseline report
python weed_visits_analyzer.py --env development

# 2. Preview - see what would change
python weed_visits_analyzer.py --env development --correct-all --preview

# 3. Apply - fix the issues (type 'YES' at prompts)
python weed_visits_analyzer.py --env development --correct-all

# 4. Review - check post-correction report
# Opens: weed_visits_field_comparison_{env}_after_corrections_{timestamp}.xlsx
```

### More Examples

```bash
# Apply individual correction types
python weed_visits_analyzer.py --env development --correct-weed-from-visits
python weed_visits_analyzer.py --env development --correct-visits
python weed_visits_analyzer.py --env development --correct-visits-from-weed

# Correct specific WeedLocations fields only
python weed_visits_analyzer.py --env development --correct-weed-from-visits --fields "Urgency,Area"

# Skip audit fields in analysis
python weed_visits_analyzer.py --env development --ignore-dates

# List all field rules
python weed_visits_analyzer.py --list-fields
```

### Adding New Rules

The analyzer uses metadata-driven rules. To add a new field comparison:

1. Add entry to `FIELD_COMPARISON_RULES`:
```python
{
  'weed_field': 'FieldNameInWeedLocations',
  'visit_field': 'FieldNameInVisits',
  'display_name': 'Human Readable Name',
  'mismatch_column': 'FieldName_Mismatch',
  'ignore_condition': lambda weed_val, visit_val: False,  # Optional
  'description': 'Explanation of what this checks',
  'category': 'optional_category'  # e.g., 'audit'
}
```

2. That's it! The rule automatically:
   - Appears in reports
   - Works with `--correct-weed-from-visits`
   - Shows in `--list-fields` output

### Performance

- **Batched queries**: Loads data in chunks (2000 records/batch)
- **Auto-recovery**: Retries failed batches with smaller sizes
- **Batched updates**: 500 records per API call
- **Progress logging**: Shows real-time update progress

Typical performance:
- Analysis: 60,000 weed locations + 200,000 visits = ~2-3 minutes
- Corrections: 10,000 updates = ~1 minute (vs hours with one-at-a-time)

## Files

- `weed_visits_analyzer.py` - Main analysis and correction tool
- `environment_config.json` - Environment configuration
- `README.md` - This file

## Support

For issues, check:
1. ArcGIS credentials are set correctly
2. Environment exists in `environment_config.json`
3. WeedLocations layer ID is correct
4. You have read access to the feature service
