"""Data Models for Batch Update Operations

Comprehensive Pydantic models for batch update results, validation,
and metrics tracking following framework model patterns and Context7 best practices.
"""

from typing import List, Dict, Any, Optional
from datetime import datetime
from pydantic import BaseModel, Field


class ValidationResult(BaseModel):
    """Result of assignment validation operations."""
    is_valid: bool = Field(..., description="Whether validation passed")
    errors: List[str] = Field(default_factory=list, description="Validation error messages")
    warnings: List[str] = Field(default_factory=list, description="Validation warnings")
    validation_duration: float = Field(ge=0, description="Time taken for validation")
    validated_count: int = Field(ge=0, description="Number of assignments validated")


class AccessibilityResult(BaseModel):
    """Result of feature accessibility checks."""
    is_accessible: bool = Field(..., description="Whether features are accessible")
    accessible_count: int = Field(ge=0, description="Number of accessible features")
    inaccessible_count: int = Field(ge=0, description="Number of inaccessible features")
    errors: List[str] = Field(default_factory=list, description="Accessibility error messages")


class PermissionResult(BaseModel):
    """Result of layer permission verification."""
    has_permission: bool = Field(..., description="Whether update permissions are available")
    permissions: List[str] = Field(default_factory=list, description="Available permissions")
    errors: List[str] = Field(default_factory=list, description="Permission error messages")


class IntegrityResult(BaseModel):
    """Result of assignment integrity validation."""
    is_valid: bool = Field(..., description="Whether assignment integrity is valid")
    validation_errors: List[str] = Field(default_factory=list, description="Integrity validation errors")
    warnings: List[str] = Field(default_factory=list, description="Integrity warnings")


class BatchUpdateResult(BaseModel):
    """Result of batch update operations."""
    updated_count: int = Field(ge=0, description="Number of features successfully updated")
    failed_count: int = Field(ge=0, description="Number of features that failed to update")
    successful_object_ids: List[str] = Field(default_factory=list, description="Object IDs of successful updates")
    failed_object_ids: List[str] = Field(default_factory=list, description="Object IDs of failed updates")
    errors: List[str] = Field(default_factory=list, description="Update error messages")
    update_duration: float = Field(ge=0, description="Time taken for batch update")
    
    def get_success_rate(self) -> float:
        """Calculate update success rate."""
        total = self.updated_count + self.failed_count
        return self.updated_count / total if total > 0 else 0.0


class RollbackResult(BaseModel):
    """Result of rollback operations."""
    success: bool = Field(..., description="Whether rollback was successful")
    rollback_count: int = Field(ge=0, description="Number of features rolled back")
    failed_rollback_count: int = Field(ge=0, description="Number of features that failed rollback")
    rollback_duration: float = Field(ge=0, description="Time taken for rollback operation")
    errors: List[str] = Field(default_factory=list, description="Rollback error messages")


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


class MetadataValidationResult(BaseModel):
    """Result of metadata integrity validation."""
    is_valid: bool = Field(..., description="Whether metadata is valid")
    errors: List[str] = Field(default_factory=list, description="Validation error messages")
    warnings: List[str] = Field(default_factory=list, description="Validation warnings")
    validation_timestamp: datetime = Field(default_factory=datetime.now, description="When validation was performed") 