"""Spatial Field Updater Data Models

This package contains Pydantic data models for the spatial field updater module,
providing validation and type safety for weed location data and processing metadata.
"""

from .weed_location import WeedLocation
from .process_metadata import ProcessMetadata

__all__ = ['WeedLocation', 'ProcessMetadata'] 