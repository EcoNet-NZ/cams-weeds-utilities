"""Unit and integration tests for SpatialQueryProcessor.

Tests spatial intersection processing, batch processing, Context7 optimization,
and error handling for the core spatial query processing engine.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock, call
from datetime import datetime
from typing import List

from modules.spatial_field_updater.spatial_query import (
    SpatialQueryProcessor, SpatialProcessingResult, SpatialAssignment, 
    ProcessingMethod, SpatialMetrics, BatchResult
)


class TestSpatialQueryProcessor:
    """Test SpatialQueryProcessor core functionality."""
    
    @pytest.fixture
    def mock_dependencies(self):
        """Create mock dependencies for spatial processor."""
        layer_manager = Mock()
        config_loader = Mock()
        
        # Mock configuration loading
        config_loader.get_config.return_value = {
            "spatial_processing": {
                "batch_size": 100,
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
            }
        }
        
        return layer_manager, config_loader
    
    @pytest.fixture
    def spatial_processor(self, mock_dependencies):
        """Create SpatialQueryProcessor instance with mocked dependencies."""
        layer_manager, config_loader = mock_dependencies
        return SpatialQueryProcessor(layer_manager, config_loader)
    
    def test_spatial_processor_initialization(self, spatial_processor, mock_dependencies):
        """Test SpatialQueryProcessor initialization."""
        layer_manager, config_loader = mock_dependencies
        
        assert spatial_processor.layer_manager == layer_manager
        assert spatial_processor.config_loader == config_loader
        assert isinstance(spatial_processor._processing_config, dict)
        assert spatial_processor._spatial_cache == {}
        assert spatial_processor._assignment_cache == {}
    
    def test_get_boundary_layer_caching(self, spatial_processor, mock_dependencies):
        """Test boundary layer caching functionality."""
        layer_manager, config_loader = mock_dependencies
        
        # Mock layer retrieval
        mock_region_layer = Mock()
        layer_manager.get_layer_by_id.return_value = mock_region_layer
        
        # First call should retrieve and cache the layer
        result1 = spatial_processor._get_boundary_layer("region")
        assert result1 == mock_region_layer
        assert "region_layer" in spatial_processor._spatial_cache
        
        # Second call should use cached layer
        result2 = spatial_processor._get_boundary_layer("region")
        assert result2 == mock_region_layer
        
        # Should only call layer_manager once due to caching
        layer_manager.get_layer_by_id.assert_called_once_with("region-layer-123")
    
    def test_get_boundary_layer_missing_config(self, spatial_processor, mock_dependencies):
        """Test boundary layer retrieval with missing configuration."""
        layer_manager, config_loader = mock_dependencies
        
        # Mock missing layer configuration
        config_loader.get_config.return_value = {"area_layers": {}}
        spatial_processor._processing_config = {}
        
        with pytest.raises(ValueError, match="Configuration not found for missing_layer layer"):
            spatial_processor._get_boundary_layer("missing_layer")
    
    def test_get_features_to_process_incremental(self, spatial_processor):
        """Test getting features for incremental processing."""
        mock_weed_layer = Mock()
        target_records = ["123", "456", "789"]
        
        # Mock query result
        mock_featureset = Mock()
        mock_weed_layer.query.return_value = mock_featureset
        
        result = spatial_processor._get_features_to_process(mock_weed_layer, target_records)
        
        assert result == mock_featureset
        
        # Verify query was called with correct parameters
        mock_weed_layer.query.assert_called_once()
        call_args = mock_weed_layer.query.call_args
        assert "OBJECTID IN (123,456,789)" in call_args[1]["where"]
        assert call_args[1]["out_fields"] == ["OBJECTID", "GlobalID", "RegionCode", "DistrictCode"]
        assert call_args[1]["return_geometry"] is True
    
    def test_get_features_to_process_full(self, spatial_processor):
        """Test getting features for full processing."""
        mock_weed_layer = Mock()
        
        # Mock query result
        mock_featureset = Mock()
        mock_weed_layer.query.return_value = mock_featureset
        
        result = spatial_processor._get_features_to_process(mock_weed_layer, None)
        
        assert result == mock_featureset
        
        # Verify query was called for full processing
        mock_weed_layer.query.assert_called_once()
        call_args = mock_weed_layer.query.call_args
        assert "where" not in call_args[1]  # No WHERE clause for full processing
        assert call_args[1]["out_fields"] == ["OBJECTID", "GlobalID", "RegionCode", "DistrictCode"]
        assert call_args[1]["return_geometry"] is True
    
    def test_batch_features_generator(self, spatial_processor):
        """Test feature batching generator."""
        features = [Mock() for _ in range(257)]  # 257 features
        batch_size = 100
        
        batches = list(spatial_processor._batch_features(features, batch_size))
        
        assert len(batches) == 3  # ceil(257/100) = 3
        assert len(batches[0]) == 100
        assert len(batches[1]) == 100  
        assert len(batches[2]) == 57
    
    def test_validate_geometry_point(self, spatial_processor):
        """Test geometry validation for Point geometries."""
        # Valid point geometry
        valid_point = Mock()
        valid_point.x = -122.4194
        valid_point.y = 37.7749
        assert spatial_processor._validate_geometry(valid_point) is True
        
        # Invalid point geometry (null coordinates)
        invalid_point = Mock()
        invalid_point.x = None
        invalid_point.y = 37.7749
        assert spatial_processor._validate_geometry(invalid_point) is False
        
        # Null geometry
        assert spatial_processor._validate_geometry(None) is False
    
    def test_validate_geometry_dictionary(self, spatial_processor):
        """Test geometry validation for dictionary geometries."""
        # Valid dictionary geometry
        valid_dict = {"x": -122.4194, "y": 37.7749}
        assert spatial_processor._validate_geometry(valid_dict) is True
        
        # Invalid dictionary geometry
        invalid_dict = {"x": None, "y": 37.7749}
        assert spatial_processor._validate_geometry(invalid_dict) is False
        
        # Missing coordinates
        missing_coords = {"z": 100}
        assert spatial_processor._validate_geometry(missing_coords) is False
    
    def test_find_intersecting_boundary_success(self, spatial_processor):
        """Test successful boundary intersection finding."""
        mock_point = Mock()
        mock_boundary_layer = Mock()
        
        # Mock intersection result
        mock_feature = Mock()
        mock_feature.attributes = {"REGC_code": "R001", "OBJECTID": 123}
        mock_intersection_result = Mock()
        mock_intersection_result.features = [mock_feature]
        
        mock_boundary_layer.query.return_value = mock_intersection_result
        
        result = spatial_processor._find_intersecting_boundary(
            mock_point, mock_boundary_layer, "REGC_code"
        )
        
        assert result == "R001"
        
        # Verify query parameters
        mock_boundary_layer.query.assert_called_once()
        call_args = mock_boundary_layer.query.call_args
        assert call_args[1]["geometry"] == mock_point
        assert call_args[1]["spatial_relationship"] == "intersects"
        assert call_args[1]["out_fields"] == ["REGC_code", "OBJECTID"]
        assert call_args[1]["return_geometry"] is False
    
    def test_find_intersecting_boundary_no_intersection(self, spatial_processor):
        """Test boundary intersection with no intersection found."""
        mock_point = Mock()
        mock_boundary_layer = Mock()
        
        # Mock no intersection result
        mock_intersection_result = Mock()
        mock_intersection_result.features = []
        mock_boundary_layer.query.return_value = mock_intersection_result
        
        result = spatial_processor._find_intersecting_boundary(
            mock_point, mock_boundary_layer, "REGC_code"
        )
        
        assert result is None
    
    def test_find_intersecting_boundary_error(self, spatial_processor):
        """Test boundary intersection with query error."""
        mock_point = Mock()
        mock_boundary_layer = Mock()
        
        # Mock query error
        mock_boundary_layer.query.side_effect = Exception("Spatial query failed")
        
        result = spatial_processor._find_intersecting_boundary(
            mock_point, mock_boundary_layer, "REGC_code"
        )
        
        assert result is None
    
    def test_calculate_intersection_quality(self, spatial_processor):
        """Test intersection quality calculation."""
        # Both codes assigned
        assert spatial_processor._calculate_intersection_quality("R001", "D001") == 1.0
        
        # Only region assigned
        assert spatial_processor._calculate_intersection_quality("R001", None) == 0.5
        
        # Only district assigned
        assert spatial_processor._calculate_intersection_quality(None, "D001") == 0.5
        
        # No codes assigned
        assert spatial_processor._calculate_intersection_quality(None, None) == 0.0
    
    def test_create_geometry_cache_key(self, spatial_processor):
        """Test geometry cache key creation."""
        # Point geometry
        point = Mock()
        point.x = -122.4194
        point.y = 37.7749
        key = spatial_processor._create_geometry_cache_key(point)
        assert key == "point_-122.4194_37.7749"
        
        # Dictionary geometry
        dict_geom = {"x": -122.4194, "y": 37.7749}
        key = spatial_processor._create_geometry_cache_key(dict_geom)
        assert key == "point_-122.4194_37.7749"
        
        # Invalid geometry
        invalid_geom = {"z": 100}
        key = spatial_processor._create_geometry_cache_key(invalid_geom)
        assert key is None
    
    def test_process_single_feature_success(self, spatial_processor, mock_dependencies):
        """Test processing a single feature successfully."""
        layer_manager, config_loader = mock_dependencies
        
        # Create mock feature
        mock_feature = Mock()
        mock_feature.attributes = {"OBJECTID": 123, "GlobalID": "guid-123"}
        mock_feature.geometry = Mock()
        mock_feature.geometry.x = -122.4194
        mock_feature.geometry.y = 37.7749
        
        # Create mock boundary layers
        mock_region_layer = Mock()
        mock_district_layer = Mock()
        
        # Mock intersection results
        mock_region_result = Mock()
        mock_region_result.features = [Mock(attributes={"REGC_code": "R001"})]
        mock_region_layer.query.return_value = mock_region_result
        
        mock_district_result = Mock()
        mock_district_result.features = [Mock(attributes={"TALB_code": "D001"})]
        mock_district_layer.query.return_value = mock_district_result
        
        # Create spatial metrics
        spatial_metrics = SpatialMetrics(
            total_intersections_calculated=0,
            successful_assignments=0,
            failed_assignments=0,
            geometry_validation_time=0.0,
            intersection_calculation_time=0.0,
            update_operation_time=0.0,
            cache_hit_rate=0.0
        )
        
        # Process feature
        result = spatial_processor._process_single_feature(
            mock_feature, mock_region_layer, mock_district_layer, spatial_metrics
        )
        
        # Verify assignment
        assert isinstance(result, SpatialAssignment)
        assert result.object_id == "123"
        assert result.region_code == "R001"
        assert result.district_code == "D001"
        assert result.intersection_quality == 1.0
        assert result.processing_method == ProcessingMethod.FULL_INTERSECTION
        assert result.geometry_valid is True
        assert result.is_successful() is True
        
        # Verify metrics were updated
        assert spatial_metrics.total_intersections_calculated == 2
        assert spatial_metrics.successful_assignments == 1
        assert spatial_metrics.failed_assignments == 0
    
    def test_process_single_feature_invalid_geometry(self, spatial_processor, mock_dependencies):
        """Test processing a feature with invalid geometry."""
        # Create mock feature with invalid geometry
        mock_feature = Mock()
        mock_feature.attributes = {"OBJECTID": 123}
        mock_feature.geometry = None  # Invalid geometry
        
        # Create spatial metrics
        spatial_metrics = SpatialMetrics(
            total_intersections_calculated=0,
            successful_assignments=0,
            failed_assignments=0,
            geometry_validation_time=0.0,
            intersection_calculation_time=0.0,
            update_operation_time=0.0,
            cache_hit_rate=0.0
        )
        
        # Process feature
        result = spatial_processor._process_single_feature(
            mock_feature, Mock(), Mock(), spatial_metrics
        )
        
        # Verify assignment for invalid geometry
        assert isinstance(result, SpatialAssignment)
        assert result.object_id == "123"
        assert result.region_code is None
        assert result.district_code is None
        assert result.intersection_quality == 0.0
        assert result.processing_method == ProcessingMethod.GEOMETRY_REPAIR
        assert result.geometry_valid is False
        assert result.is_successful() is False
    
    def test_create_assignment_summary(self, spatial_processor):
        """Test creation of assignment summary statistics."""
        # Create test assignments
        assignments = [
            SpatialAssignment(
                object_id="1", region_code="R001", district_code="D001",
                intersection_quality=1.0, processing_method=ProcessingMethod.FULL_INTERSECTION,
                geometry_valid=True, processing_duration=0.1
            ),
            SpatialAssignment(
                object_id="2", region_code="R002", district_code=None,
                intersection_quality=0.5, processing_method=ProcessingMethod.FULL_INTERSECTION,
                geometry_valid=True, processing_duration=0.1
            ),
            SpatialAssignment(
                object_id="3", region_code=None, district_code="D003",
                intersection_quality=0.5, processing_method=ProcessingMethod.FULL_INTERSECTION,
                geometry_valid=True, processing_duration=0.1
            ),
            SpatialAssignment(
                object_id="4", region_code=None, district_code=None,
                intersection_quality=0.0, processing_method=ProcessingMethod.FALLBACK_ASSIGNMENT,
                geometry_valid=False, processing_duration=0.1
            )
        ]
        
        summary = spatial_processor._create_assignment_summary(assignments)
        
        assert summary["total_assignments"] == 4
        assert summary["both_assigned"] == 1
        assert summary["region_only"] == 1
        assert summary["district_only"] == 1
        assert summary["no_assignment"] == 1
        assert summary["region_assignments"] == 2
        assert summary["district_assignments"] == 2
        assert summary["average_quality"] == 0.5  # (1.0 + 0.5 + 0.5 + 0.0) / 4
        assert summary["processing_methods"]["full_intersection"] == 3
        assert summary["processing_methods"]["fallback_assignment"] == 1
    
    def test_create_assignment_summary_empty(self, spatial_processor):
        """Test assignment summary with empty assignment list."""
        summary = spatial_processor._create_assignment_summary([])
        
        assert summary["total_assignments"] == 0
        assert summary["both_assigned"] == 0
        assert summary["region_only"] == 0
        assert summary["district_only"] == 0
        assert summary["no_assignment"] == 0
        assert summary["region_assignments"] == 0
        assert summary["district_assignments"] == 0
        assert summary["average_quality"] == 0.0
        assert summary["processing_methods"] == {}
    
    def test_clear_caches(self, spatial_processor):
        """Test cache clearing functionality."""
        # Add items to caches
        spatial_processor._spatial_cache["test"] = Mock()
        spatial_processor._assignment_cache["test"] = Mock()
        
        assert len(spatial_processor._spatial_cache) == 1
        assert len(spatial_processor._assignment_cache) == 1
        
        # Clear caches
        spatial_processor.clear_caches()
        
        assert len(spatial_processor._spatial_cache) == 0
        assert len(spatial_processor._assignment_cache) == 0
    
    def test_get_cache_statistics(self, spatial_processor):
        """Test cache statistics retrieval."""
        # Add items to caches
        spatial_processor._spatial_cache["region_layer"] = Mock()
        spatial_processor._spatial_cache["district_layer"] = Mock()
        spatial_processor._assignment_cache["point_1_2"] = Mock()
        
        stats = spatial_processor.get_cache_statistics()
        
        assert stats["spatial_cache_size"] == 2
        assert stats["assignment_cache_size"] == 1
        assert "region_layer" in stats["cached_layers"]
        assert "district_layer" in stats["cached_layers"]


class TestSpatialQueryProcessorIntegration:
    """Integration tests for SpatialQueryProcessor."""
    
    @pytest.fixture
    def mock_full_dependencies(self):
        """Create comprehensive mock dependencies for integration testing."""
        layer_manager = Mock()
        config_loader = Mock()
        
        # Mock complete configuration
        config_loader.get_config.return_value = {
            "spatial_processing": {
                "batch_size": 2,  # Small batch size for testing
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
            }
        }
        
        return layer_manager, config_loader
    
    @pytest.fixture
    def spatial_processor_integration(self, mock_full_dependencies):
        """Create SpatialQueryProcessor for integration testing."""
        layer_manager, config_loader = mock_full_dependencies
        return SpatialQueryProcessor(layer_manager, config_loader)
    
    def test_process_spatial_intersections_full_workflow(self, spatial_processor_integration, mock_full_dependencies):
        """Test complete spatial intersection processing workflow."""
        layer_manager, config_loader = mock_full_dependencies
        
        # Create mock weed features
        mock_features = []
        for i in range(3):
            feature = Mock()
            feature.attributes = {
                "OBJECTID": 100 + i,
                "GlobalID": f"guid-{i}",
                "RegionCode": None,
                "DistrictCode": None
            }
            feature.geometry = Mock()
            feature.geometry.x = -122.4194 + (i * 0.001)
            feature.geometry.y = 37.7749 + (i * 0.001)
            mock_features.append(feature)
        
        # Mock weed layer
        mock_weed_layer = Mock()
        mock_weed_featureset = Mock()
        mock_weed_featureset.features = mock_features
        mock_weed_layer.query.return_value = mock_weed_featureset
        layer_manager.get_layer_by_id.return_value = mock_weed_layer
        
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
        
        # Mock boundary layer retrieval with caching
        def get_boundary_layer_side_effect(layer_type):
            if layer_type == "region":
                return mock_region_layer
            elif layer_type == "district":
                return mock_district_layer
            else:
                raise ValueError(f"Unknown layer type: {layer_type}")
        
        with patch.object(spatial_processor_integration, '_get_boundary_layer', side_effect=get_boundary_layer_side_effect):
            with patch.object(spatial_processor_integration, '_apply_spatial_assignments') as mock_apply:
                # Mock successful update result
                from modules.spatial_field_updater.spatial_query.spatial_query_models import SpatialUpdateResult
                mock_apply.return_value = SpatialUpdateResult(
                    updated_count=3, failed_count=0, update_duration=0.5
                )
                
                # Execute spatial processing
                result = spatial_processor_integration.process_spatial_intersections("test-layer-id")
                
                # Verify comprehensive results
                assert isinstance(result, SpatialProcessingResult)
                assert result.processed_count == 3
                assert result.updated_count == 3
                assert result.failed_count == 0
                assert result.processing_duration > 0
                
                # Verify batch processing occurred
                assert len(result.batch_results) == 2  # 3 features / 2 batch_size = 2 batches
                assert result.batch_results[0].records_processed == 2
                assert result.batch_results[1].records_processed == 1
                
                # Verify spatial metrics
                assert result.spatial_metrics.total_intersections_calculated == 6  # 3 features * 2 intersections each
                assert result.spatial_metrics.successful_assignments == 3
                assert result.spatial_metrics.failed_assignments == 0
                
                # Verify assignment summary
                assert result.region_assignments == 3
                assert result.district_assignments == 3
                breakdown = result.get_assignment_breakdown()
                assert breakdown["both_assigned"] == 3
                
                # Verify processing summary
                summary = result.get_processing_summary()
                assert "3 records" in summary
                assert "100.0%" in summary  # Success rate
                
                # Verify update was called
                mock_apply.assert_called_once()
    
    def test_process_spatial_intersections_empty_features(self, spatial_processor_integration, mock_full_dependencies):
        """Test spatial processing with no features to process."""
        layer_manager, config_loader = mock_full_dependencies
        
        # Mock empty weed layer
        mock_weed_layer = Mock()
        mock_weed_featureset = Mock()
        mock_weed_featureset.features = []  # No features
        mock_weed_layer.query.return_value = mock_weed_featureset
        layer_manager.get_layer_by_id.return_value = mock_weed_layer
        
        # Execute spatial processing
        result = spatial_processor_integration.process_spatial_intersections("test-layer-id")
        
        # Verify empty result
        assert isinstance(result, SpatialProcessingResult)
        assert result.processed_count == 0
        assert result.updated_count == 0
        assert result.failed_count == 0
        assert result.processing_duration > 0
        assert len(result.batch_results) == 0
        assert result.assignment_summary["message"] == "No features to process"
    
    def test_process_spatial_intersections_error_handling(self, spatial_processor_integration, mock_full_dependencies):
        """Test spatial processing error handling."""
        layer_manager, config_loader = mock_full_dependencies
        
        # Mock layer access failure
        layer_manager.get_layer_by_id.return_value = None
        
        # Execute spatial processing - should handle error gracefully
        result = spatial_processor_integration.process_spatial_intersections("invalid-layer-id")
        
        # Verify error result
        assert isinstance(result, SpatialProcessingResult)
        assert result.processed_count == 0
        assert result.updated_count == 0
        assert result.failed_count == 0
        assert result.processing_duration > 0
        assert "error" in result.assignment_summary
        assert "Cannot access weed locations layer" in result.assignment_summary["error"] 