"""
Configuration management module for CAMS Spatial Query Optimization System.

This module provides configuration loading and validation capabilities for
multi-environment deployments (development and production).
"""

from .config_loader import ConfigLoader

__all__ = ["ConfigLoader"] 