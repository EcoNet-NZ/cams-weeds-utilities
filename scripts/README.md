# Simple Spatial Update Script

A minimal implementation for populating RegionCode and DistrictCode fields for weed locations through spatial intersection, with simple change detection.

## Usage

```bash
# Set environment variables
export ARCGIS_USERNAME="your_username"
export ARCGIS_PASSWORD="your_password"
export ARCGIS_PORTAL_URL="https://your-portal.arcgis.com"

# Process only changed features in development environment (default mode)
python scripts/simple_spatial_update.py --env development

# Process all features in production environment
python scripts/simple_spatial_update.py --env production --mode all

# Process changed features in staging environment
python scripts/simple_spatial_update.py --env staging --mode changed

# Alternative environment flag syntax
python scripts/simple_spatial_update.py --environment development
```

## What it does

1. Connects to ArcGIS using environment variables
2. Gets weed locations layer from specified environment configuration
3. Gets region and district boundary layers
4. Queries features based on mode (all vs changed since last run)
5. For each feature, finds intersecting region and district
6. Updates RegionCode and DistrictCode fields only if values changed
7. Applies updates in batches of 100
8. Saves last run timestamp for change detection

## Key Features

- **Environment selection** via CLI parameter (development, staging, production, etc.)
- **Simple change detection** using EditDate_1 field and file-based last run tracking
- **CLI options** for processing all vs changed features only
- **Smart updates** - only updates fields when values actually change
- **Simple retry logic** using `@retry` decorators (3 attempts, 5-second delays)
- **Batch processing** for efficient updates
- **Minimal dependencies** (just `arcgis` and `tenacity`)
- **Clean, readable code** with decorators handling complexity

## Command Line Options

| Option | Description | Required | Default |
|--------|-------------|----------|---------|
| `--env`, `--environment` | Environment to use (from config file) | ✓ Required | None |
| `--mode {all,changed}` | Process all features or only changed ones | Optional | `changed` |

## Environment Configuration

The script reads all layer IDs from `config/environment_config.json`:

```json
{
  "development": {
    "weed_locations_layer_id": "f1d9e7c7a95a4583bb3aa9918822db26",
    "region_layer_id": "7759fbaecd4649dea39c4ac2b07fc4ab",
    "district_layer_id": "c8f6ba6b968c4d31beddfb69abfe3df0"
  },
  "staging": {
    "weed_locations_layer_id": "staging_weed_locations_layer_id",
    "region_layer_id": "7759fbaecd4649dea39c4ac2b07fc4ab",
    "district_layer_id": "c8f6ba6b968c4d31beddfb69abfe3df0"
  },
  "production": {
    "weed_locations_layer_id": "prod_weed_locations_layer_id",
    "region_layer_id": "7759fbaecd4649dea39c4ac2b07fc4ab",
    "district_layer_id": "c8f6ba6b968c4d31beddfb69abfe3df0"
  }
}
```

**Required fields per environment:**
- `weed_locations_layer_id` - The weed locations feature layer for this environment
- `region_layer_id` - The regions boundary layer (typically same across environments)
- `district_layer_id` - The districts boundary layer (typically same across environments)

## Change Detection Logic

### File-based Tracking
- Last run timestamp stored in `scripts/.last_run`
- Uses `EditDate_1 > last_run_timestamp` for incremental processing
- Falls back to processing all features if no previous run found

### Smart Updates
- Only updates features where RegionCode or DistrictCode actually changed
- Compares current field values with spatial query results
- Avoids unnecessary writes to unchanged features

## Example Runs

### Development Environment - First Run
```bash
$ python scripts/simple_spatial_update.py --env development
Starting spatial update on 'development' (changed features only)...
No previous run found, processing all features
Query: 1=1
Processing 1000 weed locations...
Found 950 features needing updates
...
Completed: 950 features updated successfully
```

### Production Environment - Incremental Update
```bash
$ python scripts/simple_spatial_update.py --env production --mode changed
Starting spatial update on 'production' (changed features only)...
Query: EditDate_1 > timestamp '2024-01-15 14:30:22'
Processing 25 weed locations...
Found 20 features needing updates
...
Completed: 20 features updated successfully
```

### Staging Environment - Force Full Processing
```bash
$ python scripts/simple_spatial_update.py --env staging --mode all
Starting spatial update on 'staging' (all features)...
Query: 1=1
Processing 5000 weed locations...
Found 15 features needing updates
...
Completed: 15 features updated successfully
```

### Error Handling - Invalid Environment
```bash
$ python scripts/simple_spatial_update.py --env invalid
ValueError: Environment 'invalid' not found. Available: ['development', 'staging', 'production']
```

## Comparison: Simple vs Full Implementation

| Feature | Simple Script | Full Implementation |
|---------|---------------|-------------------|
| **Lines of Code** | ~197 lines | ~3,000+ lines |
| **Files** | 1 file + 1 timestamp file | 15+ files |
| **Performance** | Basic (2 queries per feature) | Optimized (1 bulk query) |
| **Error Handling** | @retry decorators | Comprehensive validation |
| **Change Detection** | EditDate_1 field + file tracking | Layer metadata + comprehensive tracking |
| **Environment Selection** | CLI parameter | Configuration file |
| **Metadata Tracking** | Simple timestamp file | Comprehensive with history |
| **Validation** | Field value comparison | Pre-update validation |
| **Rollback** | None | Automatic on failures |
| **Monitoring** | Basic progress prints | Performance metrics |
| **Configuration** | Configurable layer IDs + CLI options | Flexible JSON config |
| **Testing** | None | Unit + integration tests |

## Code Simplification with @retry

### Before (Manual Retry Logic)
```python
def connect_arcgis():
    for attempt in range(MAX_RETRIES):
        try:
            return GIS(portal_url, username, password)
        except Exception as e:
            if attempt < MAX_RETRIES - 1:
                print(f"Connection attempt {attempt + 1} failed, retrying...")
                time.sleep(RETRY_DELAY)
            else:
                raise Exception(f"Failed to connect after {MAX_RETRIES} attempts: {e}")
```

### After (@retry Decorator)
```python
@retry(stop=stop_after_attempt(3), wait=wait_fixed(5))
def connect_arcgis():
    return GIS(portal_url, username, password)
```

**Result**: Eliminated 20+ lines of manual retry logic, making the code much cleaner and more readable.

## Trade-offs

### Simple Script Benefits
- **Very easy to understand** - Single file, straightforward logic
- **Quick to modify** - No complex abstractions
- **Minimal dependencies** - Just ArcGIS API + tenacity
- **Fast to implement** - Can be written in 1 hour
- **Clean retry logic** - @retry decorators handle all complexity
- **Basic change detection** - Avoids reprocessing unchanged data
- **Flexible CLI** - Easy to choose processing mode and environment
- **Environment safety** - Explicit environment selection prevents accidents
- **Configurable layer IDs** - All layer IDs can be changed via config file

### Simple Script Limitations
- **Poor performance** - 2 spatial queries per weed location
- **File-based tracking** - Not as robust as database metadata
- **Basic error handling** - May fail on edge cases
- **No monitoring** - Limited visibility into processing
- **No validation** - Could corrupt data if layers change
- **Simple change tracking** - Only uses EditDate_1, not layer metadata

### When to Use Each

**Use Simple Script When:**
- Dataset is small-medium (<5,000 records)
- Occasional processing needs
- Quick prototyping or testing
- Simple requirements
- Team values simplicity over performance
- Need basic change detection
- Multiple environments need basic processing

**Use Full Implementation When:**
- Large datasets (>5,000 records)
- Regular automated processing
- Production environment
- Performance matters
- Data integrity is critical
- Monitoring and maintenance required
- Complex change detection needs

## Performance Example

For 10,000 weed locations:

### First Run (All Features)
- **Simple Script**: ~20,000 spatial queries (2 per feature) = ~10-15 minutes
- **Full Implementation**: ~2,000 spatial queries (optimized batching) = ~2-3 minutes

### Incremental Run (100 Changed Features)
- **Simple Script**: ~200 spatial queries = ~30 seconds
- **Full Implementation**: ~20 spatial queries = ~5 seconds

*Change detection provides significant performance improvement for incremental processing*

## Dependencies

```bash
pip install arcgis tenacity
```

The `tenacity` library provides the clean `@retry` decorators that eliminate manual retry logic. 