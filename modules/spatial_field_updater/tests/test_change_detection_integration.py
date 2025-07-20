"""
Integration tests for change detection system.

Tests the complete workflow from change detection through processing decisions,
including realistic scenarios with mocked ArcGIS layers and metadata operations.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta
from typing import Dict, Any

from modules.spatial_field_updater.change_detection import (
    SpatialChangeDetector, ProcessingType, ChangeDetectionResult, ProcessingDecision
)
from modules.spatial_field_updater.models import ProcessMetadata
from modules.spatial_field_updater.processor.spatial_field_updater import SpatialFieldUpdater


class TestChangeDetectionIntegration:
    """Integration tests for change detection components."""
    
    @pytest.fixture
    def mock_dependencies(self):
        """Create mock dependencies for change detector."""
        layer_manager = Mock()
        metadata_manager = Mock()
        config_loader = Mock()
        return layer_manager, metadata_manager, config_loader
    
    @pytest.fixture
    def change_detector(self, mock_dependencies):
        """Create SpatialChangeDetector instance."""
        layer_manager, metadata_manager, config_loader = mock_dependencies
        
        # Mock configuration loading
        with patch.object(SpatialChangeDetector, '_load_change_detection_config') as mock_config:
            mock_config.return_value = {
                "enabled": True,
                "edit_date_field": "EditDate_1",
                "thresholds": {
                    "full_reprocess_percentage": 25.0,
                    "incremental_threshold_percentage": 1.0,
                    "max_incremental_records": 1000
                }
            }
            return SpatialChangeDetector(layer_manager, metadata_manager, config_loader)
    
    @pytest.fixture
    def mock_layer_metadata(self):
        """Create mock layer metadata."""
        metadata = Mock()
        metadata.layer_name = "Weed Locations Layer"
        metadata.record_count = 5000
        metadata.last_updated = datetime.now()
        return metadata
    
    def test_no_changes_detected(self, change_detector, mock_dependencies, mock_layer_metadata):
        """Test behavior when no changes are detected."""
        layer_manager, metadata_manager, config_loader = mock_dependencies
        
        # Mock layer with no changes
        mock_layer = Mock()
        layer_manager.get_layer_by_id.return_value = mock_layer
        layer_manager.get_layer_metadata.return_value = mock_layer_metadata
        
        # Simulate query calls for no changes scenario
        def mock_query(**kwargs):
            if kwargs.get('return_count_only'):
                if 'EditDate_1' in kwargs.get('where', ''):
                    return 0  # No modified records
                return 5000  # Total records
            return Mock(features=[])
        
        mock_layer.query.side_effect = mock_query
        
        result = change_detector.detect_changes("test-layer-123")
        
        assert result.processing_recommendation == ProcessingType.NO_PROCESSING_NEEDED
        assert result.modified_records == 0
        assert result.change_percentage == 0.0
        assert result.total_records == 5000
        assert result.layer_id == "test-layer-123"
        assert "No significant changes" in result.get_change_summary()
        
        # Verify change metrics
        assert result.change_metrics.records_analyzed == 5000
        assert result.change_metrics.edit_date_changes == 0
        assert result.change_metrics.processing_duration > 0
    
    def test_incremental_changes_detected(self, change_detector, mock_dependencies, mock_layer_metadata):
        """Test behavior when incremental changes are detected."""
        layer_manager, metadata_manager, config_loader = mock_dependencies
        
        mock_layer = Mock()
        layer_manager.get_layer_by_id.return_value = mock_layer
        layer_manager.get_layer_metadata.return_value = mock_layer_metadata
        
        # Simulate 2% change (100 out of 5000 records)
        def mock_query(**kwargs):
            if kwargs.get('return_count_only'):
                if 'EditDate_1' in kwargs.get('where', ''):
                    return 100  # Modified records
                return 5000  # Total records
            # Return mock features with OBJECTID
            return Mock(features=[Mock(attributes={"OBJECTID": 1000 + i}) for i in range(100)])
        
        mock_layer.query.side_effect = mock_query
        
        result = change_detector.detect_changes("test-layer-123")
        
        assert result.processing_recommendation == ProcessingType.INCREMENTAL_UPDATE
        assert result.modified_records == 100
        assert result.change_percentage == 2.0
        assert result.total_records == 5000
        assert "Incremental update recommended" in result.get_change_summary()
        
        # Verify change details include modified record IDs
        modified_ids = result.change_details.get("modified_record_ids", [])
        assert len(modified_ids) == 100
        assert all(isinstance(id_str, str) for id_str in modified_ids)
    
    def test_full_reprocess_threshold_exceeded(self, change_detector, mock_dependencies, mock_layer_metadata):
        """Test behavior when full reprocess threshold is exceeded."""
        layer_manager, metadata_manager, config_loader = mock_dependencies
        
        mock_layer = Mock()
        layer_manager.get_layer_by_id.return_value = mock_layer
        layer_manager.get_layer_metadata.return_value = mock_layer_metadata
        
        # Simulate 30% change (1500 out of 5000 records)
        def mock_query(**kwargs):
            if kwargs.get('return_count_only'):
                if 'EditDate_1' in kwargs.get('where', ''):
                    return 1500  # Modified records
                return 5000  # Total records
            return Mock(features=[])
        
        mock_layer.query.side_effect = mock_query
        
        result = change_detector.detect_changes("test-layer-123")
        
        assert result.processing_recommendation == ProcessingType.FULL_REPROCESSING
        assert result.modified_records == 1500
        assert result.change_percentage == 30.0
        assert "Full reprocessing recommended" in result.get_change_summary()
    
    def test_max_incremental_records_exceeded(self, change_detector, mock_dependencies, mock_layer_metadata):
        """Test that full reprocessing is recommended when max incremental records is exceeded."""
        layer_manager, metadata_manager, config_loader = mock_dependencies
        
        mock_layer = Mock()
        layer_manager.get_layer_by_id.return_value = mock_layer
        layer_manager.get_layer_metadata.return_value = mock_layer_metadata
        
        # Simulate 1200 modified records (exceeds max_incremental_records of 1000)
        # but only 10% change (below full_reprocess_percentage of 25%)
        def mock_query(**kwargs):
            if kwargs.get('return_count_only'):
                if 'EditDate_1' in kwargs.get('where', ''):
                    return 1200  # Modified records exceeding limit
                return 12000  # Total records (10% change)
            return Mock(features=[])
        
        mock_layer.query.side_effect = mock_query
        
        result = change_detector.detect_changes("test-layer-123")
        
        assert result.processing_recommendation == ProcessingType.FULL_REPROCESSING
        assert result.modified_records == 1200
        assert result.change_percentage == 10.0  # Below percentage threshold but exceeds count threshold
    
    def test_processing_decision_with_no_previous_metadata(self, change_detector, mock_dependencies):
        """Test processing decision when no previous metadata exists."""
        layer_manager, metadata_manager, config_loader = mock_dependencies
        
        # Mock no previous metadata
        metadata_manager.read_last_processing_metadata.return_value = None
        
        decision = change_detector.compare_with_last_processing("test-layer")
        
        assert decision.processing_type == ProcessingType.FULL_REPROCESSING
        assert decision.full_reprocess_required is True
        assert decision.change_threshold_met is True
        assert "No previous processing metadata found" in decision.reasoning
        assert decision.target_records == []
    
    def test_processing_decision_with_changes_since_last_processing(self, change_detector, mock_dependencies, mock_layer_metadata):
        """Test processing decision when changes are detected since last processing."""
        layer_manager, metadata_manager, config_loader = mock_dependencies
        
        # Mock previous processing metadata
        last_processing = ProcessMetadata(
            process_timestamp=datetime.now() - timedelta(hours=12),
            region_layer_id="region-123",
            region_layer_updated=datetime.now() - timedelta(days=1),
            district_layer_id="district-456",
            district_layer_updated=datetime.now() - timedelta(days=1),
            process_status="Success",
            records_processed=4850,
            processing_duration=180.0,
            error_message=None
        )
        metadata_manager.read_last_processing_metadata.return_value = last_processing
        
        # Mock layer access and change detection
        mock_layer = Mock()
        layer_manager.get_layer_by_id.return_value = mock_layer
        layer_manager.get_layer_metadata.return_value = mock_layer_metadata
        
        # Simulate incremental changes (75 out of 5000 records = 1.5%)
        def mock_query(**kwargs):
            if kwargs.get('return_count_only'):
                if 'EditDate_1' in kwargs.get('where', ''):
                    return 75  # Modified records
                return 5000  # Total records
            return Mock(features=[Mock(attributes={"OBJECTID": 2000 + i}) for i in range(75)])
        
        mock_layer.query.side_effect = mock_query
        
        decision = change_detector.compare_with_last_processing("test-layer")
        
        assert decision.processing_type == ProcessingType.INCREMENTAL_UPDATE
        assert decision.change_threshold_met is True
        assert decision.full_reprocess_required is False
        assert len(decision.target_records) == 75
        assert "where_clause" in decision.incremental_filters
        assert "EditDate_1 >" in decision.incremental_filters["where_clause"]
        assert decision.estimated_processing_time > 0
        assert "1.50% change" in decision.reasoning
        
        # Verify configuration was included
        assert "thresholds" in decision.configuration_used
        assert decision.configuration_used["edit_date_field"] == "EditDate_1"
    
    def test_change_detection_error_handling(self, change_detector, mock_dependencies):
        """Test change detection handles layer access errors gracefully."""
        layer_manager, metadata_manager, config_loader = mock_dependencies
        
        # Mock layer access failure
        layer_manager.get_layer_metadata.return_value = None
        
        result = change_detector.detect_changes("invalid-layer")
        
        assert result.layer_id == "invalid-layer"
        assert result.total_records == 0
        assert result.modified_records == 0
        assert result.processing_recommendation == ProcessingType.NO_PROCESSING_NEEDED
        assert "error" in result.change_details
        assert result.change_details["detection_failed"] is True
        assert result.change_metrics.processing_duration >= 0
    
    def test_processing_decision_error_handling(self, change_detector, mock_dependencies):
        """Test processing decision handles errors gracefully."""
        layer_manager, metadata_manager, config_loader = mock_dependencies
        
        # Mock metadata access failure
        metadata_manager.read_last_processing_metadata.side_effect = Exception("Database error")
        
        decision = change_detector.compare_with_last_processing("test-layer")
        
        assert decision.processing_type == ProcessingType.FORCE_FULL_UPDATE
        assert decision.full_reprocess_required is True
        assert "Error in change detection comparison" in decision.reasoning
        assert "Database error" in decision.reasoning
    
    def test_change_detection_with_custom_timestamp(self, change_detector, mock_dependencies, mock_layer_metadata):
        """Test change detection with custom since timestamp."""
        layer_manager, metadata_manager, config_loader = mock_dependencies
        
        mock_layer = Mock()
        layer_manager.get_layer_by_id.return_value = mock_layer
        layer_manager.get_layer_metadata.return_value = mock_layer_metadata
        
        # Mock query with specific timestamp
        custom_timestamp = datetime.now() - timedelta(hours=6)
        
        def mock_query(**kwargs):
            if kwargs.get('return_count_only'):
                if 'EditDate_1' in kwargs.get('where', ''):
                    # Verify timestamp was converted to milliseconds
                    expected_ms = int(custom_timestamp.timestamp() * 1000)
                    where_clause = kwargs.get('where', '')
                    assert str(expected_ms) in where_clause
                    return 50  # Modified records
                return 5000  # Total records
            return Mock(features=[Mock(attributes={"OBJECTID": i}) for i in range(3000, 3050)])
        
        mock_layer.query.side_effect = mock_query
        
        result = change_detector.detect_changes("test-layer", custom_timestamp)
        
        assert result.modified_records == 50
        assert result.change_percentage == 1.0
        assert result.processing_recommendation == ProcessingType.INCREMENTAL_UPDATE
        assert custom_timestamp.isoformat() in result.change_details["since_timestamp"]


class TestCompleteWorkflowIntegration:
    """Integration tests for complete change detection workflow with SpatialFieldUpdater."""
    
    @pytest.fixture
    def mock_config_loader(self):
        """Create mock config loader for complete workflow."""
        config_loader = Mock()
        config_loader.load_environment_config.return_value = {
            'current_environment': 'development',
            'development': {
                'weed_locations_layer_id': 'weed-layer-123'
            }
        }
        config_loader.load_field_mapping.return_value = {
            'weed_locations': {'EditDate_1': 'date'}
        }
        return config_loader
    
    @pytest.fixture
    def complete_config(self):
        """Create complete module configuration."""
        return {
            "area_layers": {
                "region": {
                    "layer_id": "region-layer-123",
                    "source_code_field": "REGC_code",
                    "target_field": "RegionCode",
                    "expected_fields": {"REGC_code": "string", "OBJECTID": "integer"}
                },
                "district": {
                    "layer_id": "district-layer-456", 
                    "source_code_field": "TALB_code",
                    "target_field": "DistrictCode",
                    "expected_fields": {"TALB_code": "string", "OBJECTID": "integer"}
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
                "required_fields": {"ProcessTimestamp": "date"}
            },
            "validation": {
                "required_fields": ["object_id"],
                "field_mappings": {"object_id": "OBJECTID"}
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
    def spatial_updater(self, mock_config_loader, complete_config):
        """Create SpatialFieldUpdater for complete workflow testing."""
        with patch.object(SpatialFieldUpdater, '_load_module_config') as mock_load:
            mock_load.return_value = complete_config
            return SpatialFieldUpdater(mock_config_loader)
    
    def test_complete_workflow_no_processing_needed(self, spatial_updater):
        """Test complete workflow when no processing is needed."""
        # Mock all dependencies
        mock_connector = Mock()
        mock_layer = Mock()
        mock_layer_metadata = Mock()
        mock_layer_metadata.layer_name = "Weed Locations"
        
        # Mock no changes scenario
        def mock_query(**kwargs):
            if kwargs.get('return_count_only'):
                if 'EditDate_1' in kwargs.get('where', ''):
                    return 0  # No changes
                return 10000  # Total records
            return Mock(features=[])
        
        mock_layer.query.side_effect = mock_query
        
        with patch('modules.spatial_field_updater.processor.spatial_field_updater.ArcGISConnector') as mock_conn_class, \
             patch('modules.spatial_field_updater.processor.spatial_field_updater.LayerAccessManager') as mock_lam, \
             patch('modules.spatial_field_updater.processor.spatial_field_updater.FieldValidator') as mock_fv, \
             patch('modules.spatial_field_updater.processor.spatial_field_updater.MetadataTableManager') as mock_mtm:
            
            mock_conn_class.return_value = mock_connector
            
            # Setup layer access mocks
            mock_layer_manager = Mock()
            mock_layer_manager.get_layer_metadata.return_value = mock_layer_metadata
            mock_layer_manager.get_layer_by_id.return_value = mock_layer
            mock_lam.return_value = mock_layer_manager
            
            mock_field_validator = Mock()
            mock_validation_result = Mock()
            mock_validation_result.is_valid = True
            mock_field_validator.validate_layer_schema.return_value = mock_validation_result
            mock_fv.return_value = mock_field_validator
            
            mock_metadata_manager = Mock()
            mock_metadata_manager.validate_metadata_table_schema.return_value = True
            mock_metadata_manager.read_last_processing_metadata.return_value = ProcessMetadata(
                process_timestamp=datetime.now() - timedelta(hours=1),
                region_layer_id="region-123",
                region_layer_updated=datetime.now(),
                district_layer_id="district-456",
                district_layer_updated=datetime.now(),
                process_status="Success",
                records_processed=10000,
                processing_duration=120.0,
                error_message=None
            )
            mock_mtm.return_value = mock_metadata_manager
            
            # Execute complete workflow
            result = spatial_updater.process(dry_run=True)
            
            # Verify no processing was performed
            assert result.success is True
            assert result.records_processed == 0
            assert result.metadata["processing_skipped"] is True
            assert result.metadata["change_detection_used"] is True
            assert "estimated_time_saved" in result.metadata
    
    def test_complete_workflow_incremental_processing(self, spatial_updater):
        """Test complete workflow with incremental processing."""
        mock_connector = Mock()
        mock_layer = Mock()
        mock_layer_metadata = Mock()
        mock_layer_metadata.layer_name = "Weed Locations"
        
        # Mock incremental changes scenario (150 out of 10000 = 1.5%)
        def mock_query(**kwargs):
            if kwargs.get('return_count_only'):
                if 'EditDate_1' in kwargs.get('where', ''):
                    return 150  # Changed records
                return 10000  # Total records
            return Mock(features=[Mock(attributes={"OBJECTID": 5000 + i}) for i in range(150)])
        
        mock_layer.query.side_effect = mock_query
        
        with patch('modules.spatial_field_updater.processor.spatial_field_updater.ArcGISConnector') as mock_conn_class, \
             patch('modules.spatial_field_updater.processor.spatial_field_updater.LayerAccessManager') as mock_lam, \
             patch('modules.spatial_field_updater.processor.spatial_field_updater.FieldValidator') as mock_fv, \
             patch('modules.spatial_field_updater.processor.spatial_field_updater.MetadataTableManager') as mock_mtm:
            
            mock_conn_class.return_value = mock_connector
            
            # Setup mocks
            mock_layer_manager = Mock()
            mock_layer_manager.get_layer_metadata.return_value = mock_layer_metadata
            mock_layer_manager.get_layer_by_id.return_value = mock_layer
            mock_lam.return_value = mock_layer_manager
            
            mock_field_validator = Mock()
            mock_validation_result = Mock()
            mock_validation_result.is_valid = True
            mock_field_validator.validate_layer_schema.return_value = mock_validation_result
            mock_fv.return_value = mock_field_validator
            
            mock_metadata_manager = Mock()
            mock_metadata_manager.validate_metadata_table_schema.return_value = True
            mock_metadata_manager.read_last_processing_metadata.return_value = ProcessMetadata(
                process_timestamp=datetime.now() - timedelta(hours=2),
                region_layer_id="region-123",
                region_layer_updated=datetime.now(),
                district_layer_id="district-456",
                district_layer_updated=datetime.now(),
                process_status="Success",
                records_processed=9850,
                processing_duration=150.0,
                error_message=None
            )
            mock_mtm.return_value = mock_metadata_manager
            
            # Execute workflow
            result = spatial_updater.process(dry_run=True)
            
            # Verify incremental processing was performed
            assert result.success is True
            assert result.records_processed == 150
            assert result.metadata["processing_type"] == ProcessingType.INCREMENTAL_UPDATE
            assert result.metadata["change_detection_used"] is True
            
            # Verify processing decision details
            processing_decision = result.metadata["processing_decision"]
            assert processing_decision["processing_type"] == ProcessingType.INCREMENTAL_UPDATE
            assert len(processing_decision["target_records"]) == 150
            assert "where_clause" in processing_decision["incremental_filters"]
    
    def test_complete_workflow_full_reprocessing(self, spatial_updater):
        """Test complete workflow with full reprocessing."""
        mock_connector = Mock()
        mock_layer = Mock()
        mock_layer_metadata = Mock()
        mock_layer_metadata.layer_name = "Weed Locations"
        
        # Mock full reprocessing scenario (3000 out of 10000 = 30%)
        def mock_query(**kwargs):
            if kwargs.get('return_count_only'):
                if 'EditDate_1' in kwargs.get('where', ''):
                    return 3000  # Many changed records
                return 10000  # Total records
            return Mock(features=[])
        
        mock_layer.query.side_effect = mock_query
        
        with patch('modules.spatial_field_updater.processor.spatial_field_updater.ArcGISConnector') as mock_conn_class, \
             patch('modules.spatial_field_updater.processor.spatial_field_updater.LayerAccessManager') as mock_lam, \
             patch('modules.spatial_field_updater.processor.spatial_field_updater.FieldValidator') as mock_fv, \
             patch('modules.spatial_field_updater.processor.spatial_field_updater.MetadataTableManager') as mock_mtm:
            
            mock_conn_class.return_value = mock_connector
            
            # Setup mocks  
            mock_layer_manager = Mock()
            mock_layer_manager.get_layer_metadata.return_value = mock_layer_metadata
            mock_layer_manager.get_layer_by_id.return_value = mock_layer
            mock_lam.return_value = mock_layer_manager
            
            mock_field_validator = Mock()
            mock_validation_result = Mock()
            mock_validation_result.is_valid = True
            mock_field_validator.validate_layer_schema.return_value = mock_validation_result
            mock_fv.return_value = mock_field_validator
            
            mock_metadata_manager = Mock()
            mock_metadata_manager.validate_metadata_table_schema.return_value = True
            mock_metadata_manager.read_last_processing_metadata.return_value = ProcessMetadata(
                process_timestamp=datetime.now() - timedelta(days=1),
                region_layer_id="region-123",
                region_layer_updated=datetime.now(),
                district_layer_id="district-456",
                district_layer_updated=datetime.now(),
                process_status="Success",
                records_processed=10000,
                processing_duration=300.0,
                error_message=None
            )
            mock_mtm.return_value = mock_metadata_manager
            
            # Execute workflow
            result = spatial_updater.process(dry_run=True)
            
            # Verify full reprocessing was performed
            assert result.success is True
            assert result.records_processed == 10000  # Full record count
            assert result.metadata["processing_type"] == ProcessingType.FULL_REPROCESSING
            assert result.metadata["change_detection_used"] is True
            
            # Verify processing decision
            processing_decision = result.metadata["processing_decision"]
            assert processing_decision["processing_type"] == ProcessingType.FULL_REPROCESSING
            assert processing_decision["full_reprocess_required"] is True
    
    def test_metadata_writing_integration(self, spatial_updater):
        """Test that processing metadata is properly written with change detection info."""
        mock_connector = Mock()
        mock_layer = Mock()
        mock_layer_metadata = Mock()
        mock_layer_metadata.layer_name = "Weed Locations"
        
        # Mock small incremental change
        def mock_query(**kwargs):
            if kwargs.get('return_count_only'):
                if 'EditDate_1' in kwargs.get('where', ''):
                    return 25  # Small change
                return 5000  # Total records
            return Mock(features=[Mock(attributes={"OBJECTID": 1000 + i}) for i in range(25)])
        
        mock_layer.query.side_effect = mock_query
        
        with patch('modules.spatial_field_updater.processor.spatial_field_updater.ArcGISConnector') as mock_conn_class, \
             patch('modules.spatial_field_updater.processor.spatial_field_updater.LayerAccessManager') as mock_lam, \
             patch('modules.spatial_field_updater.processor.spatial_field_updater.FieldValidator') as mock_fv, \
             patch('modules.spatial_field_updater.processor.spatial_field_updater.MetadataTableManager') as mock_mtm:
            
            mock_conn_class.return_value = mock_connector
            
            mock_layer_manager = Mock()
            mock_layer_manager.get_layer_metadata.return_value = mock_layer_metadata
            mock_layer_manager.get_layer_by_id.return_value = mock_layer
            mock_lam.return_value = mock_layer_manager
            
            mock_field_validator = Mock()
            mock_validation_result = Mock()
            mock_validation_result.is_valid = True
            mock_field_validator.validate_layer_schema.return_value = mock_validation_result
            mock_fv.return_value = mock_field_validator
            
            mock_metadata_manager = Mock()
            mock_metadata_manager.validate_metadata_table_schema.return_value = True
            mock_metadata_manager.read_last_processing_metadata.return_value = ProcessMetadata(
                process_timestamp=datetime.now() - timedelta(hours=3),
                region_layer_id="region-123",
                region_layer_updated=datetime.now(),
                district_layer_id="district-456",
                district_layer_updated=datetime.now(),
                process_status="Success",
                records_processed=5000,
                processing_duration=90.0,
                error_message=None
            )
            mock_mtm.return_value = mock_metadata_manager
            
            # Execute in live mode (not dry run)
            result = spatial_updater.process(dry_run=False)
            
            # Verify metadata was written
            assert result.success is True
            mock_metadata_manager.write_processing_metadata.assert_called_once()
            
            # Verify the metadata content
            written_metadata = mock_metadata_manager.write_processing_metadata.call_args[0][0]
            assert written_metadata.process_status == "Success"
            assert written_metadata.records_processed == 25
            assert "processing_type" in written_metadata.metadata_details
            assert written_metadata.metadata_details["change_detection_used"] is True
            assert "incremental_filters" in written_metadata.metadata_details
            assert "estimated_vs_actual_time" in written_metadata.metadata_details 