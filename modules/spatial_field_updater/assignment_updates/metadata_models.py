"""Enhanced Metadata Models for Spatial Processing

Comprehensive Pydantic models for enhanced spatial processing metadata
following framework model patterns and extending base metadata capabilities.
"""

from typing import Dict, List, Any, Optional
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field

from ..spatial_query import SpatialMetrics
from ..change_detection import ProcessingType


class LayerVersionInfo(BaseModel):
    """Layer version information for processing tracking."""
    weed_layer_id: str = Field(..., description="Weed locations layer identifier")
    weed_layer_updated: datetime = Field(..., description="Weed layer last update timestamp")
    region_layer_id: str = Field(..., description="Region layer identifier")
    region_layer_updated: datetime = Field(..., description="Region layer last update timestamp")
    district_layer_id: str = Field(..., description="District layer identifier")
    district_layer_updated: datetime = Field(..., description="District layer last update timestamp")


class UpdateMetrics(BaseModel):
    """Comprehensive metrics for update operations."""
    total_assignments: int = Field(ge=0, description="Total number of assignments processed")
    successful_updates: int = Field(ge=0, description="Number of successful updates")
    failed_updates: int = Field(ge=0, description="Number of failed updates")
    validation_failures: int = Field(ge=0, description="Number of validation failures")
    batch_count: int = Field(ge=1, description="Number of batches processed")
    average_batch_size: float = Field(ge=0, description="Average size of update batches")
    update_rate_per_second: float = Field(ge=0, description="Updates processed per second")
    error_breakdown: Dict[str, int] = Field(default_factory=dict, description="Breakdown of error types")
    query_optimization_ratio: float = Field(ge=0, description="Query reduction ratio (old queries / new queries)")
    
    def get_success_rate(self) -> float:
        """Calculate overall success rate."""
        if self.total_assignments == 0:
            return 0.0
        return self.successful_updates / self.total_assignments
    
    def get_failure_rate(self) -> float:
        """Calculate overall failure rate."""
        if self.total_assignments == 0:
            return 0.0
        return self.failed_updates / self.total_assignments
    
    def get_performance_summary(self) -> str:
        """Generate performance summary string."""
        return (f"Success: {self.get_success_rate():.1%}, "
                f"Rate: {self.update_rate_per_second:.1f}/sec, "
                f"Query optimization: {self.query_optimization_ratio:.0f}x reduction")


class ErrorSummary(BaseModel):
    """Comprehensive error summary for processing operations."""
    validation_errors: List[str] = Field(default_factory=list, description="Validation error messages")
    update_errors: List[str] = Field(default_factory=list, description="Update operation errors")
    permission_errors: List[str] = Field(default_factory=list, description="Permission-related errors")
    connectivity_errors: List[str] = Field(default_factory=list, description="Connectivity errors")
    rollback_errors: List[str] = Field(default_factory=list, description="Rollback operation errors")
    error_patterns: Dict[str, int] = Field(default_factory=dict, description="Common error pattern counts")
    
    def get_total_errors(self) -> int:
        """Get total number of errors across all categories."""
        return (len(self.validation_errors) + len(self.update_errors) + 
                len(self.permission_errors) + len(self.connectivity_errors) + 
                len(self.rollback_errors))
    
    def get_error_categories(self) -> Dict[str, int]:
        """Get error count by category."""
        return {
            "validation": len(self.validation_errors),
            "update": len(self.update_errors), 
            "permission": len(self.permission_errors),
            "connectivity": len(self.connectivity_errors),
            "rollback": len(self.rollback_errors)
        }


class ProcessingPerformanceMetrics(BaseModel):
    """Performance metrics for spatial processing operations."""
    spatial_processing_rate: float = Field(ge=0, description="Spatial intersections per second")
    update_processing_rate: float = Field(ge=0, description="Updates processed per second")
    total_processing_rate: float = Field(ge=0, description="Overall records processed per second")
    memory_peak_mb: Optional[float] = Field(None, ge=0, description="Peak memory usage in MB")
    cache_hit_rate: float = Field(ge=0, le=1, description="Cache hit rate for boundary layers")
    query_optimization_achieved: float = Field(ge=0, description="Actual query reduction factor")
    
    def get_performance_rating(self) -> str:
        """Get performance rating based on processing rates."""
        if self.total_processing_rate > 100:
            return "Excellent"
        elif self.total_processing_rate > 50:
            return "Good"
        elif self.total_processing_rate > 25:
            return "Fair"
        else:
            return "Poor"


class EnhancedProcessMetadata(BaseModel):
    """Enhanced processing metadata with comprehensive spatial processing details.
    
    Extends base ProcessMetadata with spatial-specific information,
    detailed metrics, and framework-consistent tracking.
    """
    processing_id: str = Field(..., description="Unique processing identifier")
    process_timestamp: datetime = Field(..., description="Processing start timestamp")
    processing_type: ProcessingType = Field(..., description="Type of processing performed")
    records_processed: int = Field(ge=0, description="Total number of records processed")
    records_updated: int = Field(ge=0, description="Number of records successfully updated")
    records_failed: int = Field(ge=0, description="Number of records that failed processing")
    processing_duration: float = Field(ge=0, description="Spatial processing duration in seconds")
    update_duration: float = Field(ge=0, description="Update operation duration in seconds")
    spatial_metrics: SpatialMetrics = Field(..., description="Detailed spatial processing metrics")
    update_metrics: UpdateMetrics = Field(..., description="Detailed update operation metrics")
    error_summary: ErrorSummary = Field(..., description="Comprehensive error summary")
    layer_versions: LayerVersionInfo = Field(..., description="Layer version information")
    performance_metrics: ProcessingPerformanceMetrics = Field(..., description="Performance metrics")
    configuration_snapshot: Dict[str, Any] = Field(default_factory=dict, description="Configuration used for processing")
    processing_summary: str = Field(..., description="Human-readable processing summary")
    optimization_notes: List[str] = Field(default_factory=list, description="Performance optimization notes")
    
    def get_total_duration(self) -> float:
        """Get total processing duration including updates."""
        return self.processing_duration + self.update_duration
    
    def get_overall_success_rate(self) -> float:
        """Calculate overall processing success rate."""
        if self.records_processed == 0:
            return 0.0
        return self.records_updated / self.records_processed
    
    def is_successful(self, threshold: float = 0.95) -> bool:
        """Check if processing was successful based on threshold."""
        return self.get_overall_success_rate() >= threshold
    
    def get_comprehensive_summary(self) -> str:
        """Generate comprehensive processing summary."""
        success_rate = self.get_overall_success_rate()
        total_duration = self.get_total_duration()
        
        return (f"Processing {self.processing_id}: {self.processing_type} - "
                f"{self.records_updated}/{self.records_processed} records updated "
                f"({success_rate:.1%} success) in {total_duration:.1f}s. "
                f"Performance: {self.performance_metrics.get_performance_rating()}")
    
    def get_optimization_summary(self) -> str:
        """Generate optimization achievement summary."""
        query_reduction = self.update_metrics.query_optimization_ratio
        cache_rate = self.performance_metrics.cache_hit_rate
        
        return (f"Query optimization: {query_reduction:.0f}x reduction, "
                f"Cache hit rate: {cache_rate:.1%}, "
                f"Processing rate: {self.performance_metrics.total_processing_rate:.1f} records/sec")


class MetadataValidationResult(BaseModel):
    """Result of metadata integrity validation."""
    is_valid: bool = Field(..., description="Whether metadata is valid")
    errors: List[str] = Field(default_factory=list, description="Validation error messages")
    warnings: List[str] = Field(default_factory=list, description="Validation warnings")
    validation_timestamp: datetime = Field(default_factory=datetime.now, description="When validation was performed")
    validation_duration: float = Field(ge=0, description="Time taken for validation")
    
    def get_validation_summary(self) -> str:
        """Get validation summary string."""
        status = "PASSED" if self.is_valid else "FAILED"
        return f"Metadata validation {status} in {self.validation_duration:.2f}s" 