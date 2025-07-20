# Field Maps Web Map Lister

Automated tool for identifying and cataloging ArcGIS Online Web Maps configured for use with ArcGIS Field Maps.

## Overview

The Field Maps Web Map Lister analyzes your ArcGIS Online organization to identify web maps that are configured for use with ArcGIS Field Maps. It detects offline capabilities, sync-enabled layers, and other Field Maps-specific configurations, providing a comprehensive inventory of your Field Maps-ready content.

## Key Features

- **🔍 Automated Detection**: Identifies Field Maps-ready web maps across your organization
- **📋 Comprehensive Analysis**: Examines offline areas, sync capabilities, and layer configurations
- **📊 Detailed Reporting**: Generates summary reports and exports results to JSON and HTML
- **🌐 Interactive HTML Tables**: Creates professional HTML reports with clickable links to web map settings
- **🏷️ Smart Discovery**: Uses tag-based and configuration-based detection methods
- **⚡ Batch Processing**: Efficiently processes multiple web maps simultaneously
- **🎯 Flexible Filtering**: Supports custom search queries and filters

## What It Detects

### Primary Indicators
- ✅ **Offline Map Areas**: Web maps with pre-configured offline areas for Field Maps
- ✅ **Sync-Enabled Layers**: Feature services with synchronization capabilities
- ✅ **Editable Layers**: Layers that support Create, Update, Delete operations

### Secondary Indicators
- 🏷️ **Field Maps Tags**: Web maps tagged with `field maps`, `mobile`, `offline`, etc.
- 📱 **Mobile Configuration**: Web maps optimized for mobile data collection
- 🔄 **Offline Properties**: Web maps with offline-specific settings

## Installation & Setup

### Prerequisites
- Python 3.7+
- ArcGIS Python API (tested with version 2.4+)
- Valid ArcGIS Online credentials with appropriate permissions

**Note**: This tool works with the core ArcGIS Python API and does not require the additional `arcgis-mapping` package. Offline area detection is available if the `OfflineMapAreaManager` is accessible in your ArcGIS Python API installation.

### Environment Setup
```bash
# Set required environment variables
export ARCGIS_USERNAME="your_username"
export ARCGIS_PASSWORD="your_password"
export ARCGIS_PORTAL_URL="https://your-portal.arcgis.com"  # Optional, defaults to ArcGIS Online
```

## Usage

### Basic Usage

#### Simple Analysis
```bash
# Run the main analyzer
python field_maps_webmap_lister.py
```

#### Quick Examples
```bash
# Use simple example functions
python field_maps_examples.py
```

### Advanced Usage

#### Custom Search Queries
```python
from field_maps_webmap_lister import FieldMapsWebMapAnalyzer
from arcgis.gis import GIS

gis = GIS()
analyzer = FieldMapsWebMapAnalyzer(gis)

# Search specific tags
results = analyzer.find_field_maps_webmaps(
    search_query='tags:"field maps"',
    max_items=50
)

# Search by owner
results = analyzer.find_field_maps_webmaps(
    search_query='owner:your_username',
    max_items=25
)

# Search by title keywords
results = analyzer.find_field_maps_webmaps(
    search_query='title:mobile OR title:data collection',
    max_items=30
)
```

#### Programmatic Analysis
```python
from field_maps_webmap_lister import FieldMapsWebMapAnalyzer, export_field_maps_html_report
from arcgis.gis import GIS

# Connect to ArcGIS Online
gis = GIS("https://your-portal.com", "username", "password")

# Initialize analyzer
analyzer = FieldMapsWebMapAnalyzer(gis)

# Find Field Maps web maps
results = analyzer.find_field_maps_webmaps(search_query="tags:field maps", max_items=50)

# Display results
analyzer.print_summary(results)

# Export to both JSON and HTML
analyzer.export_results(results)
analyzer.export_html_table(results, portal_url="https://your-portal.com")

# Generate HTML report for specific portal
from field_maps_webmap_lister import export_field_maps_html_report
export_field_maps_html_report(
    gis, 
    search_query='tags:"field maps"',
    portal_url="https://econethub.maps.arcgis.com"
)
```

## Output & Results

### Console Output
The tool provides real-time feedback during analysis:

```
Searching for web maps with query: '*'
Found 45 web maps to analyze
Analyzing 1/45: Mobile Data Collection Map
  ✓ Field Maps enabled: Has offline map areas, Has sync-enabled layers
Analyzing 2/45: Basic Reference Map
  ✗ No Field Maps indicators found
...

============================================================
FIELD MAPS WEB MAPS SUMMARY
============================================================
Total Field Maps-enabled web maps found: 8

Title                                    Owner           Offline Areas    Editable Layers
---------------------------------------- --------------- ------------ ---------------
Mobile Data Collection Map               admin           3            5
Field Survey Map                         surveyor        1            3
Inspection Checklist                     inspector       0            2
...
```

### JSON Export
Results are automatically exported to `field_maps_webmaps.json`:

```json
[
  {
    "item_id": "abc123def456",
    "title": "Mobile Data Collection Map",
    "owner": "admin",
    "is_field_maps_enabled": true,
    "offline_enabled": true,
    "has_offline_areas": true,
    "offline_areas_count": 3,
    "editable_layers": 5,
    "total_layers": 8,
    "field_maps_indicators": [
      "Has offline map areas",
      "Has sync-enabled layers",
      "Has relevant tag: mobile"
    ],
    "tags": ["mobile", "data collection", "field maps"],
    "created": "2024-01-15T10:30:00Z",
    "modified": "2024-01-20T14:45:00Z"
  }
]
```

### HTML Export
The tool also generates a professional HTML report (`field_maps_webmaps.html`) featuring:

- **📊 Summary Dashboard**: Overview statistics with visual indicators
- **📋 Interactive Table**: Sortable, responsive table with web map details
- **🔗 Clickable Links**: Direct links to web map settings pages (e.g., `https://econethub.maps.arcgis.com/home/item.html?id=abc123def456#settings`)
- **🎨 Professional Styling**: Clean, modern design suitable for presentations
- **📱 Mobile Responsive**: Works on desktop, tablet, and mobile devices

The HTML table includes:
- Web map name (linked to settings page)
- Item ID for reference
- Owner information
- Field Maps indicators as visual tags
- Statistics (total layers, editable layers, offline areas)
- Last modified date

Example link format: `https://your-portal.maps.arcgis.com/home/item.html?id={item_id}#settings`

## Analysis Criteria

### Field Maps Enablement Logic
A web map is considered "Field Maps-enabled" if it meets **any** of these criteria:

1. **Has Offline Areas**: Pre-configured offline map areas exist
2. **Has Sync-Enabled Layers**: Contains feature services with sync capabilities
3. **Has Editable Layers**: Contains layers supporting Create/Update/Delete operations
4. **Has Field Maps Tags**: Tagged with relevant keywords (`field maps`, `mobile`, `offline`)
5. **Has Offline Configuration**: Contains offline-specific settings in web map definition

### Detection Methods

#### Offline Area Detection
```python
# Check for existing offline areas using OfflineMapAreaManager
try:
    from arcgis.mapping import OfflineMapAreaManager
    offline_mgr = OfflineMapAreaManager(webmap_item, gis)
    offline_areas = offline_mgr.list()
    has_offline_areas = len(offline_areas) > 0
except Exception:
    # Fallback if offline area manager not available
    has_offline_areas = False
```

#### Layer Capability Analysis
```python
# Check layer editing capabilities using web map definition
webmap_data = webmap_item.get_data()
operational_layers = webmap_data.get('operationalLayers', [])

for layer in operational_layers:
    layer_url = layer.get('url', '')
    
    # Check if it's a feature service (potential for editing/sync)
    if 'FeatureServer' in layer_url:
        # Try to get the actual layer to check capabilities
        layer_item = gis.content.get(layer.get('itemId', ''))
        if layer_item and layer_item.layers:
            layer_obj = layer_item.layers[0]
            if hasattr(layer_obj, 'properties'):
                capabilities = getattr(layer_obj.properties, 'capabilities', '')
                if any(cap in str(capabilities) for cap in ['Create', 'Update', 'Delete']):
                    editable_count += 1
```

#### Tag-Based Detection
```python
# Field Maps-related tags
field_maps_tags = [
    'field maps', 'fieldmaps', 'mobile', 
    'offline', 'data collection'
]
```

## Configuration Options

### Search Parameters
- **search_query**: Custom search query (default: `"*"` for all web maps)
- **max_items**: Maximum number of web maps to analyze (default: 100)
- **sort_field**: Field to sort results by (default: "modified")
- **sort_order**: Sort order (default: "desc")

### Analysis Settings
- **include_basic_webmaps**: Include web maps without clear Field Maps indicators
- **strict_mode**: Only include web maps with strong Field Maps indicators
- **export_format**: Output format for results (JSON, CSV, etc.)

## Common Use Cases

### 1. Organization Audit
Identify all Field Maps-ready web maps across your organization:
```python
results = analyzer.find_field_maps_webmaps(search_query="*", max_items=200)
```

### 2. User-Specific Analysis
Find Field Maps web maps for a specific user:
```python
results = analyzer.find_field_maps_webmaps(
    search_query="owner:field_worker_username",
    max_items=50
)
```

### 3. Tag-Based Discovery
Find web maps specifically tagged for Field Maps:
```python
results = analyzer.find_field_maps_webmaps(
    search_query='tags:"field maps" OR tags:"mobile"',
    max_items=100
)
```

### 4. Recent Activity Review
Analyze recently modified web maps:
```python
quick_field_maps_audit(gis, max_items=20)
```

## Troubleshooting

### Common Issues

#### Authentication Errors
```
Error: Please set ARCGIS_USERNAME and ARCGIS_PASSWORD environment variables
```
**Solution**: Ensure environment variables are properly set:
```bash
export ARCGIS_USERNAME="your_username"
export ARCGIS_PASSWORD="your_password"
```

#### Permission Errors
```
Error analyzing web map: Access denied
```
**Solution**: Ensure your account has permission to access the web maps being analyzed.

#### Network Timeouts
**Solution**: Reduce the `max_items` parameter or run analysis in smaller batches.

### Debug Mode
Enable verbose output for troubleshooting:
```python
from arcgis import env
env.verbose = True
```

## Best Practices

### Performance Optimization
1. **Batch Size**: Limit `max_items` to 50-100 for large organizations
2. **Targeted Searches**: Use specific search queries to reduce analysis scope
3. **Incremental Analysis**: Focus on recently modified web maps first

### Search Strategy
1. **Start Broad**: Begin with `search_query="*"` to get overall picture
2. **Refine Searches**: Use targeted queries based on initial results
3. **User-Focused**: Analyze specific users or groups first

### Data Management
1. **Regular Audits**: Run analysis monthly to track Field Maps adoption
2. **Export Results**: Keep historical records of Field Maps web map inventory
3. **Tag Standardization**: Encourage consistent tagging practices

## Integration with CAMS

This tool integrates with the CAMS utilities ecosystem:

- **Environment Configuration**: Uses shared `config/environment_config.json`
- **Authentication**: Uses standard CAMS environment variables
- **Reporting**: Compatible with existing CAMS reporting workflows

## API Reference

### FieldMapsWebMapAnalyzer Class

#### Methods
- `__init__(gis)`: Initialize with GIS connection
- `analyze_webmap_for_field_maps(webmap_item)`: Analyze single web map
- `find_field_maps_webmaps(search_query, max_items)`: Find and analyze web maps
- `export_results(results, output_file)`: Export results to JSON file
- `export_html_table(results, output_file, portal_url)`: Export results to HTML table
- `print_summary(results)`: Display summary of results

#### Properties
- `gis`: GIS connection object
- `field_maps_webmaps`: List of analyzed web maps

**Note**: This tool is compatible with ArcGIS Python API 2.4+ and works with the core API without requiring additional mapping packages. It analyzes web map items directly through the GIS content API for maximum compatibility.

### Example Functions
- `simple_field_maps_search(gis)`: Basic tag-based search
- `check_offline_capabilities(gis, webmap_id)`: Analyze specific web map
- `list_your_field_maps_webmaps(gis)`: Find your Field Maps web maps
- `quick_field_maps_audit(gis, max_items)`: Quick audit of recent web maps
- `export_field_maps_html_report(gis, search_query, max_items, portal_url)`: Generate HTML report

## Support

For issues specific to the Field Maps Web Map Lister:

1. Check environment variables are correctly set
2. Verify ArcGIS Online credentials and permissions
3. Review search queries for syntax errors
4. Check network connectivity for large analyses

For general CAMS utilities support, see the main [README](README.md).

---

*Part of the CAMS Conservation Activity Management System utilities collection.* 