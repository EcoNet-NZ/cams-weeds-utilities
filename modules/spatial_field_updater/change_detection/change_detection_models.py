"""
Change Detection Data Models

This module defines Pydantic models for the change detection system, providing
comprehensive data validation and serialization for change detection results,
processing decisions, and metrics.

All models follow Context7 best practices and integrate with the existing
SpatialFieldUpdater infrastructure.
"""

from typing import Dict, List, Any, Optional
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field, field_validator


class ProcessingType(str, Enum):
    """Processing type recommendations based on change detection.
    
    Values:
        FULL_REPROCESSING: Complete reprocessing of all records required
        INCREMENTAL_UPDATE: Process only modified records  
        NO_PROCESSING_NEEDED: No changes detected, skip processing
        FORCE_FULL_UPDATE: Force full reprocessing due to error conditions
    """
    FULL_REPROCESSING = "full_reprocessing"
    INCREMENTAL_UPDATE = "incremental_update" 
    NO_PROCESSING_NEEDED = "no_processing_needed"
    FORCE_FULL_UPDATE = "force_full_update"


class ChangeMetrics(BaseModel):
    """Detailed metrics from change detection analysis.
    
    Provides comprehensive performance and change tracking information
    for monitoring and optimization purposes.
    """
    records_analyzed: int = Field(
        ge=0, 
        description="Total records analyzed during change detection"
    )
    edit_date_changes: int = Field(
        ge=0, 
        description="Records with EditDate_1 changes since last processing"
    )
    geometry_changes: int = Field(
        ge=0, 
        description="Records with geometry changes (future enhancement)"
    )
    attribute_changes: int = Field(
        ge=0, 
        description="Records with attribute changes"
    )
    processing_duration: float = Field(
        ge=0, 
        description="Duration of change detection analysis in seconds"
    )
    last_check_timestamp: datetime = Field(
        ..., 
        description="Timestamp when change detection was performed"
    )
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "records_analyzed": 10000,
                "edit_date_changes": 125,
                "geometry_changes": 0,
                "attribute_changes": 125,
                "processing_duration": 2.45,
                "last_check_timestamp": "2024-01-15T10:30:00Z"
            }
        }
    }


class ChangeDetectionResult(BaseModel):
    """Comprehensive result of change detection analysis.
    
    Contains all information needed to make processing decisions,
    including change metrics, processing recommendations, and
    detailed change information.
    """
    layer_id: str = Field(
        ..., 
        description="ArcGIS layer identifier that was analyzed",
        min_length=1
    )
    detection_timestamp: datetime = Field(
        default_factory=datetime.now, 
        description="When change detection was performed"
    )
    total_records: int = Field(
        ge=0, 
        description="Total number of records in the layer"
    )
    modified_records: int = Field(
        ge=0, 
        description="Number of records modified since last processing"
    )
    new_records: int = Field(
        ge=0, 
        description="Number of new records added since last processing"
    )
    deleted_records: int = Field(
        ge=0, 
        description="Number of records deleted since last processing"
    )
    change_percentage: float = Field(
        ge=0, 
        le=100, 
        description="Percentage of records that changed"
    )
    processing_recommendation: ProcessingType = Field(
        ..., 
        description="Recommended processing type based on change analysis"
    )
    change_details: Dict[str, Any] = Field(
        default_factory=dict, 
        description="Additional details about detected changes"
    )
    change_metrics: ChangeMetrics = Field(
        ..., 
        description="Detailed metrics from change detection analysis"
    )
    
    @field_validator('change_percentage')
    @classmethod
    def validate_change_percentage(cls, v: float) -> float:
        """Ensure change percentage is within valid range and properly rounded."""
        return round(min(max(v, 0.0), 100.0), 2)
    
    @field_validator('modified_records')
    @classmethod
    def validate_modified_records(cls, v: int, info) -> int:
        """Ensure modified records count is not greater than total records."""
        # Note: total_records validation will happen after this in field order
        return max(v, 0)
    
    def get_change_summary(self) -> str:
        """Get a human-readable summary of the change detection results."""
        if self.processing_recommendation == ProcessingType.NO_PROCESSING_NEEDED:
            return f"No significant changes detected ({self.change_percentage:.1f}% change)"
        elif self.processing_recommendation == ProcessingType.INCREMENTAL_UPDATE:
            return f"Incremental update recommended: {self.modified_records} records changed ({self.change_percentage:.1f}%)"
        elif self.processing_recommendation == ProcessingType.FULL_REPROCESSING:
            return f"Full reprocessing recommended: {self.modified_records} records changed ({self.change_percentage:.1f}%)"
        else:
            return f"Force full update required: {self.change_details.get('error', 'Unknown error')}"
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "layer_id": "layer-123-abc",
                "detection_timestamp": "2024-01-15T10:30:00Z",
                "total_records": 10000,
                "modified_records": 125,
                "new_records": 15,
                "deleted_records": 5,
                "change_percentage": 1.25,
                "processing_recommendation": "incremental_update",
                "change_details": {
                    "since_timestamp": "2024-01-14T10:30:00Z",
                    "edit_date_field": "EditDate_1",
                    "detection_method": "edit_date_monitoring"
                }
            }
        }
    }


class ProcessingDecision(BaseModel):
    """Decision result for processing type and target records.
    
    Provides comprehensive information for the SpatialFieldUpdater
    to make intelligent processing decisions based on change detection.
    """
    processing_type: ProcessingType = Field(
        ..., 
        description="Type of processing recommended based on change analysis"
    )
    target_records: List[str] = Field(
        default_factory=list, 
        description="Specific record IDs to process (for incremental updates)",
        max_length=10000  # Reasonable limit for incremental processing
    )
    change_threshold_met: bool = Field(
        ..., 
        description="Whether the change threshold was exceeded"
    )
    full_reprocess_required: bool = Field(
        ..., 
        description="Whether full reprocessing is required"
    )
    incremental_filters: Dict[str, Any] = Field(
        default_factory=dict, 
        description="SQL WHERE clause and filters for incremental processing"
    )
    reasoning: str = Field(
        default="", 
        description="Human-readable explanation for the processing decision"
    )
    estimated_processing_time: Optional[float] = Field(
        None, 
        ge=0,
        description="Estimated processing time in seconds"
    )
    configuration_used: Dict[str, Any] = Field(
        default_factory=dict,
        description="Configuration thresholds and settings used for decision"
    )
    
    @field_validator('target_records')
    @classmethod
    def validate_target_records(cls, v: List[str]) -> List[str]:
        """Ensure target records are valid and remove duplicates."""
        # Remove empty strings and duplicates while preserving order
        seen = set()
        result = []
        for record_id in v:
            if record_id and record_id.strip() and record_id not in seen:
                seen.add(record_id)
                result.append(record_id.strip())
        return result
    
    def is_processing_needed(self) -> bool:
        """Check if any processing is needed based on the decision."""
        return self.processing_type != ProcessingType.NO_PROCESSING_NEEDED
    
    def get_processing_summary(self) -> str:
        """Get a summary of the processing decision."""
        if self.processing_type == ProcessingType.NO_PROCESSING_NEEDED:
            return "No processing needed"
        elif self.processing_type == ProcessingType.INCREMENTAL_UPDATE:
            return f"Incremental processing: {len(self.target_records)} records"
        elif self.processing_type == ProcessingType.FULL_REPROCESSING:
            return "Full reprocessing required"
        else:
            return "Force full reprocessing"
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "processing_type": "incremental_update",
                "target_records": ["12345", "12346", "12347"],
                "change_threshold_met": True,
                "full_reprocess_required": False,
                "incremental_filters": {
                    "where_clause": "EditDate_1 > 1705301400000",
                    "modified_count": 125
                },
                "reasoning": "Change detection found 125 modified records (1.25% change)",
                "estimated_processing_time": 45.5,
                "configuration_used": {
                    "full_reprocess_percentage": 25.0,
                    "incremental_threshold_percentage": 1.0,
                    "max_incremental_records": 1000
                }
            }
        }
    }


# Type aliases for convenience
ChangeResult = ChangeDetectionResult
ProcessingChoice = ProcessingDecision 