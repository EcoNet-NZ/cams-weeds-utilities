"""Integration tests for spatial query processing system.

Tests the complete end-to-end workflow of spatial intersection processing
including SpatialFieldUpdater integration, change detection, and spatial
query processing with Context7 best practices.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime
from typing import List

from modules.spatial_field_updater.spatial_query import (
    SpatialQueryProcessor, SpatialProcessingResult, SpatialAssignment,
    ProcessingMethod, SpatialMetrics, BatchResult
)
from modules.spatial_field_updater.processor import SpatialFieldUpdater
from modules.spatial_field_updater.change_detection import (
    ProcessingDecision, ProcessingType, ChangeDetectionResult
)


class TestSpatialQueryIntegration:
    """Integration tests for spatial query processing components."""
    
    @pytest.fixture
    def mock_config_loader(self):
        """Create mock config loader with comprehensive configuration."""
        config_loader = Mock()
        config_loader.get_config.return_value = {
            "spatial_processing": {
                "batch_size": 5,  # Small batch for testing
                "geometry_validation": {"enabled": True},
                "intersection_optimization": {"cache_boundary_layers": True}
            },
            "area_layers": {
                "region": {
                    "layer_id": "region-layer-123",
                    "source_code_field": "REGC_code"
                },
                "district": {
                    "layer_id": "district-layer-456",
                    "source_code_field": "TALB_code"
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
            },
            "processing": {
                "batch_size": 100,
                "max_retries": 3,
                "timeout_seconds": 1800
            },
            "metadata_table": {
                "production_name": "Weeds Area Metadata",
                "development_name": "XXX Weeds Area Metadata DEV"
            },
            "validation": {
                "required_fields": ["object_id", "global_id", "geometry", "edit_date"],
                "field_mappings": {
                    "object_id": "OBJECTID",
                    "global_id": "GlobalID",
                    "edit_date": "EditDate_1"
                }
            }
        }
        return config_loader
    
    @pytest.fixture
    def mock_layer_manager(self):
        """Create mock layer manager with test data."""
        layer_manager = Mock()
        
        # Mock weed locations layer
        mock_weed_layer = Mock()
        mock_weed_features = self._create_mock_weed_features(10)
        mock_weed_layer.query.return_value = Mock(features=mock_weed_features)
        
        # Mock boundary layers
        mock_region_layer = Mock()
        mock_district_layer = Mock()
        
        # Mock intersection results
        mock_region_result = Mock()
        mock_region_result.features = [Mock(attributes={"REGC_code": "R001"})]
        mock_region_layer.query.return_value = mock_region_result
        
        mock_district_result = Mock()
        mock_district_result.features = [Mock(attributes={"TALB_code": "D001"})]
        mock_district_layer.query.return_value = mock_district_result
        
        # Configure layer manager to return appropriate layers
        def get_layer_side_effect(layer_id):
            if layer_id == "weed-locations":
                return mock_weed_layer
            elif layer_id == "region-layer-123":
                return mock_region_layer
            elif layer_id == "district-layer-456":
                return mock_district_layer
            else:
                return None
        
        layer_manager.get_layer_by_id.side_effect = get_layer_side_effect
        
        return layer_manager, mock_weed_layer, mock_region_layer, mock_district_layer
    
    def _create_mock_weed_features(self, count: int) -> List[Mock]:
        """Create mock weed location features for testing."""
        features = []
        for i in range(count):
            feature = Mock()
            feature.attributes = {
                "OBJECTID": 1000 + i,
                "GlobalID": f"guid-{i}",
                "RegionCode": None,
                "DistrictCode": None
            }
            feature.geometry = Mock()
            feature.geometry.x = -122.4194 + (i * 0.001)
            feature.geometry.y = 37.7749 + (i * 0.001)
            features.append(feature)
        return features
    
    def test_end_to_end_spatial_processing_workflow(self, mock_config_loader, mock_layer_manager):
        """Test complete end-to-end spatial processing workflow."""
        layer_manager, mock_weed_layer, mock_region_layer, mock_district_layer = mock_layer_manager
        
        # Create spatial processor
        spatial_processor = SpatialQueryProcessor(layer_manager, mock_config_loader)
        
        # Mock boundary layer retrieval
        with patch.object(spatial_processor, '_get_boundary_layer') as mock_get_boundary:
            def boundary_side_effect(layer_type):
                if layer_type == "region":
                    return mock_region_layer
                elif layer_type == "district":
                    return mock_district_layer
                else:
                    raise ValueError(f"Unknown layer type: {layer_type}")
            
            mock_get_boundary.side_effect = boundary_side_effect
            
            # Mock update operations
            with patch.object(spatial_processor, '_apply_spatial_assignments') as mock_apply:
                from modules.spatial_field_updater.spatial_query.spatial_query_models import SpatialUpdateResult
                mock_apply.return_value = SpatialUpdateResult(
                    updated_count=10, failed_count=0, update_duration=0.5
                )
                
                # Execute full spatial processing
                result = spatial_processor.process_spatial_intersections("weed-locations")
                
                # Verify comprehensive results
                assert isinstance(result, SpatialProcessingResult)
                assert result.processed_count == 10
                assert result.updated_count == 10
                assert result.failed_count == 0
                
                # Verify batch processing occurred (10 features / 5 batch_size = 2 batches)
                assert len(result.batch_results) == 2
                assert result.batch_results[0].records_processed == 5
                assert result.batch_results[1].records_processed == 5
                
                # Verify spatial metrics
                assert result.spatial_metrics.total_intersections_calculated == 20  # 10 features * 2 intersections
                assert result.spatial_metrics.successful_assignments == 10
                assert result.spatial_metrics.failed_assignments == 0
                
                # Verify assignment breakdown
                breakdown = result.get_assignment_breakdown()
                assert breakdown["both_assigned"] == 10
                
                # Verify processing summary
                summary = result.get_processing_summary()
                assert "10 records" in summary
                assert "100.0%" in summary  # Success rate
    
    def test_spatial_field_updater_integration_full_workflow(self, mock_config_loader):
        """Test SpatialFieldUpdater integration with spatial processing."""
        # Create SpatialFieldUpdater
        spatial_updater = SpatialFieldUpdater(mock_config_loader)
        
        # Mock connector and initialization
        mock_connector = Mock()
        spatial_updater.connector = mock_connector
        
        # Mock layer access components
        with patch.object(spatial_updater, '_initialize_layer_access'):
            # Mock layer manager
            mock_layer_manager = Mock()
            spatial_updater.layer_manager = mock_layer_manager
            
            # Mock change detector
            mock_change_detector = Mock()
            spatial_updater.change_detector = mock_change_detector
            
            # Mock spatial processor with successful results
            mock_spatial_processor = Mock()
            mock_spatial_result = Mock()
            mock_spatial_result.updated_count = 100
            mock_spatial_result.get_processing_summary.return_value = "Processed 100 records successfully"
            mock_spatial_result.get_assignment_breakdown.return_value = {"both_assigned": 90, "region_only": 10}
            mock_spatial_result.spatial_metrics = Mock()
            mock_spatial_result.spatial_metrics.total_intersections_calculated = 200
            mock_spatial_result.spatial_metrics.get_success_rate.return_value = 0.95
            mock_spatial_result.spatial_metrics.get_total_processing_time.return_value = 5.0
            
            mock_spatial_processor.process_spatial_intersections.return_value = mock_spatial_result
            spatial_updater.spatial_processor = mock_spatial_processor
            
            # Mock change detection result for full reprocessing
            mock_change_decision = ProcessingDecision(
                processing_type=ProcessingType.FULL_REPROCESSING,
                target_records=[],
                change_threshold_met=True,
                full_reprocess_required=True
            )
            mock_change_detector.compare_with_last_processing.return_value = mock_change_decision
            
            # Mock metadata components
            mock_metadata_manager = Mock()
            spatial_updater.metadata_manager = mock_metadata_manager
            
            # Mock configuration validation
            with patch.object(spatial_updater, 'validate_configuration', return_value=True):
                # Execute processing
                result = spatial_updater.process(dry_run=False)
                
                # Verify successful processing
                assert result.success is True
                assert result.records_processed == 100
                assert "Processed 100 records successfully" in str(result.details)
                
                # Verify spatial processor was called for full reprocessing
                mock_spatial_processor.process_spatial_intersections.assert_called_once_with("weed-locations")
    
    def test_spatial_field_updater_incremental_processing_workflow(self, mock_config_loader):
        """Test SpatialFieldUpdater incremental processing workflow."""
        # Create SpatialFieldUpdater
        spatial_updater = SpatialFieldUpdater(mock_config_loader)
        
        # Mock connector and initialization
        mock_connector = Mock()
        spatial_updater.connector = mock_connector
        
        # Mock layer access components
        with patch.object(spatial_updater, '_initialize_layer_access'):
            # Mock change detector for incremental processing
            mock_change_detector = Mock()
            spatial_updater.change_detector = mock_change_detector
            
            # Mock spatial processor for incremental results
            mock_spatial_processor = Mock()
            mock_spatial_result = Mock()
            mock_spatial_result.updated_count = 15
            mock_spatial_result.get_processing_summary.return_value = "Processed 15 records incrementally"
            mock_spatial_result.get_assignment_breakdown.return_value = {"both_assigned": 15}
            mock_spatial_result.spatial_metrics = Mock()
            mock_spatial_result.spatial_metrics.total_intersections_calculated = 30
            mock_spatial_result.spatial_metrics.get_success_rate.return_value = 1.0
            mock_spatial_result.spatial_metrics.get_total_processing_time.return_value = 1.5
            
            mock_spatial_processor.process_spatial_intersections.return_value = mock_spatial_result
            spatial_updater.spatial_processor = mock_spatial_processor
            
            # Mock change detection for incremental update
            target_records = ["123", "456", "789"]
            mock_change_decision = ProcessingDecision(
                processing_type=ProcessingType.INCREMENTAL_UPDATE,
                target_records=target_records,
                change_threshold_met=True,
                full_reprocess_required=False
            )
            mock_change_detector.compare_with_last_processing.return_value = mock_change_decision
            
            # Mock metadata components
            mock_metadata_manager = Mock()
            spatial_updater.metadata_manager = mock_metadata_manager
            
            # Mock configuration validation
            with patch.object(spatial_updater, 'validate_configuration', return_value=True):
                # Execute incremental processing
                result = spatial_updater.process(dry_run=False)
                
                # Verify successful incremental processing
                assert result.success is True
                assert result.records_processed == 15
                assert "incremental" in str(result.details).lower()
                
                # Verify spatial processor was called with target records
                mock_spatial_processor.process_spatial_intersections.assert_called_once_with(
                    "weed-locations", target_records
                )
    
    def test_spatial_processing_error_handling_integration(self, mock_config_loader):
        """Test error handling in spatial processing integration."""
        # Create SpatialFieldUpdater
        spatial_updater = SpatialFieldUpdater(mock_config_loader)
        
        # Mock connector
        mock_connector = Mock()
        spatial_updater.connector = mock_connector
        
        # Mock layer access components
        with patch.object(spatial_updater, '_initialize_layer_access'):
            # Mock change detector
            mock_change_detector = Mock()
            spatial_updater.change_detector = mock_change_detector
            
            # Mock spatial processor that raises an error
            mock_spatial_processor = Mock()
            mock_spatial_processor.process_spatial_intersections.side_effect = Exception("Spatial processing failed")
            spatial_updater.spatial_processor = mock_spatial_processor
            
            # Mock change detection result
            mock_change_decision = ProcessingDecision(
                processing_type=ProcessingType.FULL_REPROCESSING,
                target_records=[],
                change_threshold_met=True,
                full_reprocess_required=True
            )
            mock_change_detector.compare_with_last_processing.return_value = mock_change_decision
            
            # Mock metadata components
            mock_metadata_manager = Mock()
            spatial_updater.metadata_manager = mock_metadata_manager
            
            # Mock configuration validation
            with patch.object(spatial_updater, 'validate_configuration', return_value=True):
                # Execute processing - should handle error gracefully
                result = spatial_updater.process(dry_run=False)
                
                # Verify error handling
                assert result.success is True  # Process method should still succeed overall
                assert result.records_processed == 0  # But no records processed due to error
    
    def test_spatial_processing_performance_monitoring(self, mock_config_loader, mock_layer_manager):
        """Test performance monitoring and metrics collection."""
        layer_manager, mock_weed_layer, mock_region_layer, mock_district_layer = mock_layer_manager
        
        # Create spatial processor
        spatial_processor = SpatialQueryProcessor(layer_manager, mock_config_loader)
        
        # Mock boundary layer retrieval
        with patch.object(spatial_processor, '_get_boundary_layer') as mock_get_boundary:
            mock_get_boundary.side_effect = lambda layer_type: (
                mock_region_layer if layer_type == "region" else mock_district_layer
            )
            
            # Mock update operations
            with patch.object(spatial_processor, '_apply_spatial_assignments') as mock_apply:
                from modules.spatial_field_updater.spatial_query.spatial_query_models import SpatialUpdateResult
                mock_apply.return_value = SpatialUpdateResult(
                    updated_count=10, failed_count=0, update_duration=0.5
                )
                
                # Execute spatial processing
                result = spatial_processor.process_spatial_intersections("weed-locations")
                
                # Verify performance metrics are collected
                metrics = result.spatial_metrics
                assert metrics.total_intersections_calculated > 0
                assert metrics.geometry_validation_time >= 0
                assert metrics.intersection_calculation_time >= 0
                assert metrics.update_operation_time >= 0
                
                # Verify performance summary
                performance_summary = metrics.get_performance_summary()
                assert "total_time" in performance_summary
                assert "success_rate" in performance_summary
                assert "intersection_rate" in performance_summary
                
                # Verify processing efficiency
                efficiency = result.get_processing_efficiency()
                assert "overall_rate" in efficiency
                assert "update_rate" in efficiency
    
    def test_spatial_query_caching_integration(self, mock_config_loader, mock_layer_manager):
        """Test spatial query caching and optimization."""
        layer_manager, mock_weed_layer, mock_region_layer, mock_district_layer = mock_layer_manager
        
        # Create spatial processor
        spatial_processor = SpatialQueryProcessor(layer_manager, mock_config_loader)
        
        # Verify initial cache state
        cache_stats = spatial_processor.get_cache_statistics()
        assert cache_stats["spatial_cache_size"] == 0
        assert cache_stats["assignment_cache_size"] == 0
        
        # Mock boundary layer retrieval to populate cache
        with patch.object(spatial_processor, '_get_boundary_layer') as mock_get_boundary:
            # First call should cache the layers
            mock_get_boundary.side_effect = lambda layer_type: (
                mock_region_layer if layer_type == "region" else mock_district_layer
            )
            
            spatial_processor._get_boundary_layer("region")
            spatial_processor._get_boundary_layer("district")
            
            # Verify cache population
            cache_stats = spatial_processor.get_cache_statistics()
            assert cache_stats["spatial_cache_size"] == 2
            assert "region_layer" in cache_stats["cached_layers"]
            assert "district_layer" in cache_stats["cached_layers"]
            
            # Test cache clearing
            spatial_processor.clear_caches()
            cache_stats = spatial_processor.get_cache_statistics()
            assert cache_stats["spatial_cache_size"] == 0
            assert cache_stats["assignment_cache_size"] == 0 