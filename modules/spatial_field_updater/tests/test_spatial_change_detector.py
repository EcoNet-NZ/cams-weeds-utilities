"""
Unit tests for SpatialChangeDetector.

Tests the core change detection logic, date-based queries, and processing
decision algorithms with various scenarios and edge cases.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta
from typing import List, Dict, Any

from modules.spatial_field_updater.change_detection.spatial_change_detector import SpatialChangeDetector
from modules.spatial_field_updater.change_detection.change_detection_models import (
    ProcessingType, ChangeDetectionResult, ProcessingDecision
)
from modules.spatial_field_updater.models import ProcessMetadata


class TestSpatialChangeDetector:
    """Test SpatialChangeDetector functionality."""
    
    @pytest.fixture
    def mock_dependencies(self):
        """Create mock dependencies for SpatialChangeDetector."""
        layer_manager = Mock()
        metadata_manager = Mock()
        config_loader = Mock()
        return layer_manager, metadata_manager, config_loader
    
    @pytest.fixture
    def change_detector(self, mock_dependencies):
        """Create SpatialChangeDetector instance with mocked dependencies."""
        layer_manager, metadata_manager, config_loader = mock_dependencies
        
        # Mock the config loading to avoid file system dependencies
        with patch.object(SpatialChangeDetector, '_load_change_detection_config') as mock_load_config:
            mock_load_config.return_value = {
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
    def mock_layer(self):
        """Create mock ArcGIS layer."""
        layer = Mock()
        layer.query = Mock()
        return layer
    
    @pytest.fixture
    def mock_layer_metadata(self):
        """Create mock layer metadata."""
        metadata = Mock()
        metadata.layer_name = "Test Weed Locations"
        metadata.record_count = 1000
        return metadata

    def test_initialization(self, mock_dependencies):
        """Test SpatialChangeDetector initialization."""
        layer_manager, metadata_manager, config_loader = mock_dependencies
        
        with patch.object(SpatialChangeDetector, '_load_change_detection_config') as mock_load_config:
            mock_load_config.return_value = {"enabled": True}
            
            detector = SpatialChangeDetector(layer_manager, metadata_manager, config_loader)
            
            assert detector.layer_manager == layer_manager
            assert detector.metadata_manager == metadata_manager
            assert detector.config_loader == config_loader
            assert detector._change_config == {"enabled": True}
    
    def test_detect_changes_no_changes(self, change_detector, mock_dependencies, mock_layer, mock_layer_metadata):
        """Test change detection when no changes are detected."""
        layer_manager, metadata_manager, config_loader = mock_dependencies
        
        # Setup mocks for no changes scenario
        layer_manager.get_layer_metadata.return_value = mock_layer_metadata
        layer_manager.get_layer_by_id.return_value = mock_layer
        
        # Mock query responses for no changes
        def mock_query(**kwargs):
            if kwargs.get('return_count_only'):
                if 'EditDate_1' in kwargs.get('where', ''):
                    return 0  # No modified records
                return 1000  # Total records
            return Mock(features=[])
        
        mock_layer.query.side_effect = mock_query
        
        # Mock last processing timestamp
        with patch.object(change_detector, '_get_last_processing_timestamp') as mock_timestamp:
            mock_timestamp.return_value = datetime.now() - timedelta(days=1)
            
            result = change_detector.detect_changes("test-layer-123")
        
        assert result.layer_id == "test-layer-123"
        assert result.total_records == 1000
        assert result.modified_records == 0
        assert result.change_percentage == 0.0
        assert result.processing_recommendation == ProcessingType.NO_PROCESSING_NEEDED
        assert "No significant changes" in result.get_change_summary()
    
    def test_detect_changes_incremental_update(self, change_detector, mock_dependencies, mock_layer, mock_layer_metadata):
        """Test change detection when incremental update is recommended."""
        layer_manager, metadata_manager, config_loader = mock_dependencies
        
        layer_manager.get_layer_metadata.return_value = mock_layer_metadata
        layer_manager.get_layer_by_id.return_value = mock_layer
        
        # Mock query responses for 2% change (20 out of 1000 records)
        def mock_query(**kwargs):
            if kwargs.get('return_count_only'):
                if 'EditDate_1' in kwargs.get('where', ''):
                    return 20  # Modified records
                return 1000  # Total records
            # Return mock features with OBJECTID
            return Mock(features=[Mock(attributes={"OBJECTID": i}) for i in range(100, 120)])
        
        mock_layer.query.side_effect = mock_query
        
        with patch.object(change_detector, '_get_last_processing_timestamp') as mock_timestamp:
            mock_timestamp.return_value = datetime.now() - timedelta(days=1)
            
            result = change_detector.detect_changes("test-layer-123")
        
        assert result.layer_id == "test-layer-123"
        assert result.total_records == 1000
        assert result.modified_records == 20
        assert result.change_percentage == 2.0
        assert result.processing_recommendation == ProcessingType.INCREMENTAL_UPDATE
        assert "Incremental update recommended" in result.get_change_summary()
        assert len(result.change_details.get("modified_record_ids", [])) <= 100
    
    def test_detect_changes_full_reprocessing(self, change_detector, mock_dependencies, mock_layer, mock_layer_metadata):
        """Test change detection when full reprocessing is recommended."""
        layer_manager, metadata_manager, config_loader = mock_dependencies
        
        layer_manager.get_layer_metadata.return_value = mock_layer_metadata
        layer_manager.get_layer_by_id.return_value = mock_layer
        
        # Mock query responses for 30% change (300 out of 1000 records)
        def mock_query(**kwargs):
            if kwargs.get('return_count_only'):
                if 'EditDate_1' in kwargs.get('where', ''):
                    return 300  # Modified records
                return 1000  # Total records
            return Mock(features=[])
        
        mock_layer.query.side_effect = mock_query
        
        with patch.object(change_detector, '_get_last_processing_timestamp') as mock_timestamp:
            mock_timestamp.return_value = datetime.now() - timedelta(days=1)
            
            result = change_detector.detect_changes("test-layer-123")
        
        assert result.layer_id == "test-layer-123"
        assert result.total_records == 1000
        assert result.modified_records == 300
        assert result.change_percentage == 30.0
        assert result.processing_recommendation == ProcessingType.FULL_REPROCESSING
        assert "Full reprocessing recommended" in result.get_change_summary()
    
    def test_detect_changes_max_incremental_exceeded(self, change_detector, mock_dependencies, mock_layer, mock_layer_metadata):
        """Test that full reprocessing is recommended when max incremental records is exceeded."""
        layer_manager, metadata_manager, config_loader = mock_dependencies
        
        layer_manager.get_layer_metadata.return_value = mock_layer_metadata
        layer_manager.get_layer_by_id.return_value = mock_layer
        
        # Mock query responses for 1500 modified records (exceeds max_incremental_records of 1000)
        def mock_query(**kwargs):
            if kwargs.get('return_count_only'):
                if 'EditDate_1' in kwargs.get('where', ''):
                    return 1500  # Modified records exceeding limit
                return 10000  # Total records
            return Mock(features=[])
        
        mock_layer.query.side_effect = mock_query
        
        with patch.object(change_detector, '_get_last_processing_timestamp') as mock_timestamp:
            mock_timestamp.return_value = datetime.now() - timedelta(days=1)
            
            result = change_detector.detect_changes("test-layer-123")
        
        assert result.processing_recommendation == ProcessingType.FULL_REPROCESSING
        assert result.modified_records == 1500
        # Change percentage is 15%, below full_reprocess_percentage (25%)
        # but should still recommend full reprocessing due to record count
    
    def test_detect_changes_layer_access_error(self, change_detector, mock_dependencies):
        """Test change detection when layer access fails."""
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
    
    def test_compare_with_last_processing_no_metadata(self, change_detector, mock_dependencies):
        """Test processing decision when no previous metadata exists."""
        layer_manager, metadata_manager, config_loader = mock_dependencies
        
        # Mock no previous metadata
        metadata_manager.read_last_processing_metadata.return_value = None
        
        decision = change_detector.compare_with_last_processing("test-layer")
        
        assert decision.processing_type == ProcessingType.FULL_REPROCESSING
        assert decision.full_reprocess_required is True
        assert "No previous processing metadata found" in decision.reasoning
    
    def test_compare_with_last_processing_with_changes(self, change_detector, mock_dependencies, mock_layer, mock_layer_metadata):
        """Test processing decision when changes are detected since last processing."""
        layer_manager, metadata_manager, config_loader = mock_dependencies
        
        # Mock previous processing metadata
        last_processing = ProcessMetadata(
            process_timestamp=datetime.now() - timedelta(days=1),
            region_layer_id="region-123",
            region_layer_updated=datetime.now() - timedelta(days=2),
            district_layer_id="district-456",
            district_layer_updated=datetime.now() - timedelta(days=2),
            process_status="Success",
            records_processed=950,
            processing_duration=120.5,
            error_message=None
        )
        metadata_manager.read_last_processing_metadata.return_value = last_processing
        
        # Mock layer access and change detection
        layer_manager.get_layer_metadata.return_value = mock_layer_metadata
        layer_manager.get_layer_by_id.return_value = mock_layer
        
        def mock_query(**kwargs):
            if kwargs.get('return_count_only'):
                if 'EditDate_1' in kwargs.get('where', ''):
                    return 25  # Modified records
                return 1000  # Total records
            return Mock(features=[Mock(attributes={"OBJECTID": i}) for i in range(100, 125)])
        
        mock_layer.query.side_effect = mock_query
        
        decision = change_detector.compare_with_last_processing("test-layer")
        
        assert decision.processing_type == ProcessingType.INCREMENTAL_UPDATE
        assert decision.change_threshold_met is True
        assert decision.full_reprocess_required is False
        assert len(decision.target_records) == 25
        assert "where_clause" in decision.incremental_filters
        assert "EditDate_1 >" in decision.incremental_filters["where_clause"]
        assert decision.estimated_processing_time > 0
    
    def test_determine_processing_type_thresholds(self, change_detector):
        """Test processing type determination with various threshold scenarios."""
        # Test no changes
        result = change_detector._determine_processing_type(1000, 0, 0.0)
        assert result == ProcessingType.NO_PROCESSING_NEEDED
        
        # Test below incremental threshold
        result = change_detector._determine_processing_type(1000, 5, 0.5)
        assert result == ProcessingType.NO_PROCESSING_NEEDED
        
        # Test incremental update threshold met
        result = change_detector._determine_processing_type(1000, 15, 1.5)
        assert result == ProcessingType.INCREMENTAL_UPDATE
        
        # Test full reprocess percentage threshold exceeded
        result = change_detector._determine_processing_type(1000, 300, 30.0)
        assert result == ProcessingType.FULL_REPROCESSING
        
        # Test max incremental records exceeded
        result = change_detector._determine_processing_type(10000, 1500, 15.0)
        assert result == ProcessingType.FULL_REPROCESSING
    
    def test_get_last_processing_timestamp_fallback(self, change_detector, mock_dependencies):
        """Test last processing timestamp fallback when metadata is unavailable."""
        layer_manager, metadata_manager, config_loader = mock_dependencies
        
        # Mock metadata access failure
        metadata_manager.read_last_processing_metadata.side_effect = Exception("Database error")
        
        timestamp = change_detector._get_last_processing_timestamp()
        
        # Should return a timestamp approximately 30 days ago
        expected_fallback = datetime.now() - timedelta(days=30)
        time_diff = abs((timestamp - expected_fallback).total_seconds())
        assert time_diff < 60  # Within 1 minute tolerance
    
    def test_estimate_processing_time(self, change_detector, mock_dependencies, mock_layer_metadata):
        """Test processing time estimation for different scenarios."""
        from modules.spatial_field_updater.change_detection.change_detection_models import ChangeMetrics
        
        # Create test change metrics
        metrics = ChangeMetrics(
            records_analyzed=1000,
            edit_date_changes=50,
            geometry_changes=0,
            attribute_changes=50,
            processing_duration=2.0,
            last_check_timestamp=datetime.now()
        )
        
        # Test full reprocessing estimation
        result = ChangeDetectionResult(
            layer_id="test",
            total_records=10000,
            modified_records=2500,
            new_records=0,
            deleted_records=0,
            change_percentage=25.0,
            processing_recommendation=ProcessingType.FULL_REPROCESSING,
            change_metrics=metrics
        )
        
        estimated_time = change_detector._estimate_processing_time(result)
        assert estimated_time == 1000.0  # 10000 * 0.1
        
        # Test incremental processing estimation
        result.processing_recommendation = ProcessingType.INCREMENTAL_UPDATE
        result.modified_records = 100
        estimated_time = change_detector._estimate_processing_time(result)
        assert estimated_time == 20.0  # 100 * 0.1 * 2
        
        # Test no processing estimation
        result.processing_recommendation = ProcessingType.NO_PROCESSING_NEEDED
        estimated_time = change_detector._estimate_processing_time(result)
        assert estimated_time == 0.0
    
    def test_config_loading_with_file_not_found(self, mock_dependencies):
        """Test configuration loading when config file doesn't exist."""
        layer_manager, metadata_manager, config_loader = mock_dependencies
        
        # Test with file not found - should use defaults
        with patch('pathlib.Path.exists', return_value=False):
            detector = SpatialChangeDetector(layer_manager, metadata_manager, config_loader)
            
            config = detector._change_config
            assert config["enabled"] is True
            assert config["edit_date_field"] == "EditDate_1"
            assert config["thresholds"]["full_reprocess_percentage"] == 25.0
            assert config["thresholds"]["incremental_threshold_percentage"] == 1.0
    
    def test_config_loading_with_valid_file(self, mock_dependencies):
        """Test configuration loading when config file exists."""
        layer_manager, metadata_manager, config_loader = mock_dependencies
        
        mock_config = {
            "change_detection": {
                "enabled": True,
                "edit_date_field": "CustomEditDate",
                "thresholds": {
                    "full_reprocess_percentage": 30.0,
                    "incremental_threshold_percentage": 2.0,
                    "max_incremental_records": 500
                }
            }
        }
        
        with patch('pathlib.Path.exists', return_value=True), \
             patch('builtins.open', mock_data=mock_config), \
             patch('json.load', return_value=mock_config):
            
            detector = SpatialChangeDetector(layer_manager, metadata_manager, config_loader)
            
            config = detector._change_config
            assert config["edit_date_field"] == "CustomEditDate"
            assert config["thresholds"]["full_reprocess_percentage"] == 30.0
            assert config["thresholds"]["max_incremental_records"] == 500
    
    def test_get_configuration_summary(self, change_detector):
        """Test configuration summary generation."""
        summary = change_detector._get_configuration_summary()
        
        assert "thresholds" in summary
        assert "edit_date_field" in summary
        assert "enabled" in summary
        assert summary["edit_date_field"] == "EditDate_1"
        assert summary["enabled"] is True
    
    def test_modified_records_query_error_handling(self, change_detector, mock_layer):
        """Test handling of query errors when getting modified records."""
        # Mock query to raise an exception
        mock_layer.query.side_effect = Exception("Query timeout")
        
        timestamp = datetime.now() - timedelta(days=1)
        count, records = change_detector._get_modified_records(mock_layer, timestamp)
        
        assert count == 0
        assert records == []
    
    def test_new_records_query_error_handling(self, change_detector, mock_layer):
        """Test handling of query errors when getting new records count."""
        # Mock query to raise an exception
        mock_layer.query.side_effect = Exception("Query timeout")
        
        timestamp = datetime.now() - timedelta(days=1)
        count = change_detector._get_new_records_count(mock_layer, timestamp)
        
        assert count == 0
    
    def test_total_record_count_error_handling(self, change_detector, mock_layer):
        """Test handling of query errors when getting total record count."""
        # Mock query to raise an exception
        mock_layer.query.side_effect = Exception("Service unavailable")
        
        count = change_detector._get_total_record_count(mock_layer)
        
        assert count == 0


class TestChangeDetectorIntegration:
    """Integration tests for change detector with realistic scenarios."""
    
    @pytest.fixture
    def mock_dependencies(self):
        """Create mock dependencies for change detector."""
        layer_manager = Mock()
        metadata_manager = Mock()
        config_loader = Mock()
        return layer_manager, metadata_manager, config_loader
    
    @pytest.fixture
    def detector_with_real_config(self, mock_dependencies):
        """Create detector with realistic configuration."""
        layer_manager, metadata_manager, config_loader = mock_dependencies
        
        realistic_config = {
            "enabled": True,
            "edit_date_field": "EditDate_1",
            "thresholds": {
                "full_reprocess_percentage": 25.0,
                "incremental_threshold_percentage": 1.0,
                "max_incremental_records": 1000,
                "no_change_threshold_percentage": 0.1
            },
            "processing_decisions": {
                "default_processing_type": "incremental_update",
                "force_full_reprocess_days": 7,
                "max_incremental_age_hours": 24
            },
            "performance": {
                "batch_size": 100,
                "query_timeout_seconds": 60,
                "max_records_per_query": 5000
            }
        }
        
        with patch.object(SpatialChangeDetector, '_load_change_detection_config') as mock_load:
            mock_load.return_value = realistic_config
            return SpatialChangeDetector(layer_manager, metadata_manager, config_loader)
    
    def test_complete_change_detection_workflow(self, detector_with_real_config, mock_dependencies):
        """Test complete workflow from change detection to processing decision."""
        layer_manager, metadata_manager, config_loader = mock_dependencies
        
        # Setup realistic scenario
        mock_layer = Mock()
        mock_metadata = Mock()
        mock_metadata.layer_name = "Weed Locations"
        mock_metadata.record_count = 5000
        
        layer_manager.get_layer_metadata.return_value = mock_metadata
        layer_manager.get_layer_by_id.return_value = mock_layer
        
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
        
        # Mock layer queries for realistic scenario (75 changes out of 5000 records = 1.5%)
        def mock_query(**kwargs):
            if kwargs.get('return_count_only'):
                if 'EditDate_1' in kwargs.get('where', ''):
                    return 75  # Modified records
                return 5000  # Total records
            # Return mock modified record IDs
            return Mock(features=[Mock(attributes={"OBJECTID": 1000 + i}) for i in range(75)])
        
        mock_layer.query.side_effect = mock_query
        
        # Execute complete workflow
        decision = detector_with_real_config.compare_with_last_processing("weed-locations-layer")
        
        # Verify results
        assert decision.processing_type == ProcessingType.INCREMENTAL_UPDATE
        assert decision.change_threshold_met is True
        assert decision.full_reprocess_required is False
        assert len(decision.target_records) == 75
        assert decision.estimated_processing_time > 0
        assert "1.50% change" in decision.reasoning
        
        # Verify incremental filters
        assert "where_clause" in decision.incremental_filters
        assert "EditDate_1 >" in decision.incremental_filters["where_clause"]
        assert decision.incremental_filters["modified_count"] == 75
        
        # Verify configuration was used
        config_used = decision.configuration_used
        assert config_used["thresholds"]["full_reprocess_percentage"] == 25.0
        assert config_used["edit_date_field"] == "EditDate_1" 