"""
Unit tests for change detection models.

Tests Pydantic model validation, serialization, and business logic
for the change detection system components.
"""

import pytest
from datetime import datetime, timedelta
from typing import Dict, Any

from modules.spatial_field_updater.change_detection.change_detection_models import (
    ProcessingType,
    ChangeMetrics,
    ChangeDetectionResult,
    ProcessingDecision
)


class TestProcessingType:
    """Test ProcessingType enum."""
    
    def test_processing_type_values(self):
        """Test that ProcessingType enum has expected values."""
        assert ProcessingType.FULL_REPROCESSING == "full_reprocessing"
        assert ProcessingType.INCREMENTAL_UPDATE == "incremental_update"
        assert ProcessingType.NO_PROCESSING_NEEDED == "no_processing_needed"
        assert ProcessingType.FORCE_FULL_UPDATE == "force_full_update"
    
    def test_processing_type_iteration(self):
        """Test that all processing types can be iterated."""
        expected_values = {
            "full_reprocessing", "incremental_update", 
            "no_processing_needed", "force_full_update"
        }
        actual_values = {pt.value for pt in ProcessingType}
        assert actual_values == expected_values


class TestChangeMetrics:
    """Test ChangeMetrics model."""
    
    def test_valid_change_metrics(self):
        """Test creating valid ChangeMetrics instance."""
        timestamp = datetime.now()
        metrics = ChangeMetrics(
            records_analyzed=1000,
            edit_date_changes=50,
            geometry_changes=10,
            attribute_changes=60,
            processing_duration=2.5,
            last_check_timestamp=timestamp
        )
        
        assert metrics.records_analyzed == 1000
        assert metrics.edit_date_changes == 50
        assert metrics.geometry_changes == 10
        assert metrics.attribute_changes == 60
        assert metrics.processing_duration == 2.5
        assert metrics.last_check_timestamp == timestamp
    
    def test_negative_values_validation(self):
        """Test that negative values are rejected."""
        timestamp = datetime.now()
        
        with pytest.raises(ValueError):
            ChangeMetrics(
                records_analyzed=-1,
                edit_date_changes=50,
                geometry_changes=10,
                attribute_changes=60,
                processing_duration=2.5,
                last_check_timestamp=timestamp
            )
        
        with pytest.raises(ValueError):
            ChangeMetrics(
                records_analyzed=1000,
                edit_date_changes=-1,
                geometry_changes=10,
                attribute_changes=60,
                processing_duration=2.5,
                last_check_timestamp=timestamp
            )
    
    def test_serialization(self):
        """Test ChangeMetrics serialization."""
        timestamp = datetime.now()
        metrics = ChangeMetrics(
            records_analyzed=1000,
            edit_date_changes=50,
            geometry_changes=10,
            attribute_changes=60,
            processing_duration=2.5,
            last_check_timestamp=timestamp
        )
        
        data = metrics.model_dump()
        assert isinstance(data, dict)
        assert data["records_analyzed"] == 1000
        assert data["edit_date_changes"] == 50


class TestChangeDetectionResult:
    """Test ChangeDetectionResult model."""
    
    @pytest.fixture
    def sample_change_metrics(self):
        """Create sample ChangeMetrics for testing."""
        return ChangeMetrics(
            records_analyzed=1000,
            edit_date_changes=50,
            geometry_changes=0,
            attribute_changes=50,
            processing_duration=2.5,
            last_check_timestamp=datetime.now()
        )
    
    def test_valid_change_detection_result(self, sample_change_metrics):
        """Test creating valid ChangeDetectionResult."""
        result = ChangeDetectionResult(
            layer_id="test-layer-123",
            total_records=1000,
            modified_records=50,
            new_records=5,
            deleted_records=2,
            change_percentage=5.0,
            processing_recommendation=ProcessingType.INCREMENTAL_UPDATE,
            change_details={"test": "data"},
            change_metrics=sample_change_metrics
        )
        
        assert result.layer_id == "test-layer-123"
        assert result.total_records == 1000
        assert result.modified_records == 50
        assert result.change_percentage == 5.0
        assert result.processing_recommendation == ProcessingType.INCREMENTAL_UPDATE
    
    def test_change_percentage_validation(self, sample_change_metrics):
        """Test change percentage validation and rounding."""
        # Test rounding
        result = ChangeDetectionResult(
            layer_id="test-layer",
            total_records=1000,
            modified_records=50,
            new_records=0,
            deleted_records=0,
            change_percentage=5.123456,
            processing_recommendation=ProcessingType.INCREMENTAL_UPDATE,
            change_metrics=sample_change_metrics
        )
        assert result.change_percentage == 5.12
        
        # Test normal valid values
        result = ChangeDetectionResult(
            layer_id="test-layer",
            total_records=1000,
            modified_records=50,
            new_records=0,
            deleted_records=0,
            change_percentage=25.0,
            processing_recommendation=ProcessingType.INCREMENTAL_UPDATE,
            change_metrics=sample_change_metrics
        )
        assert result.change_percentage == 25.0
    
    def test_empty_layer_id_validation(self, sample_change_metrics):
        """Test that empty layer_id is rejected."""
        with pytest.raises(ValueError):
            ChangeDetectionResult(
                layer_id="",
                total_records=1000,
                modified_records=50,
                new_records=0,
                deleted_records=0,
                change_percentage=5.0,
                processing_recommendation=ProcessingType.INCREMENTAL_UPDATE,
                change_metrics=sample_change_metrics
            )
    
    def test_get_change_summary(self, sample_change_metrics):
        """Test get_change_summary method."""
        # Test no processing needed
        result = ChangeDetectionResult(
            layer_id="test-layer",
            total_records=1000,
            modified_records=0,
            new_records=0,
            deleted_records=0,
            change_percentage=0.0,
            processing_recommendation=ProcessingType.NO_PROCESSING_NEEDED,
            change_metrics=sample_change_metrics
        )
        summary = result.get_change_summary()
        assert "No significant changes" in summary
        assert "0.0% change" in summary
        
        # Test incremental update
        result.processing_recommendation = ProcessingType.INCREMENTAL_UPDATE
        result.modified_records = 50
        result.change_percentage = 5.0
        summary = result.get_change_summary()
        assert "Incremental update recommended" in summary
        assert "50 records changed" in summary
        assert "5.0%" in summary
        
        # Test full reprocessing
        result.processing_recommendation = ProcessingType.FULL_REPROCESSING
        result.modified_records = 300
        result.change_percentage = 30.0
        summary = result.get_change_summary()
        assert "Full reprocessing recommended" in summary
        assert "300 records changed" in summary
        
        # Test force full update
        result.processing_recommendation = ProcessingType.FORCE_FULL_UPDATE
        result.change_details = {"error": "Connection timeout"}
        summary = result.get_change_summary()
        assert "Force full update required" in summary
        assert "Connection timeout" in summary


class TestProcessingDecision:
    """Test ProcessingDecision model."""
    
    def test_valid_processing_decision(self):
        """Test creating valid ProcessingDecision."""
        decision = ProcessingDecision(
            processing_type=ProcessingType.INCREMENTAL_UPDATE,
            target_records=["123", "456", "789"],
            change_threshold_met=True,
            full_reprocess_required=False,
            incremental_filters={"where": "EditDate_1 > 123456"},
            reasoning="5% change detected",
            estimated_processing_time=45.5
        )
        
        assert decision.processing_type == ProcessingType.INCREMENTAL_UPDATE
        assert len(decision.target_records) == 3
        assert decision.change_threshold_met is True
        assert decision.full_reprocess_required is False
        assert decision.reasoning == "5% change detected"
        assert decision.estimated_processing_time == 45.5
    
    def test_target_records_validation(self):
        """Test target_records validation and deduplication."""
        decision = ProcessingDecision(
            processing_type=ProcessingType.INCREMENTAL_UPDATE,
            target_records=["123", "456", "123", "", "  789  ", "456"],
            change_threshold_met=True,
            full_reprocess_required=False
        )
        
        # Should remove duplicates and empty strings, trim whitespace
        assert decision.target_records == ["123", "456", "789"]
    
    def test_is_processing_needed(self):
        """Test is_processing_needed method."""
        # No processing needed
        decision = ProcessingDecision(
            processing_type=ProcessingType.NO_PROCESSING_NEEDED,
            change_threshold_met=False,
            full_reprocess_required=False
        )
        assert decision.is_processing_needed() is False
        
        # Incremental processing needed
        decision.processing_type = ProcessingType.INCREMENTAL_UPDATE
        assert decision.is_processing_needed() is True
        
        # Full processing needed
        decision.processing_type = ProcessingType.FULL_REPROCESSING
        assert decision.is_processing_needed() is True
        
        # Force full processing needed
        decision.processing_type = ProcessingType.FORCE_FULL_UPDATE
        assert decision.is_processing_needed() is True
    
    def test_get_processing_summary(self):
        """Test get_processing_summary method."""
        # No processing
        decision = ProcessingDecision(
            processing_type=ProcessingType.NO_PROCESSING_NEEDED,
            change_threshold_met=False,
            full_reprocess_required=False
        )
        assert decision.get_processing_summary() == "No processing needed"
        
        # Incremental processing
        decision = ProcessingDecision(
            processing_type=ProcessingType.INCREMENTAL_UPDATE,
            target_records=["123", "456", "789"],
            change_threshold_met=True,
            full_reprocess_required=False
        )
        summary = decision.get_processing_summary()
        assert "Incremental processing" in summary
        assert "3 records" in summary
        
        # Full processing
        decision.processing_type = ProcessingType.FULL_REPROCESSING
        assert decision.get_processing_summary() == "Full reprocessing required"
        
        # Force full processing
        decision.processing_type = ProcessingType.FORCE_FULL_UPDATE
        assert decision.get_processing_summary() == "Force full reprocessing"
    
    def test_negative_estimated_time_validation(self):
        """Test that negative estimated processing time is rejected."""
        with pytest.raises(ValueError):
            ProcessingDecision(
                processing_type=ProcessingType.INCREMENTAL_UPDATE,
                change_threshold_met=True,
                full_reprocess_required=False,
                estimated_processing_time=-5.0
            )
    
    def test_large_target_records_list(self):
        """Test handling of large target records list."""
        # Create a list just under the limit
        large_list = [str(i) for i in range(9999)]
        decision = ProcessingDecision(
            processing_type=ProcessingType.INCREMENTAL_UPDATE,
            target_records=large_list,
            change_threshold_met=True,
            full_reprocess_required=False
        )
        assert len(decision.target_records) == 9999
        
        # Test that validation would reject lists that are too large
        # (This would need to be tested at the Pydantic level)
    
    def test_serialization_and_deserialization(self):
        """Test model serialization and deserialization."""
        original = ProcessingDecision(
            processing_type=ProcessingType.INCREMENTAL_UPDATE,
            target_records=["123", "456"],
            change_threshold_met=True,
            full_reprocess_required=False,
            incremental_filters={"where": "EditDate_1 > 123456"},
            reasoning="Test reasoning",
            estimated_processing_time=30.0,
            configuration_used={"threshold": 1.0}
        )
        
        # Serialize to dict
        data = original.model_dump()
        assert isinstance(data, dict)
        assert data["processing_type"] == "incremental_update"
        
        # Deserialize from dict
        recreated = ProcessingDecision(**data)
        assert recreated.processing_type == original.processing_type
        assert recreated.target_records == original.target_records
        assert recreated.reasoning == original.reasoning


class TestModelIntegration:
    """Test integration between models."""
    
    def test_change_detection_result_with_metrics(self):
        """Test ChangeDetectionResult with embedded ChangeMetrics."""
        metrics = ChangeMetrics(
            records_analyzed=1000,
            edit_date_changes=50,
            geometry_changes=0,
            attribute_changes=50,
            processing_duration=2.5,
            last_check_timestamp=datetime.now()
        )
        
        result = ChangeDetectionResult(
            layer_id="test-layer",
            total_records=1000,
            modified_records=50,
            new_records=5,
            deleted_records=0,
            change_percentage=5.0,
            processing_recommendation=ProcessingType.INCREMENTAL_UPDATE,
            change_metrics=metrics
        )
        
        # Test that metrics are properly embedded
        assert result.change_metrics.records_analyzed == 1000
        assert result.change_metrics.edit_date_changes == 50
        assert result.change_metrics.processing_duration == 2.5
    
    def test_complete_workflow_models(self):
        """Test a complete workflow using all models together."""
        # Create change metrics
        metrics = ChangeMetrics(
            records_analyzed=10000,
            edit_date_changes=125,
            geometry_changes=0,
            attribute_changes=125,
            processing_duration=3.2,
            last_check_timestamp=datetime.now()
        )
        
        # Create change detection result
        result = ChangeDetectionResult(
            layer_id="weed-locations-layer",
            total_records=10000,
            modified_records=125,
            new_records=10,
            deleted_records=3,
            change_percentage=1.25,
            processing_recommendation=ProcessingType.INCREMENTAL_UPDATE,
            change_details={
                "since_timestamp": (datetime.now() - timedelta(hours=24)).isoformat(),
                "edit_date_field": "EditDate_1",
                "detection_method": "edit_date_monitoring"
            },
            change_metrics=metrics
        )
        
        # Create processing decision based on result
        decision = ProcessingDecision(
            processing_type=result.processing_recommendation,
            target_records=[str(i) for i in range(100, 225)],  # 125 records
            change_threshold_met=True,
            full_reprocess_required=False,
            incremental_filters={
                "where_clause": "EditDate_1 > 1705301400000",
                "modified_count": result.modified_records
            },
            reasoning=f"Change detection found {result.modified_records} modified records ({result.change_percentage:.2f}% change)",
            estimated_processing_time=result.modified_records * 0.1,
            configuration_used={
                "full_reprocess_percentage": 25.0,
                "incremental_threshold_percentage": 1.0,
                "max_incremental_records": 1000
            }
        )
        
        # Verify the workflow
        assert result.get_change_summary() == "Incremental update recommended: 125 records changed (1.2%)"
        assert decision.is_processing_needed() is True
        assert decision.get_processing_summary() == "Incremental processing: 125 records"
        assert len(decision.target_records) == 125
        assert decision.estimated_processing_time == 12.5  # 125 * 0.1 