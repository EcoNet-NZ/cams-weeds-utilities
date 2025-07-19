"""Layer Access Management for Spatial Field Updater

This package provides comprehensive layer access and metadata management
capabilities for the Spatial Field Updater module.
"""

from .layer_access_manager import LayerAccessManager, LayerMetadata, FieldDefinition
from .field_validator import FieldValidator, FieldValidationResult
from .metadata_table_manager import MetadataTableManager

__all__ = [
    'LayerAccessManager', 'LayerMetadata', 'FieldDefinition',
    'FieldValidator', 'FieldValidationResult',
    'MetadataTableManager'
] 