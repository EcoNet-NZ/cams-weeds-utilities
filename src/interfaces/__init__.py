"""CAMS Framework Interfaces

This package contains abstract interfaces and base classes for the CAMS framework,
providing standardized contracts for all processing modules.
"""

from .module_processor import ModuleProcessor, ProcessingResult, ModuleStatus

__all__ = ['ModuleProcessor', 'ProcessingResult', 'ModuleStatus'] 