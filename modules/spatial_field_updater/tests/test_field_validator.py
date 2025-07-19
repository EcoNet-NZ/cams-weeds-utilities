"""Tests for FieldValidator.

Comprehensive test suite for field schema validation following Context7 best practices
for testing ArcGIS field type compatibility and validation logic.
"""

import pytest
from unittest.mock import Mock, patch, mock_open
import json

from modules.spatial_field_updater.layer_access.field_validator import (
    FieldValidator, FieldValidationResult
)
from modules.spatial_field_updater.layer_access.layer_access_manager import (
    LayerMetadata, FieldDefinition
)


class TestFieldValidationResult:
    """Test suite for FieldValidationResult model."""
    
    def test_field_validation_result_creation(self):
        """Test FieldValidationResult model creation."""
        result = FieldValidationResult(
            layer_id="test-layer-123",
            validation_passed=False,
            missing_fields=["RegionCode"],
            unexpected_fields=["ExtraField"],
            type_mismatches=["DistrictCode: expected string, got integer"],
            validation_errors=["Schema validation failed"]
        )
        
        assert result.layer_id == "test-layer-123"
        assert result.validation_passed is False
        assert len(result.missing_fields) == 1
        assert len(result.unexpected_fields) == 1
        assert len(result.type_mismatches) == 1
        assert len(result.validation_errors) == 1
    
    def test_field_validation_result_defaults(self):
        """Test FieldValidationResult with default values."""
        result = FieldValidationResult(
            layer_id="test-layer",
            validation_passed=True
        )
        
        assert len(result.missing_fields) == 0
        assert len(result.unexpected_fields) == 0
        assert len(result.type_mismatches) == 0
        assert len(result.validation_errors) == 0


class TestFieldValidator:
    """Test suite for FieldValidator."""
    
    @pytest.fixture
    def mock_layer_manager(self):
        """Create mock LayerAccessManager."""
        return Mock()
    
    @pytest.fixture
    def mock_config_loader(self):
        """Create mock ConfigLoader."""
        return Mock()
    
    @pytest.fixture
    def field_validator(self, mock_layer_manager, mock_config_loader):
        """Create FieldValidator instance."""
        return FieldValidator(mock_layer_manager, mock_config_loader)
    
    @pytest.fixture
    def sample_layer_metadata(self):
        """Create sample layer metadata for testing."""
        field_definitions = [
            FieldDefinition(
                name="OBJECTID",
                alias="Object ID",
                field_type="esriFieldTypeOID",
                sql_type="sqlTypeInteger"
            ),
            FieldDefinition(
                name="GlobalID",
                alias="Global ID",
                field_type="esriFieldTypeGlobalID",
                sql_type="sqlTypeString"
            ),
            FieldDefinition(
                name="RegionCode",
                alias="Region Code",
                field_type="esriFieldTypeString",
                sql_type="sqlTypeVarchar"
            ),
            FieldDefinition(
                name="EditDate_1",
                alias="Edit Date",
                field_type="esriFieldTypeDate",
                sql_type="sqlTypeDateTime"
            ),
            FieldDefinition(
                name="Shape",
                alias="Shape",
                field_type="esriFieldTypeGeometry",
                sql_type="sqlTypeGeometry"
            )
        ]
        
        from datetime import datetime
        return LayerMetadata(
            layer_id="test-layer-123",
            layer_name="Test Layer",
            last_updated=datetime.now(),
            geometry_type="esriGeometryPoint",
            field_count=len(field_definitions),
            record_count=1000,
            capabilities=["Query"],
            field_definitions=field_definitions
        )
    
    def test_initialization(self, field_validator, mock_layer_manager, mock_config_loader):
        """Test FieldValidator initialization."""
        assert field_validator.layer_manager == mock_layer_manager
        assert field_validator.config_loader == mock_config_loader
    
    def test_types_compatible_string_types(self, field_validator):
        """Test string type compatibility using Context7 mappings."""
        # Test compatible string types
        assert field_validator._types_compatible("string", "esriFieldTypeString") is True
        assert field_validator._types_compatible("string", "esriFieldTypeGUID") is True
        assert field_validator._types_compatible("string", "esriFieldTypeGlobalID") is True
        
        # Test incompatible types
        assert field_validator._types_compatible("string", "esriFieldTypeInteger") is False
        assert field_validator._types_compatible("string", "esriFieldTypeDate") is False
    
    def test_types_compatible_integer_types(self, field_validator):
        """Test integer type compatibility using Context7 mappings."""
        # Test compatible integer types
        assert field_validator._types_compatible("integer", "esriFieldTypeInteger") is True
        assert field_validator._types_compatible("integer", "esriFieldTypeSmallInteger") is True
        assert field_validator._types_compatible("integer", "esriFieldTypeOID") is True
        assert field_validator._types_compatible("integer", "esriFieldTypeBigInteger") is True
        
        # Test incompatible types
        assert field_validator._types_compatible("integer", "esriFieldTypeString") is False
        assert field_validator._types_compatible("integer", "esriFieldTypeDate") is False
    
    def test_types_compatible_date_types(self, field_validator):
        """Test date type compatibility using Context7 mappings."""
        # Test compatible date types
        assert field_validator._types_compatible("date", "esriFieldTypeDate") is True
        assert field_validator._types_compatible("date", "esriFieldTypeDateOnly") is True
        assert field_validator._types_compatible("date", "esriFieldTypeTimeOnly") is True
        
        # Test incompatible types
        assert field_validator._types_compatible("date", "esriFieldTypeString") is False
        assert field_validator._types_compatible("date", "esriFieldTypeInteger") is False
    
    def test_types_compatible_geometry_types(self, field_validator):
        """Test geometry type compatibility."""
        assert field_validator._types_compatible("geometry", "esriFieldTypeGeometry") is True
        assert field_validator._types_compatible("geometry", "esriFieldTypeString") is False
    
    def test_types_compatible_double_types(self, field_validator):
        """Test double type compatibility."""
        assert field_validator._types_compatible("double", "esriFieldTypeDouble") is True
        assert field_validator._types_compatible("double", "esriFieldTypeSingle") is True
        assert field_validator._types_compatible("double", "esriFieldTypeInteger") is False
    
    def test_types_compatible_case_insensitive(self, field_validator):
        """Test case-insensitive type compatibility."""
        assert field_validator._types_compatible("STRING", "esriFieldTypeString") is True
        assert field_validator._types_compatible("Integer", "esriFieldTypeInteger") is True
        assert field_validator._types_compatible("DATE", "esriFieldTypeDate") is True
    
    def test_types_compatible_direct_match(self, field_validator):
        """Test direct type matching."""
        assert field_validator._types_compatible("esriFieldTypeString", "esriFieldTypeString") is True
        assert field_validator._types_compatible("CustomType", "CustomType") is True
        assert field_validator._types_compatible("CustomType", "DifferentType") is False
    
    def test_validate_layer_schema_success(self, field_validator, sample_layer_metadata):
        """Test successful layer schema validation."""
        layer_id = "test-layer-123"
        expected_fields = {
            "OBJECTID": "integer",
            "GlobalID": "string",
            "RegionCode": "string",
            "EditDate_1": "date",
            "Shape": "geometry"
        }
        
        field_validator.layer_manager.get_layer_metadata.return_value = sample_layer_metadata
        
        result = field_validator.validate_layer_schema(layer_id, expected_fields)
        
        assert result.validation_passed is True
        assert len(result.missing_fields) == 0
        assert len(result.type_mismatches) == 0
        assert len(result.validation_errors) == 0
    
    def test_validate_layer_schema_missing_fields(self, field_validator, sample_layer_metadata):
        """Test layer schema validation with missing fields."""
        layer_id = "test-layer-123"
        expected_fields = {
            "OBJECTID": "integer",
            "GlobalID": "string",
            "RegionCode": "string",
            "MissingField": "string",  # This field doesn't exist
            "Shape": "geometry"
        }
        
        field_validator.layer_manager.get_layer_metadata.return_value = sample_layer_metadata
        
        result = field_validator.validate_layer_schema(layer_id, expected_fields)
        
        assert result.validation_passed is False
        assert "missingfield" in result.missing_fields  # Case-insensitive
        assert len(result.validation_errors) > 0
    
    def test_validate_layer_schema_type_mismatches(self, field_validator, sample_layer_metadata):
        """Test layer schema validation with type mismatches."""
        layer_id = "test-layer-123"
        expected_fields = {
            "OBJECTID": "string",     # Wrong type - should be integer
            "GlobalID": "string",
            "RegionCode": "integer",  # Wrong type - should be string
            "Shape": "geometry"
        }
        
        field_validator.layer_manager.get_layer_metadata.return_value = sample_layer_metadata
        
        result = field_validator.validate_layer_schema(layer_id, expected_fields)
        
        assert result.validation_passed is False
        assert len(result.type_mismatches) >= 2  # OBJECTID and RegionCode
        assert any("objectid" in mismatch.lower() for mismatch in result.type_mismatches)
        assert any("regioncode" in mismatch.lower() for mismatch in result.type_mismatches)
    
    def test_validate_layer_schema_metadata_not_available(self, field_validator):
        """Test layer schema validation when metadata is not available."""
        layer_id = "invalid-layer"
        expected_fields = {"OBJECTID": "integer"}
        
        field_validator.layer_manager.get_layer_metadata.return_value = None
        
        result = field_validator.validate_layer_schema(layer_id, expected_fields)
        
        assert result.validation_passed is False
        assert len(result.validation_errors) > 0
        assert "could not retrieve metadata" in result.validation_errors[0].lower()
    
    def test_validate_layer_schema_case_insensitive(self, field_validator, sample_layer_metadata):
        """Test that field validation is case-insensitive."""
        layer_id = "test-layer-123"
        expected_fields = {
            "objectid": "integer",      # lowercase
            "GLOBALID": "string",       # uppercase
            "RegionCode": "string",     # mixed case
        }
        
        field_validator.layer_manager.get_layer_metadata.return_value = sample_layer_metadata
        
        result = field_validator.validate_layer_schema(layer_id, expected_fields)
        
        assert result.validation_passed is True
    
    def test_validate_layer_schema_unexpected_fields_filtered(self, field_validator, sample_layer_metadata):
        """Test that system fields are not reported as unexpected."""
        layer_id = "test-layer-123"
        expected_fields = {
            "RegionCode": "string",  # Only expect one field
        }
        
        field_validator.layer_manager.get_layer_metadata.return_value = sample_layer_metadata
        
        result = field_validator.validate_layer_schema(layer_id, expected_fields)
        
        # Should pass validation despite having additional system fields
        # System fields like OBJECTID, GlobalID, Shape should be filtered out
        # Only non-system unexpected fields should be reported
        assert "objectid" not in [f.lower() for f in result.unexpected_fields]
        assert "globalid" not in [f.lower() for f in result.unexpected_fields]
        assert "shape" not in [f.lower() for f in result.unexpected_fields]
    
    def test_get_field_type_mappings(self, field_validator):
        """Test field type mappings retrieval."""
        mappings = field_validator.get_field_type_mappings()
        
        assert "string" in mappings
        assert "integer" in mappings
        assert "date" in mappings
        assert "geometry" in mappings
        assert "double" in mappings
        
        # Check specific mappings
        assert "esriFieldTypeString" in mappings["string"]
        assert "esriFieldTypeOID" in mappings["integer"]
        assert "esriFieldTypeDate" in mappings["date"]
        assert "esriFieldTypeGeometry" in mappings["geometry"]
    
    def test_load_module_config_success(self, field_validator):
        """Test successful module configuration loading."""
        mock_config = {
            "area_layers": {
                "region": {"layer_id": "region-123"}
            },
            "validation": {
                "field_types": {"OBJECTID": "integer"}
            }
        }
        
        mock_file_content = json.dumps(mock_config)
        
        with patch("pathlib.Path.exists", return_value=True):
            with patch("builtins.open", mock_open(read_data=mock_file_content)):
                config = field_validator._load_module_config()
                
                assert config == mock_config
    
    def test_load_module_config_file_not_found(self, field_validator):
        """Test module configuration loading when file doesn't exist."""
        with patch("pathlib.Path.exists", return_value=False):
            config = field_validator._load_module_config()
            
            assert config == {}
    
    def test_load_module_config_json_error(self, field_validator):
        """Test module configuration loading with JSON error."""
        invalid_json = "{ invalid json }"
        
        with patch("pathlib.Path.exists", return_value=True):
            with patch("builtins.open", mock_open(read_data=invalid_json)):
                config = field_validator._load_module_config()
                
                assert config == {}
    
    def test_validate_all_configured_layers_success(self, field_validator):
        """Test validation of all configured layers."""
        # Mock module configuration
        mock_config = {
            "validation": {
                "field_types": {
                    "OBJECTID": "integer",
                    "GlobalID": "string"
                }
            },
            "area_layers": {
                "region": {
                    "layer_id": "region-123",
                    "expected_fields": {
                        "REGC_code": "string",
                        "OBJECTID": "integer"
                    }
                }
            }
        }
        
        # Mock environment configuration
        mock_env_config = {
            "current_environment": "development",
            "development": {
                "weed_locations_layer_id": "weed-123"
            }
        }
        
        # Mock validation results
        mock_weed_result = FieldValidationResult(
            layer_id="weed-123",
            validation_passed=True
        )
        mock_region_result = FieldValidationResult(
            layer_id="region-123",
            validation_passed=True
        )
        
        field_validator.config_loader.load_environment_config.return_value = mock_env_config
        
        with patch.object(field_validator, '_load_module_config', return_value=mock_config):
            with patch.object(field_validator, 'validate_layer_schema') as mock_validate:
                mock_validate.side_effect = [mock_weed_result, mock_region_result]
                
                results = field_validator.validate_all_configured_layers()
                
                assert len(results) == 2
                assert "weed_locations" in results
                assert "region" in results
                assert results["weed_locations"].validation_passed is True
                assert results["region"].validation_passed is True
    
    def test_validate_all_configured_layers_no_weed_layer(self, field_validator):
        """Test validation when no weed locations layer is configured."""
        mock_config = {
            "validation": {"field_types": {}},
            "area_layers": {}
        }
        
        mock_env_config = {
            "current_environment": "development",
            "development": {}  # No weed_locations_layer_id
        }
        
        field_validator.config_loader.load_environment_config.return_value = mock_env_config
        
        with patch.object(field_validator, '_load_module_config', return_value=mock_config):
            results = field_validator.validate_all_configured_layers()
            
            assert len(results) == 0
    
    def test_validate_all_configured_layers_exception_handling(self, field_validator):
        """Test exception handling in validate_all_configured_layers."""
        field_validator.config_loader.load_environment_config.side_effect = Exception("Config error")
        
        results = field_validator.validate_all_configured_layers()
        
        assert results == {} 