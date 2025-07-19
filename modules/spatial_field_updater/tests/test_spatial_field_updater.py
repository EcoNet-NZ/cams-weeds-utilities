"""Tests for SpatialFieldUpdater class implementation."""

import pytest
import json
import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import Mock, patch, mock_open

from src.interfaces.module_processor import ProcessingResult, ModuleStatus
from modules.spatial_field_updater.processor.spatial_field_updater import SpatialFieldUpdater


class TestSpatialFieldUpdater:
    """Test cases for SpatialFieldUpdater class."""
    
    @pytest.fixture
    def mock_config_loader(self):
        """Create a mock ConfigLoader for testing."""
        mock = Mock()
        mock.load_environment_config.return_value = {
            "development": {"weed_locations_layer_id": "test-layer"}
        }
        mock.load_field_mapping.return_value = {
            "layers": {"weed_locations": {"fields": {}}}
        }
        return mock
    
    @pytest.fixture
    def valid_module_config(self):
        """Create valid module configuration for testing."""
        return {
            "area_layers": {
                "region": {
                    "layer_id": "region-layer-123",
                    "source_code_field": "REGC_code",
                    "target_field": "RegionCode",
                    "description": "Region boundaries"
                },
                "district": {
                    "layer_id": "district-layer-456",
                    "source_code_field": "TALB_code",
                    "target_field": "DistrictCode",
                    "description": "District boundaries"
                }
            },
            "processing": {
                "batch_size": 100,
                "max_retries": 3,
                "timeout_seconds": 1800,
                "spatial_relationship": "intersects"
            },
            "metadata_table": {
                "production_name": "Weeds Area Metadata",
                "development_name": "XXX Weeds Area Metadata DEV"
            },
            "validation": {
                "required_fields": ["object_id", "global_id", "geometry"],
                "field_mappings": {
                    "object_id": "OBJECTID",
                    "global_id": "GlobalID"
                }
            }
        }
    
    def test_initialization(self, mock_config_loader):
        """Test SpatialFieldUpdater initialization."""
        updater = SpatialFieldUpdater(mock_config_loader)
        
        assert updater.config_loader is mock_config_loader
        assert updater.connector is None
        assert updater._last_run is None
        assert updater._module_config is None
        assert updater._configuration_valid is None
    
    @patch("builtins.open", new_callable=mock_open)
    @patch("json.load")
    def test_load_module_config_success(self, mock_json_load, mock_file_open, 
                                       mock_config_loader, valid_module_config):
        """Test successful module configuration loading."""
        mock_json_load.return_value = valid_module_config
        
        updater = SpatialFieldUpdater(mock_config_loader)
        config = updater._load_module_config()
        
        assert config == valid_module_config
        mock_file_open.assert_called_once()
        mock_json_load.assert_called_once()
    
    @patch("builtins.open", side_effect=FileNotFoundError())
    def test_load_module_config_file_not_found(self, mock_file_open, mock_config_loader):
        """Test module configuration loading when file is not found."""
        updater = SpatialFieldUpdater(mock_config_loader)
        
        with pytest.raises(FileNotFoundError):
            updater._load_module_config()
    
    @patch("builtins.open", new_callable=mock_open, read_data="invalid json")
    @patch("json.load", side_effect=json.JSONDecodeError("msg", "doc", 0))
    def test_load_module_config_invalid_json(self, mock_json_load, mock_file_open, 
                                           mock_config_loader):
        """Test module configuration loading with invalid JSON."""
        updater = SpatialFieldUpdater(mock_config_loader)
        
        with pytest.raises(ValueError, match="Invalid JSON in configuration file"):
            updater._load_module_config()
    
    @patch("modules.spatial_field_updater.processor.spatial_field_updater.SpatialFieldUpdater._load_module_config")
    def test_validate_configuration_success(self, mock_load_config, mock_config_loader, 
                                          valid_module_config):
        """Test successful configuration validation."""
        mock_load_config.return_value = valid_module_config
        
        updater = SpatialFieldUpdater(mock_config_loader)
        result = updater.validate_configuration()
        
        assert result is True
        assert updater._configuration_valid is True
        
        # Test caching - should not load config again
        result2 = updater.validate_configuration()
        assert result2 is True
        mock_load_config.assert_called_once()
    
    @patch("modules.spatial_field_updater.processor.spatial_field_updater.SpatialFieldUpdater._load_module_config")
    def test_validate_configuration_missing_section(self, mock_load_config, 
                                                   mock_config_loader):
        """Test configuration validation with missing required section."""
        incomplete_config = {"area_layers": {}}  # Missing other required sections
        mock_load_config.return_value = incomplete_config
        
        updater = SpatialFieldUpdater(mock_config_loader)
        result = updater.validate_configuration()
        
        assert result is False
        assert updater._configuration_valid is False
    
    @patch("modules.spatial_field_updater.processor.spatial_field_updater.SpatialFieldUpdater._load_module_config")
    def test_validate_configuration_missing_layer_type(self, mock_load_config, 
                                                      mock_config_loader, valid_module_config):
        """Test configuration validation with missing layer type."""
        # Remove district layer
        config = valid_module_config.copy()
        del config["area_layers"]["district"]
        mock_load_config.return_value = config
        
        updater = SpatialFieldUpdater(mock_config_loader)
        result = updater.validate_configuration()
        
        assert result is False
        assert updater._configuration_valid is False
    
    @patch("modules.spatial_field_updater.processor.spatial_field_updater.SpatialFieldUpdater._load_module_config")
    def test_validate_configuration_invalid_batch_size(self, mock_load_config, 
                                                      mock_config_loader, valid_module_config):
        """Test configuration validation with invalid batch size."""
        config = valid_module_config.copy()
        config["processing"]["batch_size"] = 2000  # Too large
        mock_load_config.return_value = config
        
        updater = SpatialFieldUpdater(mock_config_loader)
        result = updater.validate_configuration()
        
        assert result is False
        assert updater._configuration_valid is False
    
    @patch("modules.spatial_field_updater.processor.spatial_field_updater.SpatialFieldUpdater._load_module_config")
    def test_validate_configuration_framework_error(self, mock_load_config, 
                                                   valid_module_config):
        """Test configuration validation when framework config fails."""
        mock_config_loader = Mock()
        mock_config_loader.load_environment_config.side_effect = Exception("Framework error")
        mock_load_config.return_value = valid_module_config
        
        updater = SpatialFieldUpdater(mock_config_loader)
        result = updater.validate_configuration()
        
        assert result is False
        assert updater._configuration_valid is False
    
    @patch("modules.spatial_field_updater.processor.spatial_field_updater.SpatialFieldUpdater._load_module_config")
    def test_process_dry_run_success(self, mock_load_config, mock_config_loader, 
                                   valid_module_config):
        """Test successful dry run processing."""
        mock_load_config.return_value = valid_module_config
        
        updater = SpatialFieldUpdater(mock_config_loader)
        result = updater.process(dry_run=True)
        
        assert isinstance(result, ProcessingResult)
        assert result.success is True
        assert result.records_processed == 150  # Simulated dry run count
        assert result.errors == []
        assert result.metadata["dry_run"] is True
        assert result.execution_time >= 0
        assert updater._last_run is not None
    
    @patch("modules.spatial_field_updater.processor.spatial_field_updater.SpatialFieldUpdater._load_module_config")
    def test_process_live_run_success(self, mock_load_config, mock_config_loader, 
                                    valid_module_config):
        """Test successful live processing."""
        mock_load_config.return_value = valid_module_config
        
        updater = SpatialFieldUpdater(mock_config_loader)
        result = updater.process(dry_run=False)
        
        assert isinstance(result, ProcessingResult)
        assert result.success is True
        assert result.records_processed == 0  # Placeholder implementation
        assert result.errors == []
        assert result.metadata["dry_run"] is False
        assert result.execution_time >= 0
    
    def test_process_configuration_invalid(self, mock_config_loader):
        """Test processing when configuration is invalid."""
        # Create updater with invalid config (will fail validation)
        with patch("modules.spatial_field_updater.processor.spatial_field_updater.SpatialFieldUpdater._load_module_config",
                   side_effect=FileNotFoundError()):
            updater = SpatialFieldUpdater(mock_config_loader)
            result = updater.process(dry_run=True)
            
            assert isinstance(result, ProcessingResult)
            assert result.success is False
            assert result.records_processed == 0
            assert "Configuration validation failed" in result.errors
            assert result.execution_time == 0.0
    
    @patch("modules.spatial_field_updater.processor.spatial_field_updater.SpatialFieldUpdater._load_module_config")
    @patch("modules.spatial_field_updater.processor.spatial_field_updater.ArcGISConnector")
    def test_process_arcgis_connector_failure(self, mock_connector_class, mock_load_config, 
                                            mock_config_loader, valid_module_config):
        """Test processing when ArcGIS connector initialization fails."""
        mock_load_config.return_value = valid_module_config
        mock_connector_class.side_effect = Exception("Connector failed")
        
        updater = SpatialFieldUpdater(mock_config_loader)
        result = updater.process(dry_run=True)
        
        assert isinstance(result, ProcessingResult)
        assert result.success is False
        assert result.records_processed == 0
        assert any("ArcGIS connector initialization failed" in error for error in result.errors)
        assert result.execution_time > 0
    
    @patch("modules.spatial_field_updater.processor.spatial_field_updater.SpatialFieldUpdater._load_module_config")
    @patch("modules.spatial_field_updater.processor.spatial_field_updater.ArcGISConnector")
    def test_process_unexpected_exception(self, mock_connector_class, mock_load_config, 
                                        mock_config_loader, valid_module_config):
        """Test processing when unexpected exception occurs during processing."""
        mock_load_config.return_value = valid_module_config
        
        # Mock ArcGIS connector to initialize successfully first
        mock_connector = Mock()
        mock_connector_class.return_value = mock_connector
        
        updater = SpatialFieldUpdater(mock_config_loader)
        
        # Mock the _get_module_config method to raise exception on second call
        # (first call is during validate_configuration, second is during processing)
        call_count = 0
        def side_effect():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return valid_module_config  # For validate_configuration
            else:
                raise Exception("Unexpected error")  # For processing
        
        with patch.object(updater, '_get_module_config', side_effect=side_effect):
            result = updater.process(dry_run=True)
            
            assert isinstance(result, ProcessingResult)
            assert result.success is False
            assert result.records_processed == 0
            assert "Unexpected error" in result.errors[0]
            assert result.execution_time > 0
    
    @patch("modules.spatial_field_updater.processor.spatial_field_updater.SpatialFieldUpdater._load_module_config")
    def test_get_status_configured(self, mock_load_config, mock_config_loader, 
                                 valid_module_config):
        """Test get_status when module is properly configured."""
        mock_load_config.return_value = valid_module_config
        
        updater = SpatialFieldUpdater(mock_config_loader)
        status = updater.get_status()
        
        assert isinstance(status, ModuleStatus)
        assert status.module_name == "spatial_field_updater"
        assert status.is_configured is True
        assert status.last_run is None  # No processing run yet
        assert status.status == "ready"
        assert status.health_check is True
    
    def test_get_status_not_configured(self, mock_config_loader):
        """Test get_status when module is not configured."""
        # Create updater with invalid config
        with patch("modules.spatial_field_updater.processor.spatial_field_updater.SpatialFieldUpdater._load_module_config",
                   side_effect=FileNotFoundError()):
            updater = SpatialFieldUpdater(mock_config_loader)
            status = updater.get_status()
            
            assert isinstance(status, ModuleStatus)
            assert status.module_name == "spatial_field_updater"
            assert status.is_configured is False
            assert status.status == "error"
            assert status.health_check is False
    
    @patch("modules.spatial_field_updater.processor.spatial_field_updater.SpatialFieldUpdater._load_module_config")
    def test_get_status_after_processing(self, mock_load_config, mock_config_loader, 
                                       valid_module_config):
        """Test get_status after a processing run."""
        mock_load_config.return_value = valid_module_config
        
        updater = SpatialFieldUpdater(mock_config_loader)
        
        # Run processing first
        updater.process(dry_run=True)
        
        # Check status
        status = updater.get_status()
        
        assert status.is_configured is True
        assert status.last_run is not None
        assert status.status == "ready"
        assert isinstance(status.last_run, datetime)
    
    @patch("modules.spatial_field_updater.processor.spatial_field_updater.SpatialFieldUpdater._load_module_config")
    def test_health_check_success(self, mock_load_config, mock_config_loader, 
                                valid_module_config):
        """Test successful health check."""
        mock_load_config.return_value = valid_module_config
        
        updater = SpatialFieldUpdater(mock_config_loader)
        health_result = updater._health_check()
        
        assert health_result is True
    
    def test_health_check_configuration_invalid(self, mock_config_loader):
        """Test health check when configuration is invalid."""
        with patch("modules.spatial_field_updater.processor.spatial_field_updater.SpatialFieldUpdater._load_module_config",
                   side_effect=FileNotFoundError()):
            updater = SpatialFieldUpdater(mock_config_loader)
            health_result = updater._health_check()
            
            assert health_result is False
    
    @patch("modules.spatial_field_updater.processor.spatial_field_updater.SpatialFieldUpdater._load_module_config")
    def test_health_check_framework_error(self, mock_load_config, valid_module_config):
        """Test health check when framework configuration fails."""
        mock_config_loader = Mock()
        mock_config_loader.load_environment_config.side_effect = Exception("Framework error")
        mock_load_config.return_value = valid_module_config
        
        updater = SpatialFieldUpdater(mock_config_loader)
        health_result = updater._health_check()
        
        assert health_result is False
    
    @patch("modules.spatial_field_updater.processor.spatial_field_updater.SpatialFieldUpdater._load_module_config")
    def test_get_processing_summary_success(self, mock_load_config, mock_config_loader, 
                                          valid_module_config):
        """Test successful processing summary generation."""
        mock_load_config.return_value = valid_module_config
        
        updater = SpatialFieldUpdater(mock_config_loader)
        summary = updater.get_processing_summary()
        
        assert isinstance(summary, dict)
        assert summary["module_name"] == "spatial_field_updater"
        assert "description" in summary
        assert "supported_operations" in summary
        assert "configuration" in summary
        assert summary["configuration"]["batch_size"] == 100
        assert "region" in summary["configuration"]["area_layers"]
        assert "district" in summary["configuration"]["area_layers"]
        assert summary["configuration"]["configured"] is True
    
    def test_get_processing_summary_error(self, mock_config_loader):
        """Test processing summary generation when an error occurs."""
        with patch("modules.spatial_field_updater.processor.spatial_field_updater.SpatialFieldUpdater._load_module_config",
                   side_effect=Exception("Config error")):
            updater = SpatialFieldUpdater(mock_config_loader)
            summary = updater.get_processing_summary()
            
            assert isinstance(summary, dict)
            assert summary["module_name"] == "spatial_field_updater"
            assert "error" in summary
            assert "Config error" in summary["error"]


class TestSpatialFieldUpdaterIntegration:
    """Integration tests for SpatialFieldUpdater with real components."""
    
    @pytest.fixture
    def valid_module_config(self):
        """Create valid module configuration for testing."""
        return {
            "area_layers": {
                "region": {
                    "layer_id": "region-layer-123",
                    "source_code_field": "REGC_code",
                    "target_field": "RegionCode",
                    "description": "Region boundaries"
                },
                "district": {
                    "layer_id": "district-layer-456",
                    "source_code_field": "TALB_code",
                    "target_field": "DistrictCode",
                    "description": "District boundaries"
                }
            },
            "processing": {
                "batch_size": 100,
                "max_retries": 3,
                "timeout_seconds": 1800,
                "spatial_relationship": "intersects"
            },
            "metadata_table": {
                "production_name": "Weeds Area Metadata",
                "development_name": "XXX Weeds Area Metadata DEV"
            },
            "validation": {
                "required_fields": ["object_id", "global_id", "geometry"],
                "field_mappings": {
                    "object_id": "OBJECTID",
                    "global_id": "GlobalID"
                }
            }
        }
    
    def test_module_processor_interface_compliance(self):
        """Test that SpatialFieldUpdater correctly implements ModuleProcessor interface."""
        from src.interfaces.module_processor import ModuleProcessor
        
        # Verify inheritance
        assert issubclass(SpatialFieldUpdater, ModuleProcessor)
        
        # Verify all abstract methods are implemented
        mock_config_loader = Mock()
        updater = SpatialFieldUpdater(mock_config_loader)
        
        # Test that all abstract methods exist and are callable
        assert hasattr(updater, 'validate_configuration')
        assert callable(updater.validate_configuration)
        
        assert hasattr(updater, 'process')
        assert callable(updater.process)
        
        assert hasattr(updater, 'get_status')
        assert callable(updater.get_status)
    
    @patch("modules.spatial_field_updater.processor.spatial_field_updater.SpatialFieldUpdater._load_module_config")
    def test_pydantic_model_integration(self, mock_load_config, valid_module_config):
        """Test integration with Pydantic models."""
        mock_config_loader = Mock()
        mock_config_loader.load_environment_config.return_value = {"development": {}}
        mock_config_loader.load_field_mapping.return_value = {"layers": {}}
        mock_load_config.return_value = valid_module_config
        
        updater = SpatialFieldUpdater(mock_config_loader)
        
        # Test that process returns valid ProcessingResult
        result = updater.process(dry_run=True)
        assert isinstance(result, ProcessingResult)
        
        # Test serialization works
        result_dict = result.model_dump()
        assert isinstance(result_dict, dict)
        assert "success" in result_dict
        assert "records_processed" in result_dict
        
        # Test that get_status returns valid ModuleStatus
        status = updater.get_status()
        assert isinstance(status, ModuleStatus)
        
        # Test serialization works
        status_dict = status.model_dump()
        assert isinstance(status_dict, dict)
        assert "module_name" in status_dict
        assert "is_configured" in status_dict 