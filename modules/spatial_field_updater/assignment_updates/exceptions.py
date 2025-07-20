"""Assignment Update Specific Exceptions

Extends framework exception hierarchy with assignment update specific
error types for comprehensive error handling and classification.
"""

from typing import List
from src.exceptions import CAMSBaseException, CAMSProcessingError, CAMSValidationError


class SpatialAssignmentException(CAMSProcessingError):
    """Base exception for spatial assignment operations."""
    pass


class BatchUpdateException(SpatialAssignmentException):
    """Exception for batch update operation failures."""
    
    def __init__(self, message: str, failed_count: int = 0, partial_success: bool = False):
        super().__init__(message)
        self.failed_count = failed_count
        self.partial_success = partial_success


class AssignmentValidationException(CAMSValidationError):
    """Exception for assignment validation failures."""
    
    def __init__(self, message: str, validation_errors: List[str] = None):
        super().__init__(message)
        self.validation_errors = validation_errors or []


class MetadataIntegrityException(CAMSValidationError):
    """Exception for metadata integrity validation failures."""
    pass


class LayerAccessException(SpatialAssignmentException):
    """Exception for layer access issues during updates."""
    pass


class RollbackException(SpatialAssignmentException):
    """Exception for rollback operation failures."""
    
    def __init__(self, message: str, rollback_count: int = 0):
        super().__init__(message)
        self.rollback_count = rollback_count


class UpdatePermissionException(SpatialAssignmentException):
    """Exception for insufficient update permissions."""
    pass


class FeatureAccessibilityException(SpatialAssignmentException):
    """Exception for feature accessibility issues."""
    pass 