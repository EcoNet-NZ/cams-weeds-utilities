"""Unit tests for spatial query processing models.

Tests Pydantic model validation, serialization, and calculation methods
for spatial processing results and assignments.
"""

import pytest
from datetime import datetime
from typing import Dict, Any

from modules.spatial_field_updater.spatial_query.spatial_query_models import (
    ProcessingMethod,
    SpatialAssignment,
    BatchResult,
    SpatialMetrics,
    SpatialProcessingResult,
    SpatialProcessingConfig,
    SpatialUpdateResult
)


class TestProcessingMethod:
    """Test ProcessingMethod enum."""
    
    def test_processing_method_values(self):
        """Test all ProcessingMethod enum values."""
        assert ProcessingMethod.FULL_INTERSECTION == "full_intersection"
        assert ProcessingMethod.CACHED_INTERSECTION == "cached_intersection"
        assert ProcessingMethod.GEOMETRY_REPAIR == "geometry_repair"
        assert ProcessingMethod.FALLBACK_ASSIGNMENT == "fallback_assignment"


class TestSpatialAssignment:
    """Test SpatialAssignment model validation and methods."""
    
    def test_spatial_assignment_creation(self):
        """Test creating a valid SpatialAssignment."""
        assignment = SpatialAssignment(
            object_id="123",
            region_code="R001",
            district_code="D001",
            intersection_quality=0.95,
            processing_method=ProcessingMethod.FULL_INTERSECTION,
            geometry_valid=True,
            processing_duration=0.1
        )
        
        assert assignment.object_id == "123"
        assert assignment.region_code == "R001"
        assert assignment.district_code == "D001"
        assert assignment.intersection_quality == 0.95
        assert assignment.processing_method == ProcessingMethod.FULL_INTERSECTION
        assert assignment.geometry_valid is True
        assert assignment.processing_duration == 0.1
    
    def test_intersection_quality_validation(self):
        """Test intersection quality is bounded between 0 and 1."""
        # Test that values outside bounds raise validation errors
        with pytest.raises(ValueError, match="Input should be less than or equal to 1"):
            SpatialAssignment(
                object_id="123",
                intersection_quality=1.5,  # Should raise validation error
                processing_method=ProcessingMethod.FULL_INTERSECTION,
                geometry_valid=True,
                processing_duration=0.1
            )
        
        with pytest.raises(ValueError, match="Input should be greater than or equal to 0"):
            SpatialAssignment(
                object_id="123",
                intersection_quality=-0.1,  # Should raise validation error
                processing_method=ProcessingMethod.FULL_INTERSECTION,
                geometry_valid=True,
                processing_duration=0.1
            )
        
        # Test valid boundary values
        assignment_max = SpatialAssignment(
            object_id="123",
            intersection_quality=1.0,  # Valid max value
            processing_method=ProcessingMethod.FULL_INTERSECTION,
            geometry_valid=True,
            processing_duration=0.1
        )
        assert assignment_max.intersection_quality == 1.0
        
        assignment_min = SpatialAssignment(
            object_id="123",
            intersection_quality=0.0,  # Valid min value
            processing_method=ProcessingMethod.FULL_INTERSECTION,
            geometry_valid=True,
            processing_duration=0.1
        )
        assert assignment_min.intersection_quality == 0.0
    
    def test_assignment_status_methods(self):
        """Test assignment status helper methods."""
        # Both assigned
        both_assigned = SpatialAssignment(
            object_id="123",
            region_code="R001",
            district_code="D001",
            intersection_quality=1.0,
            processing_method=ProcessingMethod.FULL_INTERSECTION,
            geometry_valid=True,
            processing_duration=0.1
        )
        assert both_assigned.get_assignment_status() == "both_assigned"
        assert both_assigned.is_successful() is True
        
        # Region only
        region_only = SpatialAssignment(
            object_id="123",
            region_code="R001",
            district_code=None,
            intersection_quality=0.5,
            processing_method=ProcessingMethod.FULL_INTERSECTION,
            geometry_valid=True,
            processing_duration=0.1
        )
        assert region_only.get_assignment_status() == "region_only"
        assert region_only.is_successful() is True
        
        # District only
        district_only = SpatialAssignment(
            object_id="123",
            region_code=None,
            district_code="D001",
            intersection_quality=0.5,
            processing_method=ProcessingMethod.FULL_INTERSECTION,
            geometry_valid=True,
            processing_duration=0.1
        )
        assert district_only.get_assignment_status() == "district_only"
        assert district_only.is_successful() is True
        
        # No assignment
        no_assignment = SpatialAssignment(
            object_id="123",
            region_code=None,
            district_code=None,
            intersection_quality=0.0,
            processing_method=ProcessingMethod.FALLBACK_ASSIGNMENT,
            geometry_valid=False,
            processing_duration=0.1
        )
        assert no_assignment.get_assignment_status() == "no_assignment"
        assert no_assignment.is_successful() is False


class TestBatchResult:
    """Test BatchResult model validation and methods."""
    
    def test_batch_result_creation(self):
        """Test creating a valid BatchResult."""
        batch_result = BatchResult(
            batch_number=1,
            records_processed=100,
            success_count=95,
            error_count=5,
            processing_time=2.5,
            errors=["Error in record 23", "Error in record 67"],
            assignment_summary={"both_assigned": 80, "region_only": 15}
        )
        
        assert batch_result.batch_number == 1
        assert batch_result.records_processed == 100
        assert batch_result.success_count == 95
        assert batch_result.error_count == 5
        assert batch_result.processing_time == 2.5
        assert len(batch_result.errors) == 2
        assert batch_result.assignment_summary["both_assigned"] == 80
    
    def test_batch_result_calculation_methods(self):
        """Test BatchResult calculation methods."""
        batch_result = BatchResult(
            batch_number=1,
            records_processed=100,
            success_count=95,
            error_count=5,
            processing_time=2.0
        )
        
        # Test success rate
        assert batch_result.get_success_rate() == 0.95
        
        # Test processing rate
        assert batch_result.get_processing_rate() == 50.0  # 100 records / 2 seconds
    
    def test_batch_result_edge_cases(self):
        """Test BatchResult edge cases."""
        # Zero processing time
        zero_time = BatchResult(
            batch_number=1,
            records_processed=100,
            success_count=100,
            error_count=0,
            processing_time=0.0
        )
        assert zero_time.get_processing_rate() == 0.0
        
        # Zero records processed
        zero_records = BatchResult(
            batch_number=1,
            records_processed=0,
            success_count=0,
            error_count=0,
            processing_time=1.0
        )
        assert zero_records.get_success_rate() == 0.0


class TestSpatialMetrics:
    """Test SpatialMetrics model validation and methods."""
    
    def test_spatial_metrics_creation(self):
        """Test creating valid SpatialMetrics."""
        metrics = SpatialMetrics(
            total_intersections_calculated=200,
            successful_assignments=180,
            failed_assignments=20,
            geometry_validation_time=0.5,
            intersection_calculation_time=2.0,
            update_operation_time=1.0,
            memory_peak_mb=512.5,
            cache_hit_rate=0.85
        )
        
        assert metrics.total_intersections_calculated == 200
        assert metrics.successful_assignments == 180
        assert metrics.failed_assignments == 20
        assert metrics.memory_peak_mb == 512.5
        assert metrics.cache_hit_rate == 0.85
    
    def test_spatial_metrics_calculations(self):
        """Test SpatialMetrics calculation methods."""
        metrics = SpatialMetrics(
            total_intersections_calculated=200,
            successful_assignments=180,
            failed_assignments=20,
            geometry_validation_time=0.5,
            intersection_calculation_time=2.0,
            update_operation_time=1.0,
            cache_hit_rate=0.85
        )
        
        # Test total processing time
        assert metrics.get_total_processing_time() == 3.5
        
        # Test success rate
        assert metrics.get_success_rate() == 0.9  # 180/200
        
        # Test intersection rate
        assert metrics.get_intersection_rate() == 100.0  # 200/2.0
        
        # Test performance summary
        summary = metrics.get_performance_summary()
        assert summary["total_time"] == 3.5
        assert summary["success_rate"] == 0.9
        assert summary["intersection_rate"] == 100.0
        assert summary["cache_efficiency"] == 0.85


class TestSpatialProcessingResult:
    """Test SpatialProcessingResult model validation and methods."""
    
    def test_spatial_processing_result_creation(self):
        """Test creating a valid SpatialProcessingResult."""
        spatial_metrics = SpatialMetrics(
            total_intersections_calculated=200,
            successful_assignments=180,
            failed_assignments=20,
            geometry_validation_time=0.5,
            intersection_calculation_time=2.0,
            update_operation_time=1.0,
            cache_hit_rate=0.85
        )
        
        batch_result = BatchResult(
            batch_number=1,
            records_processed=100,
            success_count=95,
            error_count=5,
            processing_time=2.0
        )
        
        result = SpatialProcessingResult(
            processed_count=100,
            updated_count=95,
            failed_count=5,
            processing_duration=3.5,
            batch_results=[batch_result],
            spatial_metrics=spatial_metrics,
            assignment_summary={"both_assigned": 80, "region_only": 15},
            region_assignments=95,
            district_assignments=80
        )
        
        assert result.processed_count == 100
        assert result.updated_count == 95
        assert result.failed_count == 5
        assert result.processing_duration == 3.5
        assert len(result.batch_results) == 1
        assert result.region_assignments == 95
        assert result.district_assignments == 80
    
    def test_processing_result_summary_methods(self):
        """Test SpatialProcessingResult summary methods."""
        spatial_metrics = SpatialMetrics(
            total_intersections_calculated=200,
            successful_assignments=180,
            failed_assignments=20,
            geometry_validation_time=0.5,
            intersection_calculation_time=2.0,
            update_operation_time=1.0,
            cache_hit_rate=0.85
        )
        
        result = SpatialProcessingResult(
            processed_count=100,
            updated_count=95,
            failed_count=5,
            processing_duration=2.0,
            spatial_metrics=spatial_metrics,
            assignment_summary={
                "both_assigned": 80,
                "region_only": 15,
                "district_only": 0,
                "no_assignment": 5
            },
            region_assignments=95,
            district_assignments=80
        )
        
        # Test processing summary
        summary = result.get_processing_summary()
        assert "100 records" in summary
        assert "2.0s" in summary
        assert "90.0%" in summary  # Success rate
        assert "50.0 records/sec" in summary
        
        # Test assignment breakdown
        breakdown = result.get_assignment_breakdown()
        assert breakdown["both_assigned"] == 80
        assert breakdown["region_only"] == 15
        assert breakdown["district_only"] == 0
        assert breakdown["no_assignment"] == 5
        
        # Test processing efficiency
        efficiency = result.get_processing_efficiency()
        assert efficiency["overall_rate"] == 50.0  # 100/2.0
        assert efficiency["update_rate"] == 47.5   # 95/2.0
        assert efficiency["failure_rate"] == 2.5   # 5/2.0
        
        # Test success check
        assert result.is_successful() is True  # >50% success rate


class TestSpatialProcessingConfig:
    """Test SpatialProcessingConfig model validation."""
    
    def test_spatial_processing_config_defaults(self):
        """Test SpatialProcessingConfig default values."""
        config = SpatialProcessingConfig()
        
        assert config.enabled is True
        assert config.batch_size == 250
        assert config.max_batch_size == 1000
        assert config.geometry_validation_enabled is True
        assert config.repair_invalid_geometry is True
        assert config.cache_boundary_layers is True
        assert config.memory_limit_mb == 1024
        assert config.quality_threshold == 0.0
    
    def test_spatial_processing_config_validation(self):
        """Test SpatialProcessingConfig validation rules."""
        # Test max_batch_size adjustment
        config = SpatialProcessingConfig(
            batch_size=500,
            max_batch_size=300  # Smaller than batch_size
        )
        assert config.max_batch_size == 500  # Should be adjusted to match batch_size
    
    def test_spatial_processing_config_bounds(self):
        """Test SpatialProcessingConfig bounds validation."""
        with pytest.raises(ValueError):
            # batch_size too small
            SpatialProcessingConfig(batch_size=0)
        
        with pytest.raises(ValueError):
            # batch_size too large
            SpatialProcessingConfig(batch_size=10000)
        
        with pytest.raises(ValueError):
            # quality_threshold out of bounds
            SpatialProcessingConfig(quality_threshold=1.5)


class TestSpatialUpdateResult:
    """Test SpatialUpdateResult model validation and methods."""
    
    def test_spatial_update_result_creation(self):
        """Test creating a valid SpatialUpdateResult."""
        update_result = SpatialUpdateResult(
            updated_count=95,
            failed_count=5,
            update_duration=1.5,
            errors=["Failed to update record 23"],
            batch_updates=[{"batch": 1, "updated": 95, "failed": 5}]
        )
        
        assert update_result.updated_count == 95
        assert update_result.failed_count == 5
        assert update_result.update_duration == 1.5
        assert len(update_result.errors) == 1
        assert len(update_result.batch_updates) == 1
    
    def test_spatial_update_result_calculations(self):
        """Test SpatialUpdateResult calculation methods."""
        update_result = SpatialUpdateResult(
            updated_count=95,
            failed_count=5,
            update_duration=2.0
        )
        
        # Test update success rate
        assert update_result.get_update_success_rate() == 0.95  # 95/100
        
        # Test update rate
        assert update_result.get_update_rate() == 47.5  # 95/2.0
    
    def test_spatial_update_result_edge_cases(self):
        """Test SpatialUpdateResult edge cases."""
        # Zero updates
        zero_updates = SpatialUpdateResult(
            updated_count=0,
            failed_count=0,
            update_duration=1.0
        )
        assert zero_updates.get_update_success_rate() == 0.0
        assert zero_updates.get_update_rate() == 0.0
        
        # Zero duration
        zero_duration = SpatialUpdateResult(
            updated_count=100,
            failed_count=0,
            update_duration=0.0
        )
        assert zero_duration.get_update_rate() == 0.0 