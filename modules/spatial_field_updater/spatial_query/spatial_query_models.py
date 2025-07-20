"""Spatial Query Processing Models for Spatial Field Updater

Comprehensive data models for spatial processing results, assignments, and metrics
using Pydantic for validation and serialization following Context7 best practices.
"""

from typing import Dict, List, Any, Optional
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field, field_validator
import logging

logger = logging.getLogger(__name__)


class ProcessingMethod(str, Enum):
    """Method used for spatial processing."""
    FULL_INTERSECTION = "full_intersection"
    CACHED_INTERSECTION = "cached_intersection"
    GEOMETRY_REPAIR = "geometry_repair"
    FALLBACK_ASSIGNMENT = "fallback_assignment"


class SpatialAssignment(BaseModel):
    """Individual spatial assignment result for a weed location.
    
    Represents the result of spatial intersection processing for a single
    weed location feature, including assigned region/district codes and
    processing quality metrics.
    """
    object_id: str = Field(..., description="OBJECTID of the weed location feature")
    region_code: Optional[str] = Field(None, description="Assigned REGC_code from region intersection")
    district_code: Optional[str] = Field(None, description="Assigned TALB_code from district intersection")
    intersection_quality: float = Field(ge=0, le=1, description="Quality score of spatial intersection (0-1)")
    processing_method: ProcessingMethod = Field(..., description="Method used for assignment")
    geometry_valid: bool = Field(..., description="Whether geometry was valid for intersection")
    region_intersection_area: Optional[float] = Field(None, ge=0, description="Area of region intersection")
    district_intersection_area: Optional[float] = Field(None, ge=0, description="Area of district intersection")
    processing_duration: float = Field(ge=0, description="Time taken for this assignment in seconds")
    
    @field_validator('intersection_quality')
    @classmethod
    def validate_quality_score(cls, v: float) -> float:
        """Ensure intersection quality is properly bounded."""
        return round(min(max(v, 0.0), 1.0), 3)
    
    def get_assignment_status(self) -> str:
        """Get human-readable assignment status."""
        if self.region_code and self.district_code:
            return "both_assigned"
        elif self.region_code:
            return "region_only"
        elif self.district_code:
            return "district_only"
        else:
            return "no_assignment"
    
    def is_successful(self) -> bool:
        """Check if assignment was successful (at least one code assigned)."""
        return bool(self.region_code or self.district_code)


class BatchResult(BaseModel):
    """Result of processing a batch of weed locations.
    
    Tracks processing results, errors, and performance metrics for a single
    batch of weed location features processed together.
    """
    batch_number: int = Field(ge=1, description="Sequential batch number")
    records_processed: int = Field(ge=0, description="Number of records in this batch")
    success_count: int = Field(ge=0, description="Number of successful assignments")
    error_count: int = Field(ge=0, description="Number of failed assignments")
    processing_time: float = Field(ge=0, description="Time taken for batch processing")
    errors: List[str] = Field(default_factory=list, description="Error messages from failed assignments")
    assignment_summary: Dict[str, int] = Field(default_factory=dict, description="Summary of assignment types")
    
    @field_validator('success_count', 'error_count')
    @classmethod
    def validate_counts(cls, v: int, info) -> int:
        """Ensure counts are non-negative."""
        return max(v, 0)
    
    def get_success_rate(self) -> float:
        """Calculate success rate for this batch."""
        if self.records_processed == 0:
            return 0.0
        return self.success_count / self.records_processed
    
    def get_processing_rate(self) -> float:
        """Calculate records processed per second."""
        if self.processing_time == 0:
            return 0.0
        return self.records_processed / self.processing_time


class SpatialMetrics(BaseModel):
    """Comprehensive metrics for spatial processing operations.
    
    Tracks detailed performance metrics for spatial processing including
    timing, success rates, and resource usage.
    """
    total_intersections_calculated: int = Field(ge=0, description="Total spatial intersections performed")
    successful_assignments: int = Field(ge=0, description="Number of successful spatial assignments")
    failed_assignments: int = Field(ge=0, description="Number of failed spatial assignments")
    geometry_validation_time: float = Field(ge=0, description="Time spent on geometry validation")
    intersection_calculation_time: float = Field(ge=0, description="Time spent on intersection calculations")
    update_operation_time: float = Field(ge=0, description="Time spent on feature updates")
    memory_peak_mb: Optional[float] = Field(None, ge=0, description="Peak memory usage in MB")
    cache_hit_rate: float = Field(ge=0, le=1, description="Cache hit rate for spatial operations")
    
    def get_total_processing_time(self) -> float:
        """Calculate total processing time across all operations."""
        return (self.geometry_validation_time + 
               self.intersection_calculation_time + 
               self.update_operation_time)
    
    def get_success_rate(self) -> float:
        """Calculate success rate of spatial assignments."""
        total = self.successful_assignments + self.failed_assignments
        return self.successful_assignments / total if total > 0 else 0.0
    
    def get_intersection_rate(self) -> float:
        """Calculate intersections per second during calculation phase."""
        if self.intersection_calculation_time == 0:
            return 0.0
        return self.total_intersections_calculated / self.intersection_calculation_time
    
    def get_performance_summary(self) -> Dict[str, Any]:
        """Get comprehensive performance summary."""
        return {
            "total_time": self.get_total_processing_time(),
            "success_rate": self.get_success_rate(),
            "intersection_rate": self.get_intersection_rate(),
            "cache_efficiency": self.cache_hit_rate,
            "memory_peak_mb": self.memory_peak_mb
        }


class SpatialProcessingResult(BaseModel):
    """Comprehensive result of spatial query processing operation.
    
    Top-level result containing all processing metrics, batch results,
    and spatial assignment summaries for a complete spatial processing run.
    """
    processed_count: int = Field(ge=0, description="Total number of records processed")
    updated_count: int = Field(ge=0, description="Number of records successfully updated")
    failed_count: int = Field(ge=0, description="Number of records that failed processing")
    processing_duration: float = Field(ge=0, description="Total processing duration in seconds")
    batch_results: List[BatchResult] = Field(default_factory=list, description="Results from each processing batch")
    spatial_metrics: SpatialMetrics = Field(..., description="Detailed spatial processing metrics")
    assignment_summary: Dict[str, Any] = Field(default_factory=dict, description="Summary of spatial assignments")
    region_assignments: int = Field(ge=0, description="Number of successful region assignments")
    district_assignments: int = Field(ge=0, description="Number of successful district assignments")
    processing_timestamp: datetime = Field(default_factory=datetime.now, description="When processing completed")
    
    def get_processing_summary(self) -> str:
        """Generate human-readable processing summary."""
        success_rate = self.spatial_metrics.get_success_rate() * 100
        processing_rate = self.processed_count / self.processing_duration if self.processing_duration > 0 else 0
        return (f"Processed {self.processed_count} records in {self.processing_duration:.1f}s "
               f"({success_rate:.1f}% success rate, {processing_rate:.1f} records/sec)")
    
    def get_assignment_breakdown(self) -> Dict[str, int]:
        """Get breakdown of assignment types."""
        return {
            "region_only": self.assignment_summary.get("region_only", 0),
            "district_only": self.assignment_summary.get("district_only", 0), 
            "both_assigned": self.assignment_summary.get("both_assigned", 0),
            "no_assignment": self.assignment_summary.get("no_assignment", 0)
        }
    
    def get_processing_efficiency(self) -> Dict[str, float]:
        """Calculate processing efficiency metrics."""
        total_time = self.processing_duration
        if total_time == 0:
            return {"overall_rate": 0.0, "update_rate": 0.0, "failure_rate": 0.0}
        
        return {
            "overall_rate": self.processed_count / total_time,
            "update_rate": self.updated_count / total_time,
            "failure_rate": self.failed_count / total_time if self.failed_count > 0 else 0.0
        }
    
    def is_successful(self) -> bool:
        """Check if overall processing was successful (>50% success rate)."""
        return self.spatial_metrics.get_success_rate() > 0.5


class SpatialProcessingConfig(BaseModel):
    """Configuration settings for spatial processing operations.
    
    Validation model for spatial processing configuration parameters
    loaded from field_updater_config.json.
    """
    enabled: bool = Field(True, description="Whether spatial processing is enabled")
    batch_size: int = Field(250, ge=1, le=5000, description="Number of records per batch")
    max_batch_size: int = Field(1000, ge=100, description="Maximum allowed batch size")
    geometry_validation_enabled: bool = Field(True, description="Enable geometry validation")
    repair_invalid_geometry: bool = Field(True, description="Attempt to repair invalid geometries")
    cache_boundary_layers: bool = Field(True, description="Cache boundary layers for performance")
    memory_limit_mb: int = Field(1024, ge=128, description="Memory limit in MB")
    quality_threshold: float = Field(0.0, ge=0.0, le=1.0, description="Minimum quality threshold for assignments")
    
    @field_validator('max_batch_size')
    @classmethod
    def validate_max_batch_size(cls, v: int, info) -> int:
        """Ensure max_batch_size is larger than batch_size."""
        batch_size = info.data.get('batch_size', 250)
        if v < batch_size:
            logger.warning(f"max_batch_size {v} is smaller than batch_size {batch_size}, adjusting")
            return batch_size
        return v


class SpatialUpdateResult(BaseModel):
    """Result of updating spatial assignments back to the feature layer.
    
    Tracks the results of applying calculated spatial assignments
    to the weed locations feature layer.
    """
    updated_count: int = Field(ge=0, description="Number of features successfully updated")
    failed_count: int = Field(ge=0, description="Number of features that failed to update")
    update_duration: float = Field(ge=0, description="Time taken for update operations")
    errors: List[str] = Field(default_factory=list, description="Update error messages")
    batch_updates: List[Dict[str, Any]] = Field(default_factory=list, description="Results from batch update operations")
    
    def get_update_success_rate(self) -> float:
        """Calculate success rate of update operations."""
        total = self.updated_count + self.failed_count
        return self.updated_count / total if total > 0 else 0.0
    
    def get_update_rate(self) -> float:
        """Calculate updates per second."""
        if self.update_duration == 0:
            return 0.0
        return self.updated_count / self.update_duration 