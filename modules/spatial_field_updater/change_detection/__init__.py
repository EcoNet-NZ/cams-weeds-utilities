"""Change Detection System for Spatial Field Updater

This module provides intelligent detection of changes requiring spatial reprocessing
within the spatial field updater module, enabling incremental processing and 
optimization based on EditDate_1 field monitoring.

Components:
- ProcessingType: Enum for processing type recommendations
- ChangeMetrics: Detailed metrics from change detection analysis
- ChangeDetectionResult: Comprehensive result of change detection analysis
- ProcessingDecision: Decision result for processing type and target records
- SpatialChangeDetector: Core change detection engine

Usage:
    from modules.spatial_field_updater.change_detection import (
        SpatialChangeDetector, ProcessingType, ChangeDetectionResult
    )
    
    # Initialize detector
    detector = SpatialChangeDetector(layer_manager, metadata_manager, config_loader)
    
    # Detect changes since last processing
    result = detector.detect_changes("layer-id-123")
    
    # Get processing decision
    decision = detector.compare_with_last_processing("layer-id-123")
"""

from .change_detection_models import (
    ProcessingType, ChangeMetrics, ChangeDetectionResult, ProcessingDecision
)
from .spatial_change_detector import SpatialChangeDetector

__all__ = [
    'ProcessingType', 'ChangeMetrics', 'ChangeDetectionResult', 'ProcessingDecision',
    'SpatialChangeDetector'
]

__version__ = "1.0.0" 