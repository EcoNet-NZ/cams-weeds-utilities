"""
Custom exception classes for CAMS Spatial Query Optimization System.

This module defines domain-specific exceptions to provide clear error handling
and debugging information throughout the system.
"""

from typing import Optional, Dict, Any


class CAMSBaseException(Exception):
    """Base exception class for all CAMS system exceptions."""
    
    def __init__(self, message: str, context: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.message = message
        self.context = context or {}
    
    def __str__(self) -> str:
        if self.context:
            context_str = ", ".join(f"{k}={v}" for k, v in self.context.items())
            return f"{self.message} (Context: {context_str})"
        return self.message


class CAMSConfigurationError(CAMSBaseException):
    """
    Exception raised when configuration loading or validation fails.
    
    This exception is raised when:
    - Configuration files are missing or invalid
    - Environment configuration is malformed
    - Required configuration values are missing
    """
    pass


class CAMSValidationError(CAMSBaseException):
    """
    Exception raised when data validation fails.
    
    This exception is raised when:
    - Field mapping validation fails
    - Data type validation fails
    - Schema validation fails
    """
    pass


class CAMSAuthenticationError(CAMSBaseException):
    """
    Exception raised when authentication fails.
    
    This exception is raised when:
    - Invalid credentials provided
    - Authentication configuration errors
    - Environment variables missing
    """
    pass


class CAMSConnectionError(CAMSBaseException):
    """
    Exception raised when ArcGIS connection fails.
    
    This exception is raised when:
    - Network connection issues
    - Service unavailable
    - Connection timeouts
    """
    pass


class CAMSProcessingError(CAMSBaseException):
    """
    Exception raised when spatial processing fails.
    
    This exception is raised when:
    - Spatial queries fail
    - Data processing errors occur
    - Metadata updates fail
    """
    pass 