"""
Utility modules for CAMS Spatial Query Optimization System.

This module provides utility functions and setup for logging, validation,
and other common functionality used throughout the system.
"""

from .logging_setup import setup_logging, get_logger, log_performance

__all__ = ["setup_logging", "get_logger", "log_performance"] 