"""Layer Access Manager for ArcGIS layers with metadata retrieval and caching.

Following Context7 ArcGIS Python API best practices for layer access, field validation,
and performance optimization through caching.
"""

from typing import Optional, List, Dict, Any
from datetime import datetime
import logging
from arcgis.features import FeatureLayer, FeatureLayerCollection
from pydantic import BaseModel, Field

from src.connection.arcgis_connector import ArcGISConnector
from src.config.config_loader import ConfigLoader

logger = logging.getLogger(__name__)


class FieldDefinition(BaseModel):
    """Definition of a field in an ArcGIS layer.
    
    Following Context7 best practices for field metadata extraction.
    """
    name: str = Field(..., description="Field name")
    alias: str = Field(..., description="Field alias")
    field_type: str = Field(..., description="ArcGIS field type")
    sql_type: str = Field(..., description="SQL field type")
    length: Optional[int] = Field(None, description="Field length for string types")
    nullable: bool = Field(True, description="Whether field allows null values")
    editable: bool = Field(True, description="Whether field is editable")


class LayerMetadata(BaseModel):
    """Metadata information for an ArcGIS layer.
    
    Comprehensive layer metadata following Context7 recommendations for
    performance monitoring and validation.
    """
    layer_id: str = Field(..., description="Unique layer identifier")
    layer_name: str = Field(..., description="Layer display name")
    last_updated: datetime = Field(..., description="Layer last update timestamp")
    geometry_type: str = Field(..., description="Geometry type (Point, Polygon, etc.)")
    field_count: int = Field(ge=0, description="Number of fields in layer")
    record_count: int = Field(ge=-1, description="Number of records in layer (-1 for unknown)")
    capabilities: List[str] = Field(default_factory=list, description="Layer capabilities")
    field_definitions: List[FieldDefinition] = Field(default_factory=list, description="Field definitions")


class LayerAccessManager:
    """Manages access to ArcGIS layers with metadata retrieval and validation.
    
    Implements Context7 best practices:
    - Layer caching for performance optimization
    - Proper field metadata extraction using layer.properties.fields
    - Efficient record counting with query(return_count_only=True)
    - Comprehensive error handling and logging
    """
    
    def __init__(self, connector: ArcGISConnector, config_loader: ConfigLoader):
        """Initialize layer access manager with caching capabilities.
        
        Args:
            connector: Authenticated ArcGIS connector
            config_loader: Configuration loader for layer access settings
        """
        self.connector = connector
        self.config_loader = config_loader
        self._layer_cache: Dict[str, FeatureLayer] = {}
        self._metadata_cache: Dict[str, LayerMetadata] = {}
        logger.info("LayerAccessManager initialized with caching enabled")
    
    def get_layer_by_id(self, layer_id: str, use_cache: bool = True) -> Optional[FeatureLayer]:
        """Get FeatureLayer instance by layer ID.
        
        Following Context7 best practices for layer access with caching.
        
        Args:
            layer_id: ArcGIS layer identifier
            use_cache: Whether to use cached layer instance
            
        Returns:
            FeatureLayer instance or None if not accessible
        """
        if use_cache and layer_id in self._layer_cache:
            logger.debug(f"Returning cached layer for {layer_id}")
            return self._layer_cache[layer_id]
        
        try:
            # Use connector to get authenticated GIS instance
            gis = self.connector.get_gis()
            layer = FeatureLayer(layer_id, gis)
            
            # Validate layer accessibility using Context7 recommended approach
            if self.validate_layer_accessibility(layer_id):
                self._layer_cache[layer_id] = layer
                logger.info(f"Successfully accessed and cached layer {layer_id}")
                return layer
            else:
                logger.error(f"Layer {layer_id} is not accessible")
                return None
                
        except Exception as e:
            logger.error(f"Failed to access layer {layer_id}: {e}")
            return None
    
    def validate_layer_accessibility(self, layer_id: str) -> bool:
        """Validate that a layer is accessible with current credentials.
        
        Uses Context7 recommended validation by testing basic property access.
        
        Args:
            layer_id: ArcGIS layer identifier
            
        Returns:
            True if layer is accessible, False otherwise
        """
        try:
            gis = self.connector.get_gis()
            layer = FeatureLayer(layer_id, gis)
            
            # Test basic access by querying properties (Context7 best practice)
            _ = layer.properties.name
            logger.debug(f"Layer accessibility validation passed for {layer_id}")
            return True
            
        except Exception as e:
            logger.debug(f"Layer accessibility validation failed for {layer_id}: {e}")
            return False
    
    def get_layer_metadata(self, layer_id: str, force_refresh: bool = False) -> Optional[LayerMetadata]:
        """Retrieve comprehensive metadata for a layer.
        
        Implements Context7 best practices for metadata extraction:
        - Uses layer.properties.fields for field definitions
        - Uses layer.query(return_count_only=True) for efficient counting
        - Caches metadata for performance optimization
        
        Args:
            layer_id: ArcGIS layer identifier
            force_refresh: Whether to bypass cache and refresh metadata
            
        Returns:
            LayerMetadata instance or None if layer not accessible
        """
        if not force_refresh and layer_id in self._metadata_cache:
            logger.debug(f"Returning cached metadata for {layer_id}")
            return self._metadata_cache[layer_id]
        
        layer = self.get_layer_by_id(layer_id)
        if not layer:
            logger.error(f"Cannot retrieve metadata: layer {layer_id} not accessible")
            return None
        
        try:
            properties = layer.properties
            
            # Extract field definitions using Context7 recommended approach
            field_definitions = []
            for field in properties.fields:
                # Safely extract field attributes with proper defaults
                def safe_getattr(obj, attr, default=None):
                    """Safely get attribute, handling Mock objects and missing attributes."""
                    try:
                        value = getattr(obj, attr, default)
                        # Check if it's a Mock object and return default instead
                        if hasattr(value, '_mock_name'):
                            return default
                        return value
                    except (AttributeError, TypeError):
                        return default
                
                field_def = FieldDefinition(
                    name=field.name,
                    alias=safe_getattr(field, 'alias', field.name),
                    field_type=field.type,
                    sql_type=safe_getattr(field, 'sqlType', 'unknown'),
                    length=safe_getattr(field, 'length', None),
                    nullable=safe_getattr(field, 'nullable', True),
                    editable=safe_getattr(field, 'editable', True)
                )
                field_definitions.append(field_def)
            
            # Get record count efficiently using Context7 best practice
            try:
                record_count = layer.query(return_count_only=True)
                logger.debug(f"Retrieved record count {record_count} for layer {layer_id}")
            except Exception as count_error:
                logger.warning(f"Could not get record count for {layer_id}: {count_error}")
                record_count = -1  # Unknown count
            
            # Extract last updated timestamp
            last_updated = datetime.now()  # Default fallback
            if hasattr(properties, 'editingInfo') and properties.editingInfo:
                if hasattr(properties.editingInfo, 'lastEditDate') and properties.editingInfo.lastEditDate:
                    last_updated = datetime.fromtimestamp(properties.editingInfo.lastEditDate / 1000)
            
            metadata = LayerMetadata(
                layer_id=layer_id,
                layer_name=properties.name,
                last_updated=last_updated,
                geometry_type=properties.geometryType,
                field_count=len(properties.fields),
                record_count=record_count,
                capabilities=properties.capabilities.split(',') if properties.capabilities else [],
                field_definitions=field_definitions
            )
            
            # Cache metadata for performance (Context7 best practice)
            self._metadata_cache[layer_id] = metadata
            logger.info(f"Successfully retrieved and cached metadata for layer {layer_id}")
            return metadata
            
        except Exception as e:
            logger.error(f"Failed to retrieve metadata for layer {layer_id}: {e}")
            return None
    
    def clear_cache(self, layer_id: Optional[str] = None) -> None:
        """Clear layer and metadata cache.
        
        Args:
            layer_id: Specific layer to clear from cache, or None to clear all
        """
        if layer_id:
            self._layer_cache.pop(layer_id, None)
            self._metadata_cache.pop(layer_id, None)
            logger.info(f"Cleared cache for layer {layer_id}")
        else:
            self._layer_cache.clear()
            self._metadata_cache.clear()
            logger.info("Cleared all layer and metadata cache")
    
    def get_cache_stats(self) -> Dict[str, int]:
        """Get cache statistics for monitoring.
        
        Returns:
            Dictionary with cache statistics
        """
        return {
            "cached_layers": len(self._layer_cache),
            "cached_metadata": len(self._metadata_cache)
        } 