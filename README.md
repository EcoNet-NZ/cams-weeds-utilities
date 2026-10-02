# CAMS Utilities

A collection of utility tools and scripts for the CAMS (Conservation Activity Management System) ArcGIS Online platform.

## Overview

This repository contains automated processing tools designed to enhance the performance and functionality of CAMS dashboards and data management workflows. Each tool is organized in its own directory with comprehensive documentation.

## Available Tools

### [Weed Maintenance](weed_maintenance/)

Daily update of weed location region, district, and effective status. One query, one write.

**Purpose**: Pre-calculate region and district assignments, and set `EffectiveStatus` to `PurpleHistoric` when a next visit is due.

**Key Features**:
- GeoPandas bulk spatial processing
- Effective status from the parent status and the next-visit date
- Incremental reads using `EditDate_1`, plus visits that became due since the last run
- No ArcGIS credits consumed for spatial operations

**Quick Start**:
```bash
pip install -r requirements.txt

export ARCGIS_USERNAME="your_username"
export ARCGIS_PASSWORD="your_password"
export ARCGIS_PORTAL_URL="https://your-portal.arcgis.com"

python weed_maintenance/weed_maintenance.py --env development
```

**Included Tools**:
- **weed_maintenance.py**: Region, district, and effective status
- **map_weed_locations.py**: Visualization tool for weed location mapping
- **map_unassigned_points.py**: Identifies and maps unassigned locations

**[View detailed documentation →](weed_maintenance/README.md)**

---

### 📱 [Field Maps Web Map Lister](field_maps_webmap_lister/)

Automated tool for identifying and cataloging ArcGIS Online Web Maps configured for use with ArcGIS Field Maps.

**Purpose**: Discovers web maps with offline capabilities, sync-enabled layers, and Field Maps-specific configurations across your organization.

**Key Features**:
- 🔍 Automated detection of Field Maps-ready web maps
- 📋 Comprehensive analysis of offline areas and sync capabilities
- 📊 Detailed reporting with export to JSON and Excel spreadsheets
- 📈 Sharing analysis (Public, Organisation, Group-specific)
- 🏷️ Tag-based and configuration-based discovery
- ⚡ High-volume batch processing for large organizations
- 🎛️ Configurable limits via environment variables

**Quick Start**:
```bash
# Set up environment
export ARCGIS_USERNAME="your_username"
export ARCGIS_PASSWORD="your_password"
export ARCGIS_PORTAL_URL="https://your-portal.arcgis.com"
export MAX_WEBMAPS="10000"  # Optional: limit number of web maps to analyze

# Run Field Maps web map analyzer
python field_maps_webmap_lister/field_maps_webmap_lister.py
```

**What it detects**:
- ✅ Web maps with offline map areas
- ✅ Sync-enabled feature layers
- ✅ Field Maps-related tags (`field maps`, `mobile`, `offline`)
- ✅ Editable layers with data collection capabilities
- ✅ Web maps with appropriate configuration for mobile use

**Outputs**:
- 📄 JSON file with detailed analysis results
- 📈 Excel spreadsheet with sharing information and clickable settings URLs
- 📋 CSV file for broader compatibility
- 📊 Console summary with statistics and sharing breakdown

**📚 [View detailed documentation →](field_maps_webmap_lister/README.md)**

---

### 🔍 [Data Quality Tools](data_quality/)

Automated tools for analyzing and monitoring data quality in CAMS.

**Purpose**: Identify data quality issues by detecting inconsistencies, missing data, and synchronization problems across related tables.

**Key Features**:
- 🔄 Weed Visits Analyzer - Date synchronization between WeedLocations and Visits_Table
- 📊 Detailed reports with statistics and percentages
- ⚠️ Identifies data quality issues requiring attention
- ✓ Validates data relationships and integrity

**Quick Start**:
```bash
# Analyze weed visits date synchronization
python data_quality/weed_visits_analyzer.py --env development
```

**📚 [View detailed documentation →](data_quality/README.md)**

---

## 🔄 Automated Workflows (GitHub Actions)

### Weed Maintenance Automation

Weed maintenance runs from a GitHub Actions workflow. The scheduled run updates production. Development is a manual run.

**Features**:
- **Scheduled Daily Runs**: Automatic execution at 00:15 NZT on production
- ⚡ **Manual Triggers**: On-demand execution with configurable options for any environment
- 🌍 **Environment Selection**: Choose development or production environment
- 📊 **Processing Modes**: Incremental (changed records) or full dataset
- 📈 **Workflow Summary**: Real-time statistics showing updated and unassigned points
- 💾 **Audit Table Storage**: Timestamps stored in ArcGIS audit table for reliable state management
- ⚡ **Streamlined**: Simplified single-job execution with minimal overhead

**Quick Setup**:
1. **Configure GitHub Secrets**: Add ArcGIS credentials for dev/prod environments
2. **Validate Configuration**: Ensure `weed_maintenance/config/environment_config.json` has required layer IDs
3. **Enable Workflow**: The scheduled run updates production. Development is a manual run.

**Manual Execution**: Go to `Actions` → `CAMS Weed Maintenance` → `Run workflow`

**[View workflow documentation →](.github/workflows/README.md)**

---

## Repository Structure

```
cams-utilities/
├── .github/
│   └── workflows/                       # GitHub Actions automation
│       ├── weed-maintenance.yml        # Daily WeedLocations maintenance
│       └── README.md                    # Workflow documentation
├── weed_maintenance/                   # Region, district, and effective status
│   ├── config/
│   │   └── environment_config.json     # Environment configurations
│   ├── README.md                        # Complete documentation
│   ├── weed_maintenance.py              # Main processing script
│   ├── map_weed_locations.py           # Visualization tool
│   └── map_unassigned_points.py        # Analysis tool
├── field_maps_webmap_lister/           # Field Maps web map discovery tool
│   ├── README.md                        # Complete documentation
│   ├── field_maps_webmap_lister.py     # Main analysis script
│   ├── test_field_maps_tool.py         # Test suite
│   └── sample_*.html/json              # Example outputs
├── README.md                           # This overview file
└── requirements.txt                    # Shared dependencies
```

## Installation

1. **Clone the repository**:
   ```bash
   git clone <repository-url>
   cd cams-utilities
   ```

2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Set up environment variables**:
   ```bash
   export ARCGIS_USERNAME="your_username"
   export ARCGIS_PASSWORD="your_password"
   export ARCGIS_PORTAL_URL="https://your-portal.arcgis.com"
   ```

## Configuration

### Environment Configuration

Weed maintenance requires environment-specific layer IDs configured in `weed_maintenance/config/environment_config.json`. See the [weed maintenance documentation](weed_maintenance/README.md#configuration) for details.

### Environment Variables

All tools require ArcGIS authentication via environment variables:

```bash
export ARCGIS_USERNAME="your_arcgis_username"
export ARCGIS_PASSWORD="your_arcgis_password"
export ARCGIS_PORTAL_URL="https://your-portal.arcgis.com"  # Optional, defaults to ArcGIS Online
```

## Dependencies

Core dependencies shared across tools:

```bash
pip install -r requirements.txt
```

- **arcgis**: ArcGIS API for Python - feature layer operations
- **tenacity**: Retry logic for robust error handling
- **geopandas**: High-performance spatial operations
- **shapely**: Geometry validation and processing
- **matplotlib**: Data visualization
- **pandas**: Data manipulation and analysis

## Development Guidelines

### Adding New Tools

1. Create a new directory for your tool: `mkdir new_tool_name/`
2. Add comprehensive README.md documentation in the tool directory
3. Update this top-level README.md to reference the new tool
4. Add any new dependencies to the shared `requirements.txt`
5. Test in development environment before production use

### Code Standards

- **Environment Safety**: All tools must support explicit environment selection
- **Error Handling**: Use robust retry logic with `@retry` decorators
- **Documentation**: Comprehensive README.md for each tool
- **Configuration**: Environment-specific configuration per tool directory
- **Logging**: Provide clear progress and error reporting

### Testing

1. Test all changes in development environment first
2. Verify environment configurations are correct
3. Ensure processing completes successfully before deployment
4. Validate data integrity after processing

## Contributing

1. Follow existing code style and patterns
2. Add comprehensive documentation for new tools
3. Test changes in development environment
4. Update this README.md when adding new tools
5. Ensure proper error handling and logging

## Support

For tool-specific issues, see the documentation in each tool's directory:
- [Weed Maintenance Documentation](weed_maintenance/README.md)

Related CAMS documentation:
- [Creating CAMS features with Easy Editor](docs/easy-editor-create-features.md)

For general repository issues, create a GitHub issue with:
- Tool name and version
- Environment (development/production)
- Error messages and logs
- Steps to reproduce

## License

This project is part of the CAMS Conservation Activity Management System.

---

*This repository provides automated tools to enhance CAMS dashboard performance and data management workflows through efficient preprocessing and analysis capabilities.* 