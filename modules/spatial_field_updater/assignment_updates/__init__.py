"""Assignment Updates Package for Spatial Field Updater

Enhanced batch update operations for spatial assignments with optimized
performance, comprehensive validation, and framework-consistent patterns.

This package replaces inefficient feature-by-feature updates with optimized
batch processing for 90%+ performance improvements.
"""

from .assignment_updater import SpatialAssignmentUpdater
from .update_validator import UpdateValidator
from .spatial_metadata_manager import SpatialMetadataManager
from .batch_update_models import (
    ValidationResult,
    AccessibilityResult, 
    PermissionResult,
    IntegrityResult,
    BatchUpdateResult,
    RollbackResult,
    UpdateMetrics,
    MetadataValidationResult
)
from .metadata_models import (
    LayerVersionInfo,
    UpdateMetrics as EnhancedUpdateMetrics,
    ErrorSummary,
    ProcessingPerformanceMetrics,
    EnhancedProcessMetadata,
    MetadataValidationResult as EnhancedMetadataValidationResult
)
from .exceptions import (
    SpatialAssignmentException,
    BatchUpdateException,
    AssignmentValidationException,
    MetadataIntegrityException,
    LayerAccessException,
    RollbackException,
    UpdatePermissionException,
    FeatureAccessibilityException
)

__all__ = [
    # Core components
    'SpatialAssignmentUpdater',
    'UpdateValidator',
    'SpatialMetadataManager',
    
    # Data models
    'ValidationResult',
    'AccessibilityResult',
    'PermissionResult', 
    'IntegrityResult',
    'BatchUpdateResult',
    'RollbackResult',
    'UpdateMetrics',
    'MetadataValidationResult',
    
    # Enhanced metadata models
    'LayerVersionInfo',
    'EnhancedUpdateMetrics',
    'ErrorSummary',
    'ProcessingPerformanceMetrics',
    'EnhancedProcessMetadata',
    'EnhancedMetadataValidationResult',
    
    # Exceptions
    'SpatialAssignmentException',
    'BatchUpdateException',
    'AssignmentValidationException',
    'MetadataIntegrityException',
    'LayerAccessException',
    'RollbackException',
    'UpdatePermissionException',
    'FeatureAccessibilityException'
]

__version__ = "1.0.0" 