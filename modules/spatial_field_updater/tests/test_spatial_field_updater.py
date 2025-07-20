"""
Unit tests for SpatialFieldUpdater with change detection integration.

Tests the main processor class including change detection integration,
processing decision logic, and intelligent processing workflows.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta
import json

from modules.spatial_field_updater.processor.spatial_field_updater import SpatialFieldUpdater
from modules.spatial_field_updater.change_detection.change_detection_models import (
    ProcessingType, ProcessingDecision
)
from modules.spatial_field_updater.models import ProcessMetadata
from src.interfaces.module_processor import ProcessingResult, ModuleStatus


class TestSpatialFieldUpdaterWithChangeDetection:
    """Test SpatialFieldUpdater with change detection integration."""
    
    @pytest.fixture
    def mock_config_loader(self):
        """Create mock ConfigLoader."""
        config_loader = Mock()
        
        # Mock environment config
        config_loader.load_environment_config.return_value = {
            'current_environment': 'development',
            'development': {
                'weed_locations_layer_id': 'weed-layer-123'
            }
        }
        
        # Mock field mapping
        config_loader.load_field_mapping.return_value = {
            'weed_locations': {'EditDate_1': 'date'}
        }
        
        return config_loader
    
    @pytest.fixture
    def sample_module_config(self):
        """Create sample module configuration."""
        return {
            "area_layers": {
                "region": {
                    "layer_id": "region-layer-123",
                    "source_code_field": "REGC_code",
                    "target_field": "RegionCode",
                    "expected_fields": {
                        "REGC_code": "string",
                        "OBJECTID": "integer"
                    }
                },
                "district": {
                    "layer_id": "district-layer-456", 
                    "source_code_field": "TALB_code",
                    "target_field": "DistrictCode",
                    "expected_fields": {
                        "TALB_code": "string",
                        "OBJECTID": "integer"
                    }
                }
            },
            "processing": {
                "batch_size": 100,
                "max_retries": 3,
                "timeout_seconds": 1800
            },
            "metadata_table": {
                "production_name": "Weeds Area Metadata",
                "development_name": "XXX Weeds Area Metadata DEV",
                "required_fields": {
                    "ProcessTimestamp": "date",
                    "ProcessStatus": "string"
                }
            },
            "validation": {
                "required_fields": ["object_id", "global_id"],
                "field_mappings": {
                    "object_id": "OBJECTID",
                    "global_id": "GlobalID"
                }
            },
            "change_detection": {
                "enabled": True,
                "edit_date_field": "EditDate_1",
                "thresholds": {
                    "full_reprocess_percentage": 25.0,
                    "incremental_threshold_percentage": 1.0,
                    "max_incremental_records": 1000
                }
            }
        }
    
    @pytest.fixture
    def spatial_updater(self, mock_config_loader, sample_module_config):
        """Create SpatialFieldUpdater instance."""
        with patch.object(SpatialFieldUpdater, '_load_module_config') as mock_load:
            mock_load.return_value = sample_module_config
            return SpatialFieldUpdater(mock_config_loader)
    
    def test_initialization_with_change_detection(self, spatial_updater):
        """Test that SpatialFieldUpdater initializes with change detection capability."""
        assert spatial_updater.change_detector is None  # Not initialized until needed
        assert hasattr(spatial_updater, 'change_detector')
    
    def test_initialize_layer_access_with_change_detection(self, spatial_updater):
        """Test layer access initialization includes change detection."""
        # Mock components
        mock_connector = Mock()
        spatial_updater.connector = mock_connector
        
        with patch('modules.spatial_field_updater.processor.spatial_field_updater.LayerAccessManager') as mock_lam, \
             patch('modules.spatial_field_updater.processor.spatial_field_updater.FieldValidator') as mock_fv, \
             patch('modules.spatial_field_updater.processor.spatial_field_updater.MetadataTableManager') as mock_mtm, \
             patch('modules.spatial_field_updater.processor.spatial_field_updater.SpatialChangeDetector') as mock_scd:
            
            spatial_updater._initialize_layer_access()
            
            # Verify all components were created
            mock_lam.assert_called_once_with(mock_connector, spatial_updater.config_loader)
            mock_fv.assert_called_once()
            mock_mtm.assert_called_once()
            mock_scd.assert_called_once()
            
            # Verify change detector was created with correct parameters
            args, kwargs = mock_scd.call_args
            assert len(args) == 3  # layer_manager, metadata_manager, config_loader
    
    def test_configuration_validation_with_change_detection(self, spatial_updater):
        """Test configuration validation includes change detection settings."""
        # Mock successful validation
        with patch.object(spatial_updater, '_initialize_layer_access'), \
             patch.object(spatial_updater, 'layer_manager') as mock_lm, \
             patch.object(spatial_updater, 'field_validator') as mock_fv, \
             patch.object(spatial_updater, 'metadata_manager') as mock_mm:
            
            # Mock connector
            spatial_updater.connector = Mock()
            
            # Mock layer metadata and validation
            mock_metadata = Mock()
            mock_metadata.layer_name = "Test Layer"
            mock_lm.get_layer_metadata.return_value = mock_metadata
            
            mock_validation_result = Mock()
            mock_validation_result.is_valid = True
            mock_fv.validate_layer_schema.return_value = mock_validation_result
            
            mock_mm.validate_metadata_table_schema.return_value = True
            
            result = spatial_updater.validate_configuration()
            
            assert result is True
            assert spatial_updater._configuration_valid is True
    
    def test_configuration_validation_invalid_change_detection(self, mock_config_loader):
        """Test configuration validation fails with invalid change detection config."""
        invalid_config = {
            "area_layers": {"region": {"layer_id": "test", "source_code_field": "code", "target_field": "field"}},
            "processing": {"batch_size": 100, "max_retries": 3, "timeout_seconds": 1800},
            "metadata_table": {"production_name": "test", "development_name": "test", "required_fields": {}},
            "validation": {"required_fields": [], "field_mappings": {}},
            "change_detection": {
                "thresholds": {
                    "full_reprocess_percentage": "invalid",  # Should be number
                    "incremental_threshold_percentage": 1.0
                }
            }
        }
        
        with patch.object(SpatialFieldUpdater, '_load_module_config') as mock_load:
            mock_load.return_value = invalid_config
            updater = SpatialFieldUpdater(mock_config_loader)
            
            result = updater.validate_configuration()
            assert result is False
    
    def test_process_with_no_changes_detected(self, spatial_updater):
        """Test processing when change detection determines no processing is needed."""
        # Mock processing decision for no changes
        mock_decision = ProcessingDecision(
            processing_type=ProcessingType.NO_PROCESSING_NEEDED,
            change_threshold_met=False,
            full_reprocess_required=False,
            reasoning="No changes detected since last processing"
        )
        
        with patch.object(spatial_updater, 'validate_configuration', return_value=True), \
             patch.object(spatial_updater, '_initialize_layer_access'), \
             patch.object(spatial_updater, 'change_detector') as mock_detector:
            
            # Mock ArcGIS connector
            spatial_updater.connector = Mock()
            
            mock_detector.compare_with_last_processing.return_value = mock_decision
            
            result = spatial_updater.process(dry_run=True)
            
            assert result.success is True
            assert result.records_processed == 0
            assert result.metadata["processing_skipped"] is True
            assert result.metadata["change_detection_used"] is True
            assert "estimated_time_saved" in result.metadata
    
    def test_process_with_incremental_update(self, spatial_updater):
        """Test processing when change detection recommends incremental update."""
        # Mock processing decision for incremental update
        mock_decision = ProcessingDecision(
            processing_type=ProcessingType.INCREMENTAL_UPDATE,
            target_records=["123", "456", "789"],
            change_threshold_met=True,
            full_reprocess_required=False,
            incremental_filters={"where_clause": "EditDate_1 > 1234567890"},
            reasoning="25 records changed (2.5% change)",
            estimated_processing_time=5.0
        )
        
        with patch.object(spatial_updater, 'validate_configuration', return_value=True), \
             patch.object(spatial_updater, '_initialize_layer_access'), \
             patch.object(spatial_updater, 'change_detector') as mock_detector, \
             patch.object(spatial_updater, '_perform_incremental_processing', return_value=3) as mock_incremental:
            
            spatial_updater.connector = Mock()
            mock_detector.compare_with_last_processing.return_value = mock_decision
            
            result = spatial_updater.process(dry_run=True)
            
            assert result.success is True
            assert result.records_processed == 3
            assert result.metadata["processing_type"] == ProcessingType.INCREMENTAL_UPDATE
            assert result.metadata["change_detection_used"] is True
            
            # Verify incremental processing was called
            mock_incremental.assert_called_once_with("weed-layer-123", mock_decision, True)
    
    def test_process_with_full_reprocessing(self, spatial_updater):
        """Test processing when change detection recommends full reprocessing."""
        # Mock processing decision for full reprocessing
        mock_decision = ProcessingDecision(
            processing_type=ProcessingType.FULL_REPROCESSING,
            target_records=[],
            change_threshold_met=True,
            full_reprocess_required=True,
            reasoning="300 records changed (30% change) - exceeds threshold",
            estimated_processing_time=100.0
        )
        
        with patch.object(spatial_updater, 'validate_configuration', return_value=True), \
             patch.object(spatial_updater, '_initialize_layer_access'), \
             patch.object(spatial_updater, 'change_detector') as mock_detector, \
             patch.object(spatial_updater, '_perform_full_reprocessing', return_value=1000) as mock_full:
            
            spatial_updater.connector = Mock()
            mock_detector.compare_with_last_processing.return_value = mock_decision
            
            result = spatial_updater.process(dry_run=True)
            
            assert result.success is True
            assert result.records_processed == 1000
            assert result.metadata["processing_type"] == ProcessingType.FULL_REPROCESSING
            
            # Verify full processing was called
            mock_full.assert_called_once_with("weed-layer-123", True)
    
    def test_process_with_force_full_update(self, spatial_updater):
        """Test processing when change detection recommends force full update."""
        # Mock processing decision for force full update
        mock_decision = ProcessingDecision(
            processing_type=ProcessingType.FORCE_FULL_UPDATE,
            target_records=[],
            change_threshold_met=True,
            full_reprocess_required=True,
            reasoning="Change detection failed - forcing full update"
        )
        
        with patch.object(spatial_updater, 'validate_configuration', return_value=True), \
             patch.object(spatial_updater, '_initialize_layer_access'), \
             patch.object(spatial_updater, 'change_detector') as mock_detector, \
             patch.object(spatial_updater, '_perform_full_reprocessing', return_value=1000) as mock_full:
            
            spatial_updater.connector = Mock()
            mock_detector.compare_with_last_processing.return_value = mock_decision
            
            result = spatial_updater.process(dry_run=True)
            
            assert result.success is True
            assert result.records_processed == 1000
            assert result.metadata["processing_type"] == ProcessingType.FORCE_FULL_UPDATE
            
            # Verify full processing was called
            mock_full.assert_called_once_with("weed-layer-123", True)
    
    def test_perform_full_reprocessing_dry_run(self, spatial_updater):
        """Test full reprocessing in dry run mode."""
        # Mock layer manager
        mock_layer_manager = Mock()
        mock_layer = Mock()
        mock_layer.query.return_value = 5000  # Total record count
        mock_layer_manager.get_layer_by_id.return_value = mock_layer
        spatial_updater.layer_manager = mock_layer_manager
        
        result = spatial_updater._perform_full_reprocessing("layer-123", dry_run=True)
        
        assert result == 5000
        mock_layer.query.assert_called_once_with(return_count_only=True)
    
    def test_perform_full_reprocessing_live_mode(self, spatial_updater):
        """Test full reprocessing in live mode (placeholder implementation)."""
        result = spatial_updater._perform_full_reprocessing("layer-123", dry_run=False)
        
        # Should return placeholder value until actual implementation
        assert result == 1000
    
    def test_perform_incremental_processing_dry_run(self, spatial_updater):
        """Test incremental processing in dry run mode."""
        mock_decision = ProcessingDecision(
            processing_type=ProcessingType.INCREMENTAL_UPDATE,
            target_records=["123", "456", "789"],
            change_threshold_met=True,
            full_reprocess_required=False,
            incremental_filters={"where_clause": "EditDate_1 > 1234567890"}
        )
        
        result = spatial_updater._perform_incremental_processing("layer-123", mock_decision, dry_run=True)
        
        assert result == 3  # Number of target records
    
    def test_perform_incremental_processing_live_mode(self, spatial_updater):
        """Test incremental processing in live mode (placeholder implementation)."""
        mock_decision = ProcessingDecision(
            processing_type=ProcessingType.INCREMENTAL_UPDATE,
            target_records=["123", "456"],
            change_threshold_met=True,
            full_reprocess_required=False
        )
        
        result = spatial_updater._perform_incremental_processing("layer-123", mock_decision, dry_run=False)
        
        # Should return target record count until actual implementation
        assert result == 2
    
    def test_create_processing_metadata_with_change_detection(self, spatial_updater, sample_module_config):
        """Test processing metadata creation includes change detection information."""
        mock_decision = ProcessingDecision(
            processing_type=ProcessingType.INCREMENTAL_UPDATE,
            target_records=["123", "456"],
            change_threshold_met=True,
            full_reprocess_required=False,
            incremental_filters={"where_clause": "EditDate_1 > 1234567890"},
            estimated_processing_time=5.0,
            configuration_used={"threshold": 1.0}
        )
        
        spatial_updater._module_config = sample_module_config
        
        metadata = spatial_updater._create_processing_metadata(mock_decision, 2, 3.5)
        
        assert metadata.process_status == "Success"
        assert metadata.records_processed == 2
        assert metadata.processing_duration == 3.5
        assert metadata.metadata_details["processing_type"] == ProcessingType.INCREMENTAL_UPDATE
        assert metadata.metadata_details["change_detection_used"] is True
        assert metadata.metadata_details["change_threshold_met"] is True
        assert "incremental_filters" in metadata.metadata_details
        assert "estimated_vs_actual_time" in metadata.metadata_details
        assert metadata.metadata_details["estimated_vs_actual_time"]["estimated"] == 5.0
        assert metadata.metadata_details["estimated_vs_actual_time"]["actual"] == 3.5
    
    def test_process_metadata_writing(self, spatial_updater):
        """Test that processing metadata is written when not in dry run mode."""
        mock_decision = ProcessingDecision(
            processing_type=ProcessingType.INCREMENTAL_UPDATE,
            target_records=["123"],
            change_threshold_met=True,
            full_reprocess_required=False
        )
        
        mock_metadata_manager = Mock()
        
        with patch.object(spatial_updater, 'validate_configuration', return_value=True), \
             patch.object(spatial_updater, '_initialize_layer_access'), \
             patch.object(spatial_updater, 'change_detector') as mock_detector, \
             patch.object(spatial_updater, '_perform_incremental_processing', return_value=1):
            
            spatial_updater.connector = Mock()
            spatial_updater.metadata_manager = mock_metadata_manager
            mock_detector.compare_with_last_processing.return_value = mock_decision
            
            result = spatial_updater.process(dry_run=False)
            
            assert result.success is True
            # Verify metadata was written
            mock_metadata_manager.write_processing_metadata.assert_called_once()
    
    def test_process_missing_weed_layer_id(self, spatial_updater, mock_config_loader):
        """Test processing fails gracefully when weed layer ID is not configured."""
        # Mock environment config without weed_locations_layer_id
        mock_config_loader.load_environment_config.return_value = {
            'current_environment': 'development',
            'development': {}  # Missing weed_locations_layer_id
        }
        
        with patch.object(spatial_updater, 'validate_configuration', return_value=True):
            spatial_updater.connector = Mock()
            
            result = spatial_updater.process(dry_run=True)
            
            assert result.success is False
            assert "not configured for current environment" in str(result.errors[0])
            assert result.metadata["environment"] == "development"
    
    def test_process_change_detection_failure(self, spatial_updater):
        """Test processing handles change detection failures gracefully."""
        with patch.object(spatial_updater, 'validate_configuration', return_value=True), \
             patch.object(spatial_updater, '_initialize_layer_access'), \
             patch.object(spatial_updater, 'change_detector') as mock_detector:
            
            spatial_updater.connector = Mock()
            
            # Mock change detection failure
            mock_detector.compare_with_last_processing.side_effect = Exception("Change detection failed")
            
            result = spatial_updater.process(dry_run=True)
            
            assert result.success is False
            assert "Change detection failed" in str(result.errors[0])
    
    def test_get_processing_summary_with_change_detection(self, spatial_updater):
        """Test processing summary includes change detection information."""
        # Mock layer manager and metadata manager
        mock_layer_manager = Mock()
        mock_layer_manager.get_cache_stats.return_value = {"hits": 10, "misses": 2}
        spatial_updater.layer_manager = mock_layer_manager
        
        mock_metadata_manager = Mock()
        mock_metadata_manager.get_metadata_table_name.return_value = "Test Metadata Table"
        mock_metadata_manager.access_metadata_table.return_value = Mock()  # Non-None indicates accessible
        spatial_updater.metadata_manager = mock_metadata_manager
        
        with patch.object(spatial_updater, 'get_all_layer_metadata', return_value={"test": "data"}), \
             patch.object(spatial_updater, 'validate_configuration', return_value=True), \
             patch.object(spatial_updater, 'get_status') as mock_status:
            
            mock_status.return_value = Mock()
            mock_status.return_value.model_dump.return_value = {"status": "ready"}
            
            summary = spatial_updater.get_processing_summary()
            
            assert summary["module_name"] == "spatial_field_updater"
            assert "Incremental processing based on change detection" in summary["supported_operations"]
            assert "layer_cache_stats" in summary
            assert summary["layer_cache_stats"]["hits"] == 10
            assert summary["metadata_table"]["name"] == "Test Metadata Table"
            assert summary["metadata_table"]["accessible"] is True


class TestSpatialFieldUpdaterCompatibility:
    """Test that SpatialFieldUpdater maintains compatibility with existing interfaces."""
    
    @pytest.fixture
    def basic_config(self):
        """Create basic configuration without change detection."""
        return {
            "area_layers": {
                "region": {"layer_id": "test", "source_code_field": "code", "target_field": "field"}
            },
            "processing": {"batch_size": 100, "max_retries": 3, "timeout_seconds": 1800},
            "metadata_table": {"production_name": "test", "development_name": "test", "required_fields": {}},
            "validation": {"required_fields": [], "field_mappings": {}}
        }
    
    def test_compatibility_without_change_detection_config(self, mock_config_loader, basic_config):
        """Test that the updater works without change detection configuration."""
        with patch.object(SpatialFieldUpdater, '_load_module_config') as mock_load:
            mock_load.return_value = basic_config
            updater = SpatialFieldUpdater(mock_config_loader)
            
            # Should initialize successfully
            assert updater.change_detector is None
            assert hasattr(updater, 'change_detector')
    
    def test_module_processor_interface_compliance(self, mock_config_loader, basic_config):
        """Test that SpatialFieldUpdater still implements ModuleProcessor interface correctly."""
        with patch.object(SpatialFieldUpdater, '_load_module_config') as mock_load:
            mock_load.return_value = basic_config
            updater = SpatialFieldUpdater(mock_config_loader)
            
            # Test interface methods exist
            assert hasattr(updater, 'process')
            assert hasattr(updater, 'validate_configuration')
            assert hasattr(updater, 'get_status')
            
            # Test method signatures
            assert callable(updater.process)
            assert callable(updater.validate_configuration)
            assert callable(updater.get_status) 