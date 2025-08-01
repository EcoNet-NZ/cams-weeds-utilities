# CAMS Utilities

A collection of utility tools and scripts for the CAMS (Conservation Activity Management System) ArcGIS Online platform.

## Overview

This repository contains automated processing tools designed to enhance the performance and functionality of CAMS dashboards and data management workflows. Each tool is organized in its own directory with comprehensive documentation.

## Available Tools

### 🗺️ [Spatial Field Updater](spatial_field_updater/)

High-performance automated preprocessing tool for spatial field assignment in weed location data.

**Purpose**: Eliminates real-time spatial queries during dashboard filtering by pre-calculating region and district assignments.

**Key Features**:
- 🚀 GeoPandas bulk spatial processing (2-5x faster)
- 🎯 99.98% assignment success rate with 2km nearest boundary fallback
- 📊 Advanced visualization and analysis tools
- ⚡ Intelligent change detection for incremental updates
- 🔒 No ArcGIS credits consumed for spatial operations

**Quick Start**:
```bash
# Install dependencies
pip install -r requirements.txt

# Set up environment
export ARCGIS_USERNAME="your_username"
export ARCGIS_PASSWORD="your_password"
export ARCGIS_PORTAL_URL="https://your-portal.arcgis.com"

# Run spatial field updater
python spatial_field_updater/spatial_field_updater.py --env development
```

**📚 [View detailed documentation →](spatial_field_updater/README.md)**

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

## 🔄 Automated Workflows (GitHub Actions)

### Spatial Field Updater Automation

The spatial field updater includes a comprehensive GitHub Actions workflow for automated daily processing.

**Features**:
- 🕰️ **Scheduled Daily Runs**: Automatic execution at 6 AM UTC (7-8 PM NZ time)
- ⚡ **Manual Triggers**: On-demand execution with configurable options
- 🌍 **Multi-Environment**: Separate development and production processing
- 📊 **Processing Modes**: Incremental (changed records) or full dataset
- 🗺️ **Map Generation**: Optional visualization maps and analysis reports
- 📦 **Artifact Storage**: Logs, maps, and reports retained for 30 days
- 🔔 **Error Notifications**: Failure alerts for scheduled runs

**Quick Setup**:
1. **Configure GitHub Secrets**: Add ArcGIS credentials for dev/prod environments
2. **Validate Configuration**: Ensure `spatial_field_updater/config/environment_config.json` has required layer IDs
3. **Enable Workflow**: The workflow runs automatically or can be triggered manually

**Manual Execution**: Go to `Actions` → `CAMS Spatial Field Updater` → `Run workflow`

**📚 [View workflow documentation →](.github/workflows/README.md)**

---

## Repository Structure

```
cams-utilities/
├── .github/
│   └── workflows/                       # GitHub Actions automation
│       ├── spatial-field-updater.yml   # Daily spatial processing workflow
│       └── README.md                    # Workflow documentation
├── spatial_field_updater/              # Spatial field assignment tool
│   ├── config/
│   │   └── environment_config.json     # Environment configurations
│   ├── README.md                        # Complete documentation
│   ├── spatial_field_updater.py         # Main processing script
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

The spatial field updater requires environment-specific layer IDs configured in `spatial_field_updater/config/environment_config.json`. See the [spatial field updater documentation](spatial_field_updater/README.md#configuration) for details.

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
- [Spatial Field Updater Documentation](spatial_field_updater/README.md)

For general repository issues, create a GitHub issue with:
- Tool name and version
- Environment (development/production)
- Error messages and logs
- Steps to reproduce

## License

This project is part of the CAMS Conservation Activity Management System.

---

*This repository provides automated tools to enhance CAMS dashboard performance and data management workflows through efficient preprocessing and analysis capabilities.* 