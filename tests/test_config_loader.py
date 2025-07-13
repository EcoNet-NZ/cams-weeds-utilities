"""
Unit tests for ConfigLoader class.

This module contains comprehensive tests for configuration loading,
validation, and error handling.
"""

import json
import os
import pytest
import tempfile
from pathlib import Path
from unittest.mock import patch, mock_open

from src.config import ConfigLoader
from src.exceptions import CAMSConfigurationError, CAMSValidationError


class TestConfigLoader:
    """Test suite for ConfigLoader class."""
    
    @pytest.fixture
    def temp_config_dir(self):
        """Create a temporary directory for configuration files."""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield Path(temp_dir)
    
    @pytest.fixture
    def valid_environment_config(self):
        """Valid environment configuration for testing with DRY structure."""
        return {
            "shared": {
                "layers": {
                    "regions": "shared_region_layer_id",
                    "districts": "shared_district_layer_id"
                }
            },
            "environments": {
                "development": {
                    "arcgis_url": "https://dev.arcgis.com",
                    "layers": {
                        "weed_locations": "dev_weed_id",
                        "metadata": "dev_metadata_id"
                    },
                    "logging": {
                        "level": "DEBUG",
                        "format": "standard"
                    },
                    "processing": {
                        "batch_size": 100,
                        "timeout_seconds": 300
                    }
                },
                "production": {
                    "arcgis_url": "https://prod.arcgis.com",
                    "layers": {
                        "weed_locations": "prod_weed_id",
                        "metadata": "prod_metadata_id"
                    },
                    "logging": {
                        "level": "INFO",
                        "format": "json"
                    },
                    "processing": {
                        "batch_size": 500,
                        "timeout_seconds": 600
                    }
                }
            },
            "validation": {
                "required_environment_variables": ["ARCGIS_USERNAME", "ARCGIS_PASSWORD"],
                "supported_environments": ["development", "production"]
            }
        }
    
    @pytest.fixture
    def valid_field_mapping(self):
        """Valid field mapping configuration for testing."""
        return {
            "layers": {
                "weed_locations": {
                    "fields": {
                        "object_id": {
                            "field_name": "OBJECTID",
                            "data_type": "integer",
                            "required": True
                        },
                        "edit_date": {
                            "field_name": "EditDate_1",
                            "data_type": "datetime",
                            "required": True
                        }
                    },
                    "validation": {
                        "required_fields": ["OBJECTID", "EditDate_1"]
                    }
                },
                "regions": {
                    "fields": {
                        "object_id": {
                            "field_name": "OBJECTID",
                            "data_type": "integer",
                            "required": True
                        },
                        "region_code": {
                            "field_name": "REGC_code",
                            "data_type": "string",
                            "required": True
                        }
                    },
                    "validation": {
                        "required_fields": ["OBJECTID", "REGC_code"]
                    }
                }
            },
            "data_types": {
                "integer": {"python_type": "int"},
                "string": {"python_type": "str"},
                "datetime": {"python_type": "datetime"}
            }
        }
    
    @pytest.fixture
    def config_loader(self, temp_config_dir):
        """Create ConfigLoader instance with temporary directory."""
        return ConfigLoader(config_dir=str(temp_config_dir))
    
    def test_init_default_config_dir(self):
        """Test ConfigLoader initialization with default config directory."""
        loader = ConfigLoader()
        assert loader.config_dir == Path("config")
    
    def test_init_custom_config_dir(self, temp_config_dir):
        """Test ConfigLoader initialization with custom config directory."""
        loader = ConfigLoader(config_dir=str(temp_config_dir))
        assert loader.config_dir == temp_config_dir
    
    def test_load_environment_config_success(self, config_loader, temp_config_dir, valid_environment_config):
        """Test successful loading of environment configuration with shared layers."""
        # Write valid configuration file
        env_config_path = temp_config_dir / "environment_config.json"
        with open(env_config_path, 'w') as f:
            json.dump(valid_environment_config, f)
        
        # Load development configuration
        config = config_loader.load_environment_config("development")
        
        assert config["arcgis_url"] == "https://dev.arcgis.com"
        assert config["layers"]["weed_locations"] == "dev_weed_id"
        assert config["layers"]["regions"] == "shared_region_layer_id"  # From shared
        assert config["layers"]["districts"] == "shared_district_layer_id"  # From shared
        assert config["layers"]["metadata"] == "dev_metadata_id"
        assert config["logging"]["level"] == "DEBUG"
        assert "_validation" in config
    
    def test_load_environment_config_shared_override(self, config_loader, temp_config_dir):
        """Test that environment-specific layers override shared layers."""
        config_with_override = {
            "shared": {
                "layers": {
                    "regions": "shared_region_layer_id",
                    "weed_locations": "shared_weed_id"  # This should be overridden
                }
            },
            "environments": {
                "development": {
                    "arcgis_url": "https://dev.arcgis.com",
                    "layers": {
                        "weed_locations": "dev_weed_id",  # This overrides shared
                        "metadata": "dev_metadata_id",
                        "districts": "dev_district_id"
                    },
                    "logging": {"level": "DEBUG", "format": "standard"},
                    "processing": {"batch_size": 100, "timeout_seconds": 300}
                }
            },
            "validation": {
                "required_environment_variables": ["ARCGIS_USERNAME"],
                "supported_environments": ["development"]
            }
        }
        
        # Write configuration file
        env_config_path = temp_config_dir / "environment_config.json"
        with open(env_config_path, 'w') as f:
            json.dump(config_with_override, f)
        
        # Load configuration
        config = config_loader.load_environment_config("development")
        
        # Environment-specific should override shared
        assert config["layers"]["weed_locations"] == "dev_weed_id"
        # Shared should still be present
        assert config["layers"]["regions"] == "shared_region_layer_id"
        # Environment-specific should be present
        assert config["layers"]["districts"] == "dev_district_id"
    
    def test_load_environment_config_file_not_found(self, config_loader):
        """Test loading environment configuration when file doesn't exist."""
        with pytest.raises(CAMSConfigurationError) as exc_info:
            config_loader.load_environment_config("development")
        
        assert "Environment configuration file not found" in str(exc_info.value)
    
    def test_load_environment_config_invalid_json(self, config_loader, temp_config_dir):
        """Test loading environment configuration with invalid JSON."""
        # Write invalid JSON file
        env_config_path = temp_config_dir / "environment_config.json"
        with open(env_config_path, 'w') as f:
            f.write("{ invalid json }")
        
        with pytest.raises(CAMSConfigurationError) as exc_info:
            config_loader.load_environment_config("development")
        
        assert "Invalid JSON in environment configuration" in str(exc_info.value)
    
    def test_load_environment_config_missing_environment(self, config_loader, temp_config_dir, valid_environment_config):
        """Test loading non-existent environment configuration."""
        # Write valid configuration file
        env_config_path = temp_config_dir / "environment_config.json"
        with open(env_config_path, 'w') as f:
            json.dump(valid_environment_config, f)
        
        with pytest.raises(CAMSConfigurationError) as exc_info:
            config_loader.load_environment_config("staging")
        
        assert "Environment 'staging' not found" in str(exc_info.value)
    
    def test_load_field_mapping_success(self, config_loader, temp_config_dir, valid_field_mapping):
        """Test successful loading of field mapping configuration."""
        # Write valid field mapping file
        field_mapping_path = temp_config_dir / "field_mapping.json"
        with open(field_mapping_path, 'w') as f:
            json.dump(valid_field_mapping, f)
        
        # Load field mapping
        mapping = config_loader.load_field_mapping()
        
        assert "layers" in mapping
        assert "weed_locations" in mapping["layers"]
        assert "data_types" in mapping
    
    def test_load_field_mapping_file_not_found(self, config_loader):
        """Test loading field mapping when file doesn't exist."""
        with pytest.raises(CAMSConfigurationError) as exc_info:
            config_loader.load_field_mapping()
        
        assert "Field mapping configuration file not found" in str(exc_info.value)
    
    def test_get_layer_config_success(self, config_loader, temp_config_dir, valid_field_mapping):
        """Test successful retrieval of layer configuration."""
        # Write valid field mapping file
        field_mapping_path = temp_config_dir / "field_mapping.json"
        with open(field_mapping_path, 'w') as f:
            json.dump(valid_field_mapping, f)
        
        layer_config = config_loader.get_layer_config("weed_locations")
        
        assert "fields" in layer_config
        assert "validation" in layer_config
        assert "object_id" in layer_config["fields"]
    
    def test_get_layer_config_not_found(self, config_loader, temp_config_dir, valid_field_mapping):
        """Test retrieval of non-existent layer configuration."""
        # Write valid field mapping file
        field_mapping_path = temp_config_dir / "field_mapping.json"
        with open(field_mapping_path, 'w') as f:
            json.dump(valid_field_mapping, f)
        
        with pytest.raises(CAMSConfigurationError) as exc_info:
            config_loader.get_layer_config("invalid_layer")
        
        assert "Layer 'invalid_layer' not found" in str(exc_info.value)
    
    def test_get_field_name_success(self, config_loader, temp_config_dir, valid_field_mapping):
        """Test successful retrieval of field name."""
        # Write valid field mapping file
        field_mapping_path = temp_config_dir / "field_mapping.json"
        with open(field_mapping_path, 'w') as f:
            json.dump(valid_field_mapping, f)
        
        field_name = config_loader.get_field_name("weed_locations", "object_id")
        
        assert field_name == "OBJECTID"
    
    def test_get_field_name_not_found(self, config_loader, temp_config_dir, valid_field_mapping):
        """Test retrieval of non-existent field name."""
        # Write valid field mapping file
        field_mapping_path = temp_config_dir / "field_mapping.json"
        with open(field_mapping_path, 'w') as f:
            json.dump(valid_field_mapping, f)
        
        with pytest.raises(CAMSConfigurationError) as exc_info:
            config_loader.get_field_name("weed_locations", "invalid_field")
        
        assert "Field 'invalid_field' not found" in str(exc_info.value)
    
    @patch.dict(os.environ, {"ARCGIS_USERNAME": "test", "ARCGIS_PASSWORD": "test"})
    def test_validate_environment_variables_success(self, config_loader, temp_config_dir, valid_environment_config):
        """Test successful validation of environment variables."""
        # Write valid configuration file
        env_config_path = temp_config_dir / "environment_config.json"
        with open(env_config_path, 'w') as f:
            json.dump(valid_environment_config, f)
        
        # Should not raise any exception
        config_loader.validate_environment_variables("development")
    
    @patch.dict(os.environ, {}, clear=True)
    def test_validate_environment_variables_missing(self, config_loader, temp_config_dir, valid_environment_config):
        """Test validation with missing environment variables."""
        # Write valid configuration file
        env_config_path = temp_config_dir / "environment_config.json"
        with open(env_config_path, 'w') as f:
            json.dump(valid_environment_config, f)
        
        with pytest.raises(CAMSValidationError) as exc_info:
            config_loader.validate_environment_variables("development")
        
        assert "Missing required environment variables" in str(exc_info.value)
    
    def test_validate_environment_config_missing_environments(self, config_loader):
        """Test validation with missing environments key."""
        invalid_config = {"invalid": "config"}
        
        with pytest.raises(CAMSValidationError) as exc_info:
            config_loader._validate_environment_config(invalid_config, "development")
        
        assert "Missing 'environments' key" in str(exc_info.value)
    
    def test_validate_environment_config_missing_keys(self, config_loader):
        """Test validation with missing required keys."""
        invalid_config = {
            "environments": {
                "development": {
                    "arcgis_url": "https://test.com"
                    # Missing required keys
                }
            }
        }
        
        with pytest.raises(CAMSValidationError) as exc_info:
            config_loader._validate_environment_config(invalid_config, "development")
        
        assert "Missing required key" in str(exc_info.value)
    
    def test_validate_environment_config_missing_layers_with_shared(self, config_loader):
        """Test validation correctly handles missing layers when using shared configuration."""
        config_missing_layers = {
            "shared": {
                "layers": {
                    "regions": "shared_region_id"
                    # Missing districts
                }
            },
            "environments": {
                "development": {
                    "arcgis_url": "https://test.com",
                    "layers": {
                        "weed_locations": "dev_weed_id"
                        # Missing metadata
                    },
                    "logging": {"level": "DEBUG", "format": "standard"},
                    "processing": {"batch_size": 100, "timeout_seconds": 300}
                }
            }
        }
        
        with pytest.raises(CAMSValidationError) as exc_info:
            config_loader._validate_environment_config(config_missing_layers, "development")
        
        assert "Missing required layers" in str(exc_info.value)
        assert "districts" in str(exc_info.value)
        assert "metadata" in str(exc_info.value)
    
    def test_validate_field_mapping_missing_layers(self, config_loader):
        """Test validation with missing layers key."""
        invalid_mapping = {"data_types": {}}
        
        with pytest.raises(CAMSValidationError) as exc_info:
            config_loader._validate_field_mapping(invalid_mapping)
        
        assert "Missing 'layers' key" in str(exc_info.value)
    
    def test_validate_field_mapping_missing_data_types(self, config_loader):
        """Test validation with missing data_types key."""
        invalid_mapping = {"layers": {}}
        
        with pytest.raises(CAMSValidationError) as exc_info:
            config_loader._validate_field_mapping(invalid_mapping)
        
        assert "Missing 'data_types' key" in str(exc_info.value)
    
    def test_clear_cache(self, config_loader, temp_config_dir, valid_environment_config, valid_field_mapping):
        """Test cache clearing functionality."""
        # Write configuration files
        env_config_path = temp_config_dir / "environment_config.json"
        with open(env_config_path, 'w') as f:
            json.dump(valid_environment_config, f)
        
        field_mapping_path = temp_config_dir / "field_mapping.json"
        with open(field_mapping_path, 'w') as f:
            json.dump(valid_field_mapping, f)
        
        # Load configurations to populate cache
        config_loader.load_environment_config("development")
        config_loader.load_field_mapping()
        
        # Clear cache
        config_loader.clear_cache()
        
        # Verify cache is cleared by checking cache info
        assert config_loader.load_environment_config.cache_info().currsize == 0
        assert config_loader.load_field_mapping.cache_info().currsize == 0
    
    def test_configuration_caching(self, config_loader, temp_config_dir, valid_environment_config):
        """Test that configuration is properly cached."""
        # Write valid configuration file
        env_config_path = temp_config_dir / "environment_config.json"
        with open(env_config_path, 'w') as f:
            json.dump(valid_environment_config, f)
        
        # Load configuration twice
        config1 = config_loader.load_environment_config("development")
        config2 = config_loader.load_environment_config("development")
        
        # Should return the same object (cached)
        assert config1 is config2
        assert config_loader.load_environment_config.cache_info().hits == 1 