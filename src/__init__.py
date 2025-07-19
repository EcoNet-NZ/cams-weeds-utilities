"""
CAMS Framework Core Package

This package contains the core infrastructure for the CAMS (Conservation Activity
Management System) utilities framework, providing shared components and interfaces
for processing modules.
"""

from .interfaces import ModuleProcessor, ProcessingResult, ModuleStatus

__version__ = "1.0.0"
__all__ = ['ModuleProcessor', 'ProcessingResult', 'ModuleStatus'] 