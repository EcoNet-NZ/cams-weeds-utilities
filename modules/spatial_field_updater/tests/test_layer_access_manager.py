"""Tests for LayerAccessManager.

Comprehensive test suite for layer access management following Context7 best practices
for testing ArcGIS layer access, metadata retrieval, and caching functionality.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime

from modules.spatial_field_updater.layer_access.layer_access_manager import (
    LayerAccessManager, LayerMetadata, FieldDefinition
)


class TestFieldDefinition:
    """Test suite for FieldDefinition model."""
    
    def test_field_definition_creation(self):
        """Test FieldDefinition model creation with valid data."""
        field_def = FieldDefinition(
            name="OBJECTID",
            alias="Object ID",
            field_type="esriFieldTypeOID",
            sql_type="sqlTypeInteger",
            length=None,
            nullable=False,
            editable=False
        )
        
        assert field_def.name == "OBJECTID"
        assert field_def.alias == "Object ID"
        assert field_def.field_type == "esriFieldTypeOID"
        assert field_def.sql_type == "sqlTypeInteger"
        assert field_def.length is None
        assert field_def.nullable is False
        assert field_def.editable is False
    
    def test_field_definition_defaults(self):
        """Test FieldDefinition with default values."""
        field_def = FieldDefinition(
            name="TestField",
            alias="Test Field",
            field_type="esriFieldTypeString",
            sql_type="sqlTypeVarchar"
        )
        
        assert field_def.nullable is True  # Default
        assert field_def.editable is True  # Default
        assert field_def.length is None    # Default


class TestLayerMetadata:
    """Test suite for LayerMetadata model."""
    
    def test_layer_metadata_creation(self):
        """Test LayerMetadata model creation with valid data."""
        field_def = FieldDefinition(
            name="OBJECTID",
            alias="Object ID",
            field_type="esriFieldTypeOID",
            sql_type="sqlTypeInteger"
        )
        
        metadata = LayerMetadata(
            layer_id="test-layer-123",
            layer_name="Test Layer",
            last_updated=datetime.now(),
            geometry_type="esriGeometryPoint",
            field_count=5,
            record_count=1000,
            capabilities=["Query", "Create", "Update"],
            field_definitions=[field_def]
        )
        
        assert metadata.layer_id == "test-layer-123"
        assert metadata.layer_name == "Test Layer"
        assert metadata.geometry_type == "esriGeometryPoint"
        assert metadata.field_count == 5
        assert metadata.record_count == 1000
        assert len(metadata.capabilities) == 3
        assert len(metadata.field_definitions) == 1


class TestLayerAccessManager:
    """Test suite for LayerAccessManager."""
    
    @pytest.fixture
    def mock_connector(self):
        """Create mock ArcGIS connector."""
        connector = Mock()
        mock_gis = Mock()
        connector.get_gis.return_value = mock_gis
        return connector
    
    @pytest.fixture
    def mock_config_loader(self):
        """Create mock config loader."""
        return Mock()
    
    @pytest.fixture
    def layer_manager(self, mock_connector, mock_config_loader):
        """Create LayerAccessManager instance."""
        return LayerAccessManager(mock_connector, mock_config_loader)
    
    @pytest.fixture
    def mock_arcgis_layer(self):
        """Create mock ArcGIS layer with realistic properties."""
        mock_layer = Mock()
        mock_layer.properties.name = "Test Layer"
        mock_layer.properties.geometryType = "esriGeometryPoint"
        mock_layer.properties.capabilities = "Query,Create,Update"
        
        # Mock field with proper attributes (not Mock objects)
        mock_field = Mock()
        mock_field.name = "OBJECTID"
        mock_field.alias = "Object ID"
        mock_field.type = "esriFieldTypeOID"
        # Use getattr to return proper values instead of Mock objects
        def mock_getattr(name, default=None):
            if name == 'sqlType':
                return 'sqlTypeInteger'
            elif name == 'length':
                return None
            elif name == 'nullable':
                return False
            elif name == 'editable':
                return False
            return default
        
        # Configure the mock field's getattr behavior
        mock_field.configure_mock(**{
            'sqlType': 'sqlTypeInteger',
            'length': None,
            'nullable': False,
            'editable': False
        })
        
        mock_layer.properties.fields = [mock_field]
        mock_layer.query.return_value = 100  # Mock record count
        
        # Mock editing info
        mock_editing_info = Mock()
        mock_editing_info.lastEditDate = int(datetime.now().timestamp() * 1000)
        mock_layer.properties.editingInfo = mock_editing_info
        
        return mock_layer
    
    def test_initialization(self, layer_manager, mock_connector, mock_config_loader):
        """Test LayerAccessManager initialization."""
        assert layer_manager.connector == mock_connector
        assert layer_manager.config_loader == mock_config_loader
        assert len(layer_manager._layer_cache) == 0
        assert len(layer_manager._metadata_cache) == 0
    
    def test_validate_layer_accessibility_success(self, layer_manager, mock_arcgis_layer):
        """Test successful layer accessibility validation."""
        layer_id = "test-layer-123"
        
        with patch('modules.spatial_field_updater.layer_access.layer_access_manager.FeatureLayer') as mock_feature_layer:
            mock_feature_layer.return_value = mock_arcgis_layer
            
            result = layer_manager.validate_layer_accessibility(layer_id)
            
            assert result is True
            mock_feature_layer.assert_called_once()
    
    def test_validate_layer_accessibility_failure(self, layer_manager):
        """Test layer accessibility validation failure."""
        layer_id = "invalid-layer"
        
        with patch('modules.spatial_field_updater.layer_access.layer_access_manager.FeatureLayer') as mock_feature_layer:
            mock_feature_layer.side_effect = Exception("Layer not found")
            
            result = layer_manager.validate_layer_accessibility(layer_id)
            
            assert result is False
    
    def test_get_layer_by_id_success(self, layer_manager, mock_arcgis_layer):
        """Test successful layer retrieval by ID."""
        layer_id = "test-layer-123"
        
        with patch('modules.spatial_field_updater.layer_access.layer_access_manager.FeatureLayer') as mock_feature_layer:
            mock_feature_layer.return_value = mock_arcgis_layer
            
            # Mock successful validation
            with patch.object(layer_manager, 'validate_layer_accessibility', return_value=True):
                result = layer_manager.get_layer_by_id(layer_id)
                
                assert result == mock_arcgis_layer
                assert layer_id in layer_manager._layer_cache
    
    def test_get_layer_by_id_cached(self, layer_manager, mock_arcgis_layer):
        """Test layer retrieval from cache."""
        layer_id = "test-layer-123"
        layer_manager._layer_cache[layer_id] = mock_arcgis_layer
        
        result = layer_manager.get_layer_by_id(layer_id)
        
        assert result == mock_arcgis_layer
    
    def test_get_layer_by_id_validation_failure(self, layer_manager, mock_arcgis_layer):
        """Test layer retrieval with validation failure."""
        layer_id = "test-layer-123"
        
        with patch('modules.spatial_field_updater.layer_access.layer_access_manager.FeatureLayer') as mock_feature_layer:
            mock_feature_layer.return_value = mock_arcgis_layer
            
            # Mock failed validation
            with patch.object(layer_manager, 'validate_layer_accessibility', return_value=False):
                result = layer_manager.get_layer_by_id(layer_id)
                
                assert result is None
                assert layer_id not in layer_manager._layer_cache
    
    def test_get_layer_metadata_success(self, layer_manager, mock_arcgis_layer):
        """Test successful layer metadata retrieval."""
        layer_id = "test-layer-123"
        
        with patch.object(layer_manager, 'get_layer_by_id', return_value=mock_arcgis_layer):
            result = layer_manager.get_layer_metadata(layer_id)
            
            assert result is not None
            assert isinstance(result, LayerMetadata)
            assert result.layer_id == layer_id
            assert result.layer_name == "Test Layer"
            assert result.geometry_type == "esriGeometryPoint"
            assert result.record_count == 100
            assert len(result.field_definitions) == 1
            assert layer_id in layer_manager._metadata_cache
    
    def test_get_layer_metadata_cached(self, layer_manager):
        """Test layer metadata retrieval from cache."""
        layer_id = "test-layer-123"
        cached_metadata = LayerMetadata(
            layer_id=layer_id,
            layer_name="Cached Layer",
            last_updated=datetime.now(),
            geometry_type="esriGeometryPolygon",
            field_count=3,
            record_count=500,
            capabilities=[],
            field_definitions=[]
        )
        layer_manager._metadata_cache[layer_id] = cached_metadata
        
        result = layer_manager.get_layer_metadata(layer_id)
        
        assert result == cached_metadata
    
    def test_get_layer_metadata_layer_not_accessible(self, layer_manager):
        """Test metadata retrieval when layer is not accessible."""
        layer_id = "invalid-layer"
        
        with patch.object(layer_manager, 'get_layer_by_id', return_value=None):
            result = layer_manager.get_layer_metadata(layer_id)
            
            assert result is None
    
    def test_get_layer_metadata_record_count_failure(self, layer_manager, mock_arcgis_layer):
        """Test metadata retrieval when record count query fails."""
        layer_id = "test-layer-123"
        mock_arcgis_layer.query.side_effect = Exception("Query failed")
        
        with patch.object(layer_manager, 'get_layer_by_id', return_value=mock_arcgis_layer):
            result = layer_manager.get_layer_metadata(layer_id)
            
            assert result is not None
            assert result.record_count == -1  # Unknown count
    
    def test_clear_cache_specific_layer(self, layer_manager, mock_arcgis_layer):
        """Test clearing cache for specific layer."""
        layer_id = "test-layer-123"
        layer_manager._layer_cache[layer_id] = mock_arcgis_layer
        layer_manager._metadata_cache[layer_id] = Mock()
        
        layer_manager.clear_cache(layer_id)
        
        assert layer_id not in layer_manager._layer_cache
        assert layer_id not in layer_manager._metadata_cache
    
    def test_clear_cache_all(self, layer_manager, mock_arcgis_layer):
        """Test clearing all cache."""
        layer_manager._layer_cache["layer1"] = mock_arcgis_layer
        layer_manager._layer_cache["layer2"] = mock_arcgis_layer
        layer_manager._metadata_cache["layer1"] = Mock()
        layer_manager._metadata_cache["layer2"] = Mock()
        
        layer_manager.clear_cache()
        
        assert len(layer_manager._layer_cache) == 0
        assert len(layer_manager._metadata_cache) == 0
    
    def test_get_cache_stats(self, layer_manager, mock_arcgis_layer):
        """Test cache statistics retrieval."""
        layer_manager._layer_cache["layer1"] = mock_arcgis_layer
        layer_manager._layer_cache["layer2"] = mock_arcgis_layer
        layer_manager._metadata_cache["layer1"] = Mock()
        
        stats = layer_manager.get_cache_stats()
        
        assert stats["cached_layers"] == 2
        assert stats["cached_metadata"] == 1
    
    def test_get_layer_metadata_force_refresh(self, layer_manager, mock_arcgis_layer):
        """Test metadata retrieval with forced refresh."""
        layer_id = "test-layer-123"
        
        # Add to cache first
        cached_metadata = Mock()
        layer_manager._metadata_cache[layer_id] = cached_metadata
        
        with patch.object(layer_manager, 'get_layer_by_id', return_value=mock_arcgis_layer):
            result = layer_manager.get_layer_metadata(layer_id, force_refresh=True)
            
            # Should retrieve new metadata, not cached
            assert result is not None
            assert result != cached_metadata
            assert isinstance(result, LayerMetadata)
    
    def test_field_definition_extraction(self, layer_manager, mock_arcgis_layer):
        """Test proper field definition extraction from layer properties."""
        layer_id = "test-layer-123"
        
        # Add additional mock field with different properties
        mock_field2 = Mock()
        mock_field2.name = "Name"
        mock_field2.alias = "Feature Name"
        mock_field2.type = "esriFieldTypeString"
        mock_field2.sqlType = "sqlTypeVarchar"
        mock_field2.length = 255
        mock_field2.nullable = True
        mock_field2.editable = True
        
        mock_arcgis_layer.properties.fields = [
            mock_arcgis_layer.properties.fields[0],  # OBJECTID field
            mock_field2
        ]
        
        with patch.object(layer_manager, 'get_layer_by_id', return_value=mock_arcgis_layer):
            result = layer_manager.get_layer_metadata(layer_id)
            
            assert result is not None
            assert len(result.field_definitions) == 2
            
            # Check first field (OBJECTID)
            objectid_field = result.field_definitions[0]
            assert objectid_field.name == "OBJECTID"
            assert objectid_field.field_type == "esriFieldTypeOID"
            assert objectid_field.nullable is False
            
            # Check second field (Name)
            name_field = result.field_definitions[1]
            assert name_field.name == "Name"
            assert name_field.field_type == "esriFieldTypeString"
            assert name_field.length == 255
            assert name_field.nullable is True 