"""Tests for Spatial Field Updater data models."""

import pytest
from datetime import datetime, timezone
from pydantic import ValidationError

from modules.spatial_field_updater.models import WeedLocation, ProcessMetadata


class TestWeedLocation:
    """Test cases for WeedLocation Pydantic model."""
    
    def test_valid_weed_location(self):
        """Test creating a valid WeedLocation with all fields."""
        location = WeedLocation(
            object_id=12345,
            global_id="{A1B2C3D4-E5F6-7890-ABCD-EF1234567890}",
            region_code="01",
            district_code="ABC01",
            edit_date=datetime(2024, 1, 15, 10, 30, 0, tzinfo=timezone.utc),
            geometry={
                "x": 1750000.0,
                "y": 5950000.0,
                "spatialReference": {"wkid": 2193}
            }
        )
        
        assert location.object_id == 12345
        assert location.global_id == "{A1B2C3D4-E5F6-7890-ABCD-EF1234567890}"
        assert location.region_code == "01"
        assert location.district_code == "ABC01"
        assert location.edit_date == datetime(2024, 1, 15, 10, 30, 0, tzinfo=timezone.utc)
        assert location.geometry["x"] == 1750000.0
    
    def test_weed_location_minimal_required_fields(self):
        """Test WeedLocation with only required fields."""
        location = WeedLocation(
            object_id=1,
            global_id="12345678-1234-1234-1234-123456789012",
            geometry={"x": 100.0, "y": 200.0}
        )
        
        assert location.object_id == 1
        assert location.region_code is None
        assert location.district_code is None
        assert location.edit_date is None
    
    def test_global_id_validation(self):
        """Test global_id validation with various formats."""
        # Valid UUID with braces
        location1 = WeedLocation(
            object_id=1,
            global_id="{12345678-1234-1234-1234-123456789012}",
            geometry={"x": 1, "y": 2}
        )
        assert location1.global_id == "{12345678-1234-1234-1234-123456789012}"
        
        # Valid UUID without braces
        location2 = WeedLocation(
            object_id=2,
            global_id="12345678-1234-1234-1234-123456789012",
            geometry={"x": 1, "y": 2}
        )
        assert location2.global_id == "12345678-1234-1234-1234-123456789012"
    
    def test_invalid_global_id(self):
        """Test that invalid global_id raises ValidationError."""
        # Test with a string that meets length requirement but fails pattern
        with pytest.raises(ValidationError) as exc_info:
            WeedLocation(
                object_id=1,
                global_id="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",  # 36 chars, UUID format but invalid hex
                geometry={"x": 1, "y": 2}
            )
        
        errors = exc_info.value.errors()
        assert any("pattern" in str(error) or "match" in str(error) for error in errors)
        
        # Test with a string that's too short
        with pytest.raises(ValidationError) as exc_info:
            WeedLocation(
                object_id=1,
                global_id="short",
                geometry={"x": 1, "y": 2}
            )
        
        errors = exc_info.value.errors()
        assert any("at least 36 characters" in str(error) for error in errors)
    
    def test_negative_object_id_invalid(self):
        """Test that negative object_id raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            WeedLocation(
                object_id=-1,
                global_id="12345678-1234-1234-1234-123456789012",
                geometry={"x": 1, "y": 2}
            )
        
        errors = exc_info.value.errors()
        assert any("greater than or equal to 1" in str(error) for error in errors)
    
    def test_region_code_validation(self):
        """Test region code validation."""
        # Valid region code
        location = WeedLocation(
            object_id=1,
            global_id="12345678-1234-1234-1234-123456789012",
            region_code="01",
            geometry={"x": 1, "y": 2}
        )
        assert location.region_code == "01"
        
        # Invalid length (too long - caught by max_length constraint)
        with pytest.raises(ValidationError) as exc_info:
            WeedLocation(
                object_id=1,
                global_id="12345678-1234-1234-1234-123456789012",
                region_code="123",  # Too long
                geometry={"x": 1, "y": 2}
            )
        
        errors = exc_info.value.errors()
        assert any("at most 2 characters" in str(error) for error in errors)
        
        # Invalid characters
        with pytest.raises(ValidationError) as exc_info:
            WeedLocation(
                object_id=1,
                global_id="12345678-1234-1234-1234-123456789012",
                region_code="0!",  # Contains special character
                geometry={"x": 1, "y": 2}
            )
        
        errors = exc_info.value.errors()
        assert any("alphanumeric characters" in str(error) for error in errors)
    
    def test_district_code_validation(self):
        """Test district code validation."""
        # Valid district code
        location = WeedLocation(
            object_id=1,
            global_id="12345678-1234-1234-1234-123456789012",
            district_code="ABC01",
            geometry={"x": 1, "y": 2}
        )
        assert location.district_code == "ABC01"
        
        # Invalid length
        with pytest.raises(ValidationError) as exc_info:
            WeedLocation(
                object_id=1,
                global_id="12345678-1234-1234-1234-123456789012",
                district_code="AB",  # Too short
                geometry={"x": 1, "y": 2}
            )
        
        errors = exc_info.value.errors()
        assert any("exactly 5 characters" in str(error) for error in errors)
    
    def test_geometry_validation(self):
        """Test geometry validation."""
        # Valid point geometry
        location1 = WeedLocation(
            object_id=1,
            global_id="12345678-1234-1234-1234-123456789012",
            geometry={"x": 100.0, "y": 200.0}
        )
        assert location1.geometry["x"] == 100.0
        
        # Valid polygon geometry
        location2 = WeedLocation(
            object_id=2,
            global_id="12345678-1234-1234-1234-123456789012",
            geometry={"rings": [[[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]]]}
        )
        assert "rings" in location2.geometry
        
        # Invalid geometry (not a dict)
        with pytest.raises(ValidationError) as exc_info:
            WeedLocation(
                object_id=1,
                global_id="12345678-1234-1234-1234-123456789012",
                geometry="not a dict"
            )
        
        errors = exc_info.value.errors()
        assert any("dictionary" in str(error) for error in errors)
        
        # Invalid geometry (missing required structure)
        with pytest.raises(ValidationError) as exc_info:
            WeedLocation(
                object_id=1,
                global_id="12345678-1234-1234-1234-123456789012",
                geometry={"invalid": "structure"}
            )
        
        errors = exc_info.value.errors()
        assert any("valid ArcGIS geometry structure" in str(error) for error in errors)
    
    def test_utility_methods(self):
        """Test utility methods on WeedLocation."""
        # Location with both assignments
        location1 = WeedLocation(
            object_id=1,
            global_id="12345678-1234-1234-1234-123456789012",
            region_code="01",
            district_code="ABC01",
            geometry={"x": 1, "y": 2}
        )
        
        assert location1.has_spatial_assignments() is True
        assert location1.needs_spatial_update() is False
        summary1 = location1.get_location_summary()
        assert "Region: 01" in summary1
        assert "District: ABC01" in summary1
        
        # Location missing assignments
        location2 = WeedLocation(
            object_id=2,
            global_id="12345678-1234-1234-1234-123456789012",
            geometry={"x": 1, "y": 2}
        )
        
        assert location2.has_spatial_assignments() is False
        assert location2.needs_spatial_update() is True
        summary2 = location2.get_location_summary()
        assert "Region: Unassigned" in summary2
        assert "District: Unassigned" in summary2


class TestProcessMetadata:
    """Test cases for ProcessMetadata Pydantic model."""
    
    def test_valid_process_metadata(self):
        """Test creating valid ProcessMetadata."""
        now = datetime(2024, 1, 15, 21, 5, 0, tzinfo=timezone.utc)
        layer_time = datetime(2024, 1, 15, 14, 30, 0, tzinfo=timezone.utc)
        
        metadata = ProcessMetadata(
            process_timestamp=now,
            region_layer_id="region-layer-123",
            region_layer_updated=layer_time,
            district_layer_id="district-layer-456",
            district_layer_updated=layer_time,
            process_status="Success",
            records_processed=100,
            processing_duration=45.7,
            metadata_details={"batch_size": 50}
        )
        
        assert metadata.process_timestamp == now
        assert metadata.region_layer_id == "region-layer-123"
        assert metadata.process_status == "Success"
        assert metadata.records_processed == 100
        assert metadata.processing_duration == 45.7
        assert metadata.metadata_details["batch_size"] == 50
    
    def test_process_metadata_minimal_fields(self):
        """Test ProcessMetadata with minimal required fields."""
        now = datetime(2024, 1, 15, 21, 5, 0, tzinfo=timezone.utc)
        
        metadata = ProcessMetadata(
            process_timestamp=now,
            region_layer_id="region-123",
            region_layer_updated=now,
            district_layer_id="district-456",
            district_layer_updated=now,
            process_status="Error",
            records_processed=0
        )
        
        assert metadata.processing_duration is None
        assert metadata.error_message is None
        assert metadata.metadata_details == {}
    
    def test_layer_id_validation(self):
        """Test layer ID validation."""
        now = datetime.now(timezone.utc)
        
        # Valid layer IDs
        for layer_id in ["layer123", "layer-456", "layer_789", "a1b2c3d4"]:
            metadata = ProcessMetadata(
                process_timestamp=now,
                region_layer_id=layer_id,
                region_layer_updated=now,
                district_layer_id=layer_id,
                district_layer_updated=now,
                process_status="Success",
                records_processed=0
            )
            assert metadata.region_layer_id == layer_id
        
        # Invalid layer IDs
        invalid_ids = ["", "   ", "layer@123", "layer!456"]
        for invalid_id in invalid_ids:
            with pytest.raises(ValidationError):
                ProcessMetadata(
                    process_timestamp=now,
                    region_layer_id=invalid_id,
                    region_layer_updated=now,
                    district_layer_id="valid-id",
                    district_layer_updated=now,
                    process_status="Success",
                    records_processed=0
                )
    
    def test_negative_records_processed_invalid(self):
        """Test that negative records_processed raises ValidationError."""
        now = datetime.now(timezone.utc)
        
        with pytest.raises(ValidationError) as exc_info:
            ProcessMetadata(
                process_timestamp=now,
                region_layer_id="region-123",
                region_layer_updated=now,
                district_layer_id="district-456",
                district_layer_updated=now,
                process_status="Success",
                records_processed=-5
            )
        
        errors = exc_info.value.errors()
        assert any("greater than or equal to 0" in str(error) for error in errors)
    
    def test_negative_processing_duration_invalid(self):
        """Test that negative processing_duration raises ValidationError."""
        now = datetime.now(timezone.utc)
        
        with pytest.raises(ValidationError) as exc_info:
            ProcessMetadata(
                process_timestamp=now,
                region_layer_id="region-123",
                region_layer_updated=now,
                district_layer_id="district-456",
                district_layer_updated=now,
                process_status="Success",
                records_processed=10,
                processing_duration=-1.0
            )
        
        errors = exc_info.value.errors()
        assert any("greater than or equal to 0" in str(error) for error in errors)
    
    def test_utility_methods(self):
        """Test utility methods on ProcessMetadata."""
        now = datetime.now(timezone.utc)
        
        # Successful processing
        success_metadata = ProcessMetadata(
            process_timestamp=now,
            region_layer_id="region-123",
            region_layer_updated=now,
            district_layer_id="district-456",
            district_layer_updated=now,
            process_status="Success",
            records_processed=100,
            processing_duration=30.5
        )
        
        assert success_metadata.is_successful() is True
        assert success_metadata.has_errors() is False
        summary = success_metadata.get_processing_summary()
        assert "✓ Success" in summary
        assert "100 records processed" in summary
        assert "(30.5s)" in summary
        
        # Failed processing
        error_metadata = ProcessMetadata(
            process_timestamp=now,
            region_layer_id="region-123",
            region_layer_updated=now,
            district_layer_id="district-456",
            district_layer_updated=now,
            process_status="Error",
            records_processed=25,
            error_message="Connection timeout"
        )
        
        assert error_metadata.is_successful() is False
        assert error_metadata.has_errors() is True
        error_summary = error_metadata.get_processing_summary()
        assert "✗ Error" in error_summary
        assert "Connection timeout" in error_summary
    
    def test_layer_info_method(self):
        """Test get_layer_info method."""
        now = datetime(2024, 1, 15, 21, 5, 0, tzinfo=timezone.utc)
        layer_time = datetime(2024, 1, 15, 14, 30, 0, tzinfo=timezone.utc)
        
        metadata = ProcessMetadata(
            process_timestamp=now,
            region_layer_id="region-layer-123",
            region_layer_updated=layer_time,
            district_layer_id="district-layer-456",
            district_layer_updated=layer_time,
            process_status="Success",
            records_processed=100
        )
        
        layer_info = metadata.get_layer_info()
        assert "region-layer-123" in layer_info["region_layer"]
        assert "district-layer-456" in layer_info["district_layer"]
        assert layer_time.isoformat() in layer_info["region_layer"]
    
    def test_metadata_details_methods(self):
        """Test metadata details manipulation methods."""
        now = datetime.now(timezone.utc)
        
        metadata = ProcessMetadata(
            process_timestamp=now,
            region_layer_id="region-123",
            region_layer_updated=now,
            district_layer_id="district-456",
            district_layer_updated=now,
            process_status="Success",
            records_processed=100
        )
        
        # Test adding details
        metadata.add_detail("batch_size", 50)
        metadata.add_detail("total_batches", 2)
        
        assert metadata.get_detail("batch_size") == 50
        assert metadata.get_detail("total_batches") == 2
        assert metadata.get_detail("nonexistent", "default") == "default"
        
        # Test that details are persisted
        assert metadata.metadata_details["batch_size"] == 50


class TestModelSerialization:
    """Test serialization and deserialization of models."""
    
    def test_weed_location_serialization(self):
        """Test WeedLocation serialization to dict."""
        location = WeedLocation(
            object_id=123,
            global_id="12345678-1234-1234-1234-123456789012",
            region_code="01",
            geometry={"x": 100, "y": 200}
        )
        
        data = location.model_dump()
        assert data["object_id"] == 123
        assert data["global_id"] == "12345678-1234-1234-1234-123456789012"
        assert data["region_code"] == "01"
        assert data["district_code"] is None
        assert data["geometry"]["x"] == 100
    
    def test_process_metadata_serialization(self):
        """Test ProcessMetadata serialization to dict."""
        now = datetime(2024, 1, 15, 21, 5, 0, tzinfo=timezone.utc)
        
        metadata = ProcessMetadata(
            process_timestamp=now,
            region_layer_id="region-123",
            region_layer_updated=now,
            district_layer_id="district-456",
            district_layer_updated=now,
            process_status="Success",
            records_processed=100,
            metadata_details={"test": "value"}
        )
        
        data = metadata.model_dump()
        assert data["process_status"] == "Success"
        assert data["records_processed"] == 100
        assert data["metadata_details"]["test"] == "value" 