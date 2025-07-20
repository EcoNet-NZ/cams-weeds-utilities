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

## Repository Structure

```
cams-utilities/
├── config/
│   └── environment_config.json         # Shared environment configurations
├── spatial_field_updater/              # Spatial field assignment tool
│   ├── README.md                        # Complete documentation
│   ├── spatial_field_updater.py         # Main processing script
│   ├── map_weed_locations.py           # Visualization tool
│   └── map_unassigned_points.py        # Analysis tool
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

Tools in this repository read layer IDs and settings from `config/environment_config.json`:

```json
{
  "development": {
    "weed_locations_layer_id": "development_layer_id",
    "region_layer_id": "7759fbaecd4649dea39c4ac2b07fc4ab",
    "district_layer_id": "c8f6ba6b968c4d31beddfb69abfe3df0"
  },
  "production": {
    "weed_locations_layer_id": "production_layer_id",
    "region_layer_id": "7759fbaecd4649dea39c4ac2b07fc4ab",
    "district_layer_id": "c8f6ba6b968c4d31beddfb69abfe3df0"
  }
}
```

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
- **Configuration**: Use the shared config/environment_config.json format
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