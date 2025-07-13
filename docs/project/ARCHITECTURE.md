# CAMS Spatial Query Optimization - System Architecture

## Overview

This document defines the architecture for the CAMS Spatial Query Optimization system, which eliminates real-time spatial queries from the CAMS dashboard by pre-calculating region and district assignments for weed locations through automated daily batch processing.

## Business Context

- **Problem**: CAMS dashboard experiences slow response times due to real-time spatial queries when filtering 50,000+ weed records by region/district
- **Solution**: Daily batch processing to pre-calculate spatial relationships
- **Benefit**: Sub-second dashboard response times and improved user experience

## Architecture Principles

### Reliability
- **Idempotent Operations**: All processes can be safely rerun without data corruption
- **Fail-Safe Processing**: No metadata updates on any processing failures
- **Incremental Processing**: Only process changed data to minimize resource usage

### Maintainability
- **Configuration-Driven**: External configuration files for environment-specific settings
- **Environment Separation**: Clear separation between development and production
- **Logging and Monitoring**: Comprehensive process tracking and status reporting

### Scalability
- **Extensible Design**: Architecture supports future additional area layers
- **Batch Processing**: Optimized for handling growing data volumes
- **Resource Efficiency**: Minimal processing through change detection

## System Architecture

### High-Level Components

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   GitHub        │    │   Spatial Query  │    │   ArcGIS Online │
│   Actions       │───▶│   Processor      │───▶│   CAMS System   │
│   (Scheduler)   │    │   (Python)       │    │   (Data Store)  │
└─────────────────┘    └──────────────────┘    └─────────────────┘
                                                       │
                                                       ├─ WeedLocations
                                                       ├─ Region Layer
                                                       ├─ District Layer
                                                       └─ Metadata Table
```

### Technology Stack

- **Python 3.12**: Latest version supported by ArcGIS API for Python
- **ArcGIS API for Python**: Latest stable version for ArcGIS Online integration
- **Tenacity**: Retry patterns for API resilience
- **func_timeout**: Request timeouts for reliability
- **python-dateutil**: Date parsing and timezone handling
- **pytz**: NZT timezone support for scheduling

### Project Structure

```
cams-spatial-optimization/
├── config/                          # Configuration management
│   ├── spatial_config.json         # Layer mapping and processing rules
│   ├── environment_config.json     # Environment-specific settings
│   └── field_mapping.json          # ArcGIS field definitions
├── src/
│   ├── __init__.py
│   ├── main.py                     # Entry point and orchestration
│   ├── processor/                  # Core processing logic
│   │   ├── __init__.py
│   │   ├── spatial_processor.py   # Main spatial query engine
│   │   ├── change_detector.py     # Incremental processing logic
│   │   └── metadata_manager.py    # Status and version tracking
│   ├── connectors/                 # External system integration
│   │   ├── __init__.py
│   │   ├── arcgis_connector.py    # ArcGIS Online interface
│   │   └── layer_handler.py       # Feature layer read/write operations
│   ├── models/                     # Data models and validation
│   │   ├── __init__.py
│   │   ├── weed_location.py       # WeedLocation data model
│   │   └── process_metadata.py    # Metadata table model
│   ├── utils/                      # Shared utilities
│   │   ├── __init__.py
│   │   ├── config_loader.py       # Configuration management
│   │   ├── logger.py              # Logging setup
│   │   └── exceptions.py          # Custom exceptions
│   └── tests/                      # Unit and integration tests
│       ├── __init__.py
│       ├── test_spatial_processor.py
│       ├── test_change_detector.py
│       ├── test_layer_integration.py  # Integration tests for layer access
│       └── fixtures/
├── .github/
│   └── workflows/
│       └── spatial-optimization.yml # GitHub Actions workflow
├── requirements.txt                 # Direct dependencies
├── requirements_lock.txt           # Pinned dependencies
└── README.md                       # Project documentation
```

## Data Architecture

### Source Systems

#### WeedLocations Layer
**Purpose**: Primary feature layer containing weed instances with spatial and temporal data

**Key Fields for Spatial Processing**:
- OBJECTID: Primary key for feature identification
- GlobalID: Unique identifier for relationships
- RegionCode: 2-character region assignment (target field)
- DistrictCode: 5-character district assignment (target field)
- EditDate_1: Change detection timestamp field
- geometry: Spatial coordinates for intersection queries

*Note: Layer contains additional weed management fields not listed here*

#### Area Layers Configuration

**Region Layer**:
- Layer ID: 7759fbaecd4649dea39c4ac2b07fc4ab
- Purpose: Region boundary polygons for spatial intersection
- Source Code Field: REGC_code (contains region codes to assign)
- Target Field: RegionCode (2-character field in WeedLocations)

**District Layer**:
- Layer ID: c8f6ba6b968c4d31beddfb69abfe3df0
- Purpose: District boundary polygons for spatial intersection
- Source Code Field: TALB_code (contains district codes to assign)
- Target Field: DistrictCode (5-character field in WeedLocations)

*Note: Layer IDs are consistent across development and production environments*

### Metadata Store

#### Weeds Area Metadata Table (ArcGIS Online)
**Purpose**: Track processing status and layer versions for dashboard consumption

**Fields**:
- ProcessTimestamp (Date): Process start time
- RegionLayerID (Text, 50): Region layer identifier
- RegionLayerUpdated (Date): Region layer version timestamp
- DistrictLayerID (Text, 50): District layer identifier
- DistrictLayerUpdated (Date): District layer version timestamp
- ProcessStatus (Text, 20): 'Success' or 'Error'
- RecordsProcessed (Integer): Count of updated records

**Environment Naming:**
- Production: `Weeds Area Metadata`
- Development: `XXX Weeds Area Metadata DEV`

## Core Processing Architecture

### Processing Workflow

**Main Process Flow:**
1. **Change Detection**: Compare layer metadata and check EditDate_1 for modified weeds
2. **Spatial Analysis**: Perform intersection queries between weed locations and area boundaries
3. **Assignment Updates**: Update RegionCode and DistrictCode fields in WeedLocations
4. **Metadata Recording**: Write processing status and layer versions to metadata table

### Processing Components

**SpatialProcessor**: Main orchestrator managing the complete workflow with error handling and coordination between components.

**ChangeDetector**: Identifies which records require processing by:
- Comparing current area layer "Date updated" with stored metadata
- Finding weeds modified since last processing via EditDate_1
- Determining full reprocessing (layer changes) vs incremental (weed changes)

**ArcGISConnector**: Handles all ArcGIS Online interactions with retry logic, timeouts, and batch processing for API reliability and performance.

**MetadataManager**: Manages status tracking and layer version recording, only writing metadata on successful completion.

### Dry-Run Mode

**Purpose**: Enable testing and validation without data modification
**Implementation**: Command-line flag `--dry-run` that:
- Performs all spatial queries and change detection
- Logs all planned updates without executing them
- Validates processing logic and configuration
- Reports potential changes and processing metrics

## Configuration Management

### Environment Configuration

**Purpose**: Separate development and production settings for safe testing and deployment.

**Environment Settings**:
- WeedLocations layer IDs for each environment
- Metadata table names (with DEV suffix for development)
- GitHub secrets suffixes for authentication

**Area Layer Configuration**:
- Layer IDs and field mappings for region and district boundaries
- Extensible structure for future additional area layers
- Code field mappings between area layers and WeedLocations

### Field Mapping Configuration

**Purpose**: Define ArcGIS field names and validation rules for consistent data access.

**Key Mappings**:
- RegionCode: 2-character target field in WeedLocations
- DistrictCode: 5-character target field in WeedLocations  
- EditDate_1: Change detection timestamp field in WeedLocations
- REGC_code: Source field in Region layer containing region codes
- TALB_code: Source field in District layer containing district codes

## Deployment Architecture

### GitHub Actions Workflow

**Schedule**: Daily at 9:05pm NZT via cron schedule
**Triggers**: Automated schedule and manual dispatch for testing
**Strategy**: Matrix deployment for both development and production environments
**Timeout**: 120 minutes maximum execution time

**Key Features**:
- Python 3.12 runtime environment
- Environment-specific secret management
- Artifact collection for processing logs
- Parallel execution for dev/prod environments

### Dependency Management

**Dependabot Configuration**: Automated dependency updates with weekly scanning for security vulnerabilities and version updates.

**Dependency Strategy**:
- requirements.txt: Direct dependencies with flexible version ranges
- requirements_lock.txt: Pinned versions for reproducible builds
- Automated security vulnerability scanning
- Weekly dependency update checks

### Environment Protection

**Validation Strategy**: Runtime validation ensures operations target the correct environment and prevent accidental cross-environment data modifications.

**Protection Mechanisms**:
- Metadata table name validation against environment
- Layer ID verification for environment consistency
- Fail-fast validation on startup to prevent incorrect operations

## Error Handling and Monitoring

### Error Handling Strategy

**Fail-Safe Processing**: Any processing error prevents metadata table updates to ensure dashboard accuracy.

**Exception Categories**:
- SpatialQueryException: Spatial intersection query failures
- UpdateFailedException: Feature update operation failures  
- ConfigurationException: Invalid configuration or environment setup

**Recovery Strategy**: Process terminates on any error with detailed logging for troubleshooting. Manual intervention required for resolution.

### Logging Strategy

**Structured Logging**: Consistent log format with timestamps, severity levels, and component identification.

**Log Categories**:
- Summary logs for dashboard consumption and monitoring
- Detailed processing logs for troubleshooting
- Performance metrics for optimization

### Testing Strategy

**Unit Testing**: Comprehensive unit tests for individual components with mocked ArcGIS interactions.

**Integration Testing**: Tests for external system interactions and layer validation.

**Test Coverage**:
- Change detection logic validation
- Spatial query processing logic
- Configuration management
- Error handling scenarios
- Dry-run mode validation
- Layer metadata "Date updated" retrieval
- ArcGIS Online connectivity and authentication
- Field mapping validation against actual layer schemas

## Security Considerations

### Secrets Management
- **GitHub Repository Secrets**: Environment-specific ArcGIS credentials
- **Secret Naming Convention**: 
  - Development: `ARCGIS_USERNAME_DEV`, `ARCGIS_PASSWORD_DEV`
  - Production: `ARCGIS_USERNAME`, `ARCGIS_PASSWORD`

### Data Protection
- **Environment Isolation**: Strict separation between dev/prod data
- **Schema Validation**: Runtime validation of metadata table environment
- **Read-Only Dependencies**: No modifications to area boundary layers

## Performance Considerations

### Optimization Strategies
- **Incremental Processing**: Only process changed records
- **Batch Operations**: Group updates to minimize API calls
- **Spatial Query Optimization**: Use appropriate spatial relationship filters
- **Connection Reuse**: Maintain persistent ArcGIS connections

### Scalability Metrics
- **Current Scale**: 50,000 weed locations
- **Growth Rate**: 20,000 records/year
- **Processing Window**: 2-hour maximum execution time
- **Batch Size**: 100 records per update operation

## Future Extensibility

### Additional Area Layers

The architecture supports future area layers through configuration

### Metadata Schema Evolution

The metadata table design accommodates additional layers through configuration-driven field management, supporting dynamic addition of new area layer tracking without schema modifications.