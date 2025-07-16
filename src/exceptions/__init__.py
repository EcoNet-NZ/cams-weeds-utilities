"""
Custom exceptions for CAMS Spatial Query Optimization System.

This module provides domain-specific exception classes for error handling
and debugging throughout the system.
"""

from .custom_exceptions import (
    CAMSBaseException,
    CAMSConfigurationError,
    CAMSValidationError,
    CAMSConnectionError,
    CAMSProcessingError,
)

__all__ = [
    "CAMSBaseException",
    "CAMSConfigurationError",
    "CAMSValidationError",
    "CAMSConnectionError",
    "CAMSProcessingError",
] 