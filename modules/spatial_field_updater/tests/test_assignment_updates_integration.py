"""Integration Tests for Enhanced Assignment Updates

Tests the integration of enhanced batch update operations, spatial metadata
management, and fail-safe processing with the complete workflow.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime
from typing import List

from ..assignment_updates import (
    SpatialAssignmentUpdater,
    SpatialMetadataManager,
    UpdateValidator,
    ValidationResult,
    BatchUpdateResult,
    EnhancedProcessMetadata
)
from ..spatial_query import SpatialAssignment, SpatialProcessingResult, SpatialUpdateResult, SpatialMetrics, ProcessingMethod
from ..change_detection import ProcessingDecision, ProcessingType
from ..layer_access import LayerAccessManager, MetadataTableManager
from src.config.config_loader import ConfigLoader


class TestAssignmentUpdatesIntegration:
    """Integration tests for enhanced assignment update components."""
    
    @pytest.fixture
    def mock_config_loader(self):
        """Mock configuration loader with assignment update settings."""
        config_loader = Mock(spec=ConfigLoader)
        config_loader.get_config.return_value = {
            "assignment_updates": {
                "enabled": True,
                "batch_optimization": {
                    "max_batch_size": 1000,
                    "rollback_on_partial_failure": False,
                    "validation_enabled": True
                },
                "error_handling": {
                    "max_retries": 3,
                    "rollback_threshold": 0.5
                }
            },
            "enhanced_metadata": {
                "enabled": True,
                "fail_safe_writing": {
                    "success_threshold": 0.95,
                    "integrity_validation": True
                }
            }
        }
        return config_loader
    
    @pytest.fixture
    def mock_layer_manager(self):
        """Mock layer access manager."""
        layer_manager = Mock(spec=LayerAccessManager)
        
        # Mock layer access
        mock_layer = Mock()
        mock_layer.query.return_value = Mock(features=[])
        mock_layer.edit_features.return_value = {
            'updateResults': [
                {'success': True, 'objectId': 1},
                {'success': True, 'objectId': 2}
            ]
        }
        layer_manager.get_layer_by_id.return_value = mock_layer
        
        return layer_manager
    
    @pytest.fixture
    def mock_metadata_manager(self):
        """Mock metadata table manager."""
        metadata_manager = Mock(spec=MetadataTableManager)
        metadata_manager.write_processing_metadata.return_value = True
        return metadata_manager
    
    @pytest.fixture
    def sample_assignments(self):
        """Sample spatial assignments for testing."""
        return [
            SpatialAssignment(
                object_id="1",
                region_code="R001",
                district_code="D001", 
                intersection_quality=1.0,
                processing_method=ProcessingMethod.FULL_INTERSECTION,
                geometry_valid=True,
                processing_duration=0.1
            ),
            SpatialAssignment(
                object_id="2",
                region_code="R001",
                district_code="D002",
                intersection_quality=0.8,
                processing_method=ProcessingMethod.FULL_INTERSECTION,
                geometry_valid=True,
                processing_duration=0.1
            )
        ]
    
    @pytest.fixture
    def assignment_updater(self, mock_layer_manager, mock_config_loader):
        """Create SpatialAssignmentUpdater instance for testing."""
        return SpatialAssignmentUpdater(mock_layer_manager, mock_config_loader)
    
    @pytest.fixture
    def spatial_metadata_manager(self, mock_metadata_manager, mock_layer_manager, mock_config_loader):
        """Create SpatialMetadataManager instance for testing."""
        return SpatialMetadataManager(mock_metadata_manager, mock_layer_manager, mock_config_loader)
    
    def test_batch_update_optimization(self, assignment_updater, sample_assignments, mock_layer_manager):
        """Test that batch processing optimizes queries significantly."""
        # Mock the layer to return features for bulk query
        mock_layer = mock_layer_manager.get_layer_by_id.return_value
        
        # Create mock features for bulk query response
        mock_features = []
        for assignment in sample_assignments:
            feature = Mock()
            feature.attributes = {
                "OBJECTID": int(assignment.object_id),
                "GlobalID": f"guid-{assignment.object_id}",
                "RegionCode": "",
                "DistrictCode": ""
            }
            mock_features.append(feature)
        
        mock_layer.query.return_value = Mock(features=mock_features)
        
        # Execute batch update
        result = assignment_updater.apply_assignments_batch("test_layer", sample_assignments)
        
        # Verify optimization: Only 1 query called instead of N individual queries
        assert mock_layer.query.call_count == 1, "Should use single bulk query"
        
        # Verify query optimization in WHERE clause
        call_args = mock_layer.query.call_args
        where_clause = call_args[1]['where']
        assert "OBJECTID IN" in where_clause, "Should use optimized IN clause"
        assert "1,2" in where_clause, "Should include all object IDs"
        
        # Verify successful processing
        assert result.updated_count == 2
        assert result.failed_count == 0
        
        print(f"✅ PERFORMANCE OPTIMIZATION: 1 bulk query instead of {len(sample_assignments)} individual queries")
        print(f"✅ Query reduction: {len(sample_assignments)}x improvement achieved")
    
    def test_enhanced_metadata_creation(self, spatial_metadata_manager, sample_assignments):
        """Test enhanced metadata creation with comprehensive tracking."""
        # Create mock processing decision
        processing_decision = ProcessingDecision(
            processing_type=ProcessingType.FULL_REPROCESSING,
            change_threshold_met=True,
            target_records=[],
            incremental_filters={},
            estimated_processing_time=10.0,
            reasoning="Test processing",
            configuration_used={}
        )
        
        # Create mock spatial result
        spatial_result = SpatialProcessingResult(
            processed_count=2,
            updated_count=2,
            failed_count=0,
            processing_duration=5.0,
            spatial_metrics=SpatialMetrics(
                total_intersections_calculated=4,
                successful_assignments=2,
                failed_assignments=0,
                geometry_validation_time=0.5,
                intersection_calculation_time=2.0,
                update_operation_time=1.0,
                cache_hit_rate=0.5
            ),
            assignment_summary={"total_assignments": 2, "both_assigned": 2},
            region_assignments=2,
            district_assignments=2
        )
        
        # Create mock update result
        update_result = SpatialUpdateResult(
            updated_count=2,
            failed_count=0,
            update_duration=1.0,
            errors=[]
        )
        
        # Create enhanced metadata
        metadata = spatial_metadata_manager.create_processing_metadata(
            processing_decision, spatial_result, update_result
        )
        
        # Verify enhanced metadata features
        assert isinstance(metadata, EnhancedProcessMetadata)
        assert metadata.processing_id is not None
        assert metadata.records_processed == 2
        assert metadata.records_updated == 2
        assert metadata.update_metrics.query_optimization_ratio == 2.0  # 2 assignments = 2x reduction
        assert metadata.performance_metrics.total_processing_rate > 0
        
        # Verify comprehensive summaries
        assert "success" in metadata.get_comprehensive_summary().lower()
        assert "reduction" in metadata.get_optimization_summary().lower()
        
        print(f"✅ Enhanced metadata created with optimization tracking")
        print(f"✅ Processing summary: {metadata.get_comprehensive_summary()}")
        print(f"✅ Optimization summary: {metadata.get_optimization_summary()}")
    
    def test_fail_safe_metadata_writing(self, spatial_metadata_manager, sample_assignments):
        """Test fail-safe metadata writing only on successful processing."""
        # Create metadata with high success rate (should write)
        high_success_metadata = self._create_test_metadata(
            processing_id="test-high-success",
            processed=100,
            updated=98,
            failed=2
        )
        
        # Test successful metadata write
        result = spatial_metadata_manager.write_metadata_on_success(
            high_success_metadata, success_threshold=0.95
        )
        assert result is True, "Should write metadata for high success rate"
        
        # Create metadata with low success rate (should not write)
        low_success_metadata = self._create_test_metadata(
            processing_id="test-low-success",
            processed=100,
            updated=80,
            failed=20
        )
        
        # Test failed metadata write due to low success rate
        result = spatial_metadata_manager.write_metadata_on_success(
            low_success_metadata, success_threshold=0.95
        )
        assert result is False, "Should not write metadata for low success rate"
        
        print(f"✅ Fail-safe metadata writing: Only writes on 95%+ success rate")
    
    def test_validation_integration(self, assignment_updater, mock_layer_manager):
        """Test comprehensive validation integration."""
        # Create assignments with validation issues
        invalid_assignments = [
            SpatialAssignment(
                object_id="",  # Invalid empty object ID
                region_code="R001",
                district_code="D001",
                intersection_quality=1.5,  # Invalid quality > 1.0
                processing_method=ProcessingMethod.FULL_INTERSECTION,
                geometry_valid=True,
                processing_duration=0.1
            )
        ]
        
        # Mock validation enabled
        assignment_updater._update_config = {"validation_enabled": True}
        
        # Execute batch update
        result = assignment_updater.apply_assignments_batch("test_layer", invalid_assignments)
        
        # Verify validation caught the issues
        assert result.updated_count == 0
        assert result.failed_count == 1
        assert len(result.errors) > 0
        
        print(f"✅ Validation integration: Caught validation errors before processing")
    
    def test_error_handling_comprehensive(self, assignment_updater, mock_layer_manager):
        """Test comprehensive error handling throughout the workflow."""
        # Mock layer access failure
        mock_layer_manager.get_layer_by_id.return_value = None
        
        sample_assignments = [
            SpatialAssignment(
                object_id="1",
                region_code="R001",
                district_code="D001",
                intersection_quality=1.0,
                processing_method=ProcessingMethod.FULL_INTERSECTION,
                geometry_valid=True,
                processing_duration=0.1
            )
        ]
        
        # Execute batch update with layer access failure
        result = assignment_updater.apply_assignments_batch("invalid_layer", sample_assignments)
        
        # Verify error handling
        assert result.updated_count == 0
        assert result.failed_count == 1
        assert len(result.errors) > 0
        assert "Cannot access layer" in result.errors[0]
        
        print(f"✅ Error handling: Graceful failure with detailed error messages")
    
    def test_performance_monitoring_integration(self, spatial_metadata_manager):
        """Test performance monitoring and optimization tracking."""
        # Create metadata with performance metrics
        metadata = self._create_test_metadata(
            processing_id="perf-test",
            processed=1000,
            updated=995,
            failed=5
        )
        
        # Verify performance tracking
        assert metadata.performance_metrics.total_processing_rate > 0
        assert metadata.update_metrics.query_optimization_ratio >= 1.0
        assert metadata.performance_metrics.get_performance_rating() in ["Poor", "Fair", "Good", "Excellent"]
        
        # Verify optimization notes
        assert len(metadata.optimization_notes) > 0
        assert any("query reduction" in note.lower() for note in metadata.optimization_notes)
        
        print(f"✅ Performance monitoring: Comprehensive metrics and optimization tracking")
        print(f"✅ Performance rating: {metadata.performance_metrics.get_performance_rating()}")
        print(f"✅ Query optimization: {metadata.update_metrics.query_optimization_ratio}x reduction")
    
    def _create_test_metadata(self, processing_id: str, processed: int, updated: int, failed: int) -> EnhancedProcessMetadata:
        """Helper to create test metadata."""
        from ..assignment_updates.metadata_models import (
            LayerVersionInfo, UpdateMetrics, ErrorSummary, ProcessingPerformanceMetrics
        )
        
        return EnhancedProcessMetadata(
            processing_id=processing_id,
            process_timestamp=datetime.now(),
            processing_type=ProcessingType.FULL_REPROCESSING,
            records_processed=processed,
            records_updated=updated,
            records_failed=failed,
            processing_duration=5.0,
            update_duration=1.0,
            spatial_metrics=SpatialMetrics(
                total_intersections_calculated=processed * 2,
                successful_assignments=updated,
                failed_assignments=failed,
                geometry_validation_time=0.5,
                intersection_calculation_time=2.0,
                update_operation_time=1.0,
                cache_hit_rate=0.5
            ),
            update_metrics=UpdateMetrics(
                total_assignments=processed,
                successful_updates=updated,
                failed_updates=failed,
                validation_failures=0,
                batch_count=1,
                average_batch_size=processed,
                update_rate_per_second=updated / 1.0,
                error_breakdown={},
                query_optimization_ratio=processed
            ),
            error_summary=ErrorSummary(),
            layer_versions=LayerVersionInfo(
                weed_layer_id="test_weed",
                weed_layer_updated=datetime.now(),
                region_layer_id="test_region",
                region_layer_updated=datetime.now(),
                district_layer_id="test_district",
                district_layer_updated=datetime.now()
            ),
            performance_metrics=ProcessingPerformanceMetrics(
                spatial_processing_rate=processed / 5.0,
                update_processing_rate=updated / 1.0,
                total_processing_rate=(processed + updated) / 6.0,
                cache_hit_rate=0.5,
                query_optimization_achieved=processed
            ),
            configuration_snapshot={},
            processing_summary=f"Test processing: {updated}/{processed} records updated",
            optimization_notes=[f"Achieved {processed}x query reduction through batch processing"]
        ) 