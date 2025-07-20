"""Spatial Query Processing Engine for Spatial Field Updater

Core spatial intersection processing between weed locations and area boundaries
(regions/districts) with optimized batch processing and intelligent assignment logic.

This module provides production-ready spatial query processing that replaces
placeholder implementations with actual spatial intersection calculations.
"""

from .spatial_query_models import (
    ProcessingMethod,
    SpatialAssignment, 
    BatchResult,
    SpatialMetrics,
    SpatialProcessingResult,
    SpatialProcessingConfig,
    SpatialUpdateResult
)
from .spatial_query_processor import SpatialQueryProcessor

__all__ = [
    # Core models
    'ProcessingMethod',
    'SpatialAssignment', 
    'BatchResult',
    'SpatialMetrics',
    'SpatialProcessingResult',
    'SpatialProcessingConfig',
    'SpatialUpdateResult',
    # Main processor
    'SpatialQueryProcessor'
]

__version__ = "1.0.0" 