# CAMS Spatial Query Optimization System - Foundation

## Overview

This is the foundation implementation for the CAMS Spatial Query Optimization System, which eliminates real-time spatial queries from the CAMS dashboard by pre-calculating region and district assignments for weed locations through automated daily batch processing.

## Project Structure

```
cams-utilities/
├── src/                          # Source code modules
│   ├── __init__.py              # Main package initialization
│   ├── config/                  # Configuration management
│   │   ├── __init__.py
│   │   └── config_loader.py     # ConfigLoader class
│   ├── exceptions/              # Custom exception classes
│   │   ├── __init__.py
│   │   └── custom_exceptions.py # Domain-specific exceptions
│   └── utils/                   # Utility modules
│       ├── __init__.py
│       └── logging_setup.py     # Logging configuration
├── config/                      # Configuration files
│   ├── environment_config.json  # Environment-specific settings
│   └── field_mapping.json       # Layer field definitions
├── tests/                       # Unit tests
│   ├── __init__.py
│   ├── test_config_loader.py    # ConfigLoader tests
│   ├── test_exceptions.py       # Exception tests
│   └── test_logging.py          # Logging tests
├── docs/                        # Documentation
│   └── prp/                     # Product Requirements
│       └── 1-foundation/
│           └── PRP.md           # Foundation requirements
├── example_usage.py             # Example usage demonstration
├── requirements.txt             # Python dependencies
└── README.md                    # This file
```

## Features Implemented

### 1. Configuration Management System
- **ConfigLoader**: Centralized configuration loading and validation
- **Environment-specific configurations**: Separate settings for development and production
- **Field mapping**: Configurable field names for different layers
- **Validation**: Comprehensive validation of configuration structure
- **Caching**: Performance optimization through configuration caching

### 2. Logging Infrastructure
- **Structured logging**: JSON formatting for production environments
- **Environment-specific formatting**: Human-readable logs for development
- **Performance logging**: Decorator for function execution timing
- **Log rotation**: Automatic log file management
- **Third-party library control**: Appropriate log levels for external dependencies

### 3. Exception Handling
- **Custom exceptions**: Domain-specific error classes
- **Context preservation**: Rich error information with context
- **Exception hierarchy**: Proper inheritance structure
- **Error chaining**: Support for exception chaining

### 4. Testing Framework
- **Comprehensive unit tests**: 100% test coverage for all components
- **Integration tests**: Cross-component testing
- **Mock testing**: Isolated testing with proper mocking
- **Test fixtures**: Reusable test data and configurations

## Installation

1. **Clone the repository**:
   ```bash
   git clone <repository-url>
   cd cams-utilities
   ```

2. **Create a virtual environment**:
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

## Usage

### Basic Configuration Loading

```python
from src.config import ConfigLoader
from src.utils import setup_logging, get_logger

# Setup logging
setup_logging(environment="development", log_level="INFO")
logger = get_logger(__name__)

# Load configuration
config_loader = ConfigLoader()
dev_config = config_loader.load_environment_config("development")

# Access configuration values
arcgis_url = dev_config["arcgis_url"]
weed_layer_id = dev_config["layers"]["weed_locations"]  # Environment-specific
regions_layer_id = dev_config["layers"]["regions"]      # From shared config
districts_layer_id = dev_config["layers"]["districts"]  # From shared config
```

### Field Mapping Usage

```python
# Get field names for a layer
object_id_field = config_loader.get_field_name("weed_locations", "object_id")
edit_date_field = config_loader.get_field_name("weed_locations", "edit_date")

# Get complete layer configuration
layer_config = config_loader.get_layer_config("weed_locations")
```

### Performance Monitoring

```python
from src.utils import log_performance

@log_performance
def process_spatial_data():
    # Your processing logic here
    return "Processing completed"

result = process_spatial_data()  # Automatically logs execution time
```

### Exception Handling

```python
from src.exceptions import CAMSConfigurationError, CAMSValidationError

try:
    config = config_loader.load_environment_config("production")
except CAMSConfigurationError as e:
    logger.error(f"Configuration error: {e}")
    # Handle configuration error
except CAMSValidationError as e:
    logger.error(f"Validation error: {e}")
    # Handle validation error
```

## Configuration Files

### Environment Configuration (`config/environment_config.json`)

The configuration follows DRY principles by using shared configuration for layers that are the same across environments:

```json
{
  "shared": {
    "layers": {
      "regions": "region_boundaries_layer_id",
      "districts": "district_boundaries_layer_id"
    }
  },
  "environments": {
    "development": {
      "arcgis_url": "https://econethub.maps.arcgis.com",
      "layers": {
        "weed_locations": "dev_weed_locations_layer_id",
        "metadata": "dev_metadata_layer_id"
      },
      "logging": {
        "level": "DEBUG",
        "format": "standard"
      }
    },
    "production": {
      "arcgis_url": "https://econethub.maps.arcgis.com",
      "layers": {
        "weed_locations": "prod_weed_locations_layer_id",
        "metadata": "prod_metadata_layer_id"
      },
      "logging": {
        "level": "INFO",
        "format": "json"
      }
    }
  }
}
```

**Note:** The `ConfigLoader` automatically merges shared layers with environment-specific layers. Environment-specific layers will override shared layers if there are naming conflicts.

### Field Mapping Configuration (`config/field_mapping.json`)

```json
{
  "layers": {
    "weed_locations": {
      "fields": {
        "object_id": {
          "field_name": "OBJECTID",
          "data_type": "integer",
          "required": true
        },
        "edit_date": {
          "field_name": "EditDate_1",
          "data_type": "datetime",
          "required": true
        }
      }
    }
  }
}
```

## Testing

Run all tests:
```bash
python -m pytest tests/ -v
```

Run tests with coverage:
```bash
python -m pytest tests/ --cov=src --cov-report=html
```

Run specific test file:
```bash
python -m pytest tests/test_config_loader.py -v
```

## Development

### Running the Example

```bash
python example_usage.py
```

This will demonstrate all the foundation components working together.

### Code Quality

The project follows these quality standards:
- **Type hints**: All functions have proper type annotations
- **Documentation**: Comprehensive docstrings for all modules and functions
- **Error handling**: Proper exception handling with meaningful error messages
- **Testing**: 100% test coverage for all components
- **Logging**: Structured logging throughout the system

### Environment Variables

The system requires the following environment variables:
- `ARCGIS_USERNAME`: ArcGIS Online username
- `ARCGIS_PASSWORD`: ArcGIS Online password
- `CAMS_ENVIRONMENT`: Environment name (development/production)

## Architecture

The foundation follows these architectural principles:

### Reliability
- **Idempotent Operations**: Configuration loading can be safely repeated
- **Fail-Safe Processing**: Comprehensive error handling prevents system crashes
- **Validation**: Input validation at all system boundaries

### Maintainability
- **Configuration-Driven**: External configuration for environment-specific settings
- **Separation of Concerns**: Clear separation between configuration, logging, and exception handling
- **Comprehensive Testing**: High test coverage ensures reliability during changes

### Scalability
- **Caching**: Configuration caching for performance optimization
- **Structured Logging**: JSON logging for production monitoring
- **Modular Design**: Components can be extended independently

## Next Steps

This foundation enables the implementation of:
1. **ArcGIS Connectivity**: Secure connection to ArcGIS Online services
2. **Layer Reading**: Access to WeedLocations, Region, and District layers
3. **Spatial Processing**: Core spatial query processing engine
4. **Change Detection**: Intelligent detection of data changes
5. **Batch Processing**: Automated daily processing workflows

## Contributing

1. Follow the existing code style and patterns
2. Add comprehensive tests for new features
3. Update documentation for any changes
4. Ensure all tests pass before submitting changes

## License

This project is part of the CAMS Spatial Query Optimization System. 