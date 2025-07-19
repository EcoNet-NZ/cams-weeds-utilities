"""CAMS Module Processor Interface

This module defines the abstract base class and data models that all CAMS processing
modules must implement to ensure consistent behavior and integration with the core framework.
"""

from abc import ABC, abstractmethod
from pydantic import BaseModel, Field
from typing import Optional, Dict, List, Any
from datetime import datetime


class ProcessingResult(BaseModel):
    """Result data model for module processing operations.
    
    This model standardizes the return value from all module processing operations,
    providing consistent success/failure reporting, metrics, and error details.
    """
    
    success: bool = Field(..., description="Whether the processing completed successfully")
    records_processed: int = Field(ge=0, description="Number of records processed")
    errors: List[str] = Field(default_factory=list, description="List of error messages if any")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional processing metadata")
    execution_time: float = Field(ge=0.0, description="Processing execution time in seconds")


class ModuleStatus(BaseModel):
    """Status data model for module health and configuration reporting.
    
    This model provides a standardized way for modules to report their current
    operational status, configuration validity, and health checks.
    """
    
    module_name: str = Field(..., description="Name of the processing module")
    is_configured: bool = Field(..., description="Whether the module is properly configured")
    last_run: Optional[datetime] = Field(None, description="Timestamp of the last successful processing run")
    status: str = Field(..., description="Current module status: 'ready', 'running', 'error', 'disabled'")
    health_check: bool = Field(..., description="Result of the most recent health check")


class ModuleProcessor(ABC):
    """Abstract base class for all CAMS processing modules.
    
    This interface defines the contract that all processing modules must implement
    to ensure consistent behavior, configuration validation, and integration with
    the CAMS framework infrastructure.
    
    All concrete module implementations should inherit from this class and implement
    all abstract methods according to their specific processing requirements.
    """
    
    @abstractmethod
    def __init__(self, config_loader):
        """Initialize module with shared configuration.
        
        Args:
            config_loader: ConfigLoader instance providing access to framework configuration
        """
        pass
    
    @abstractmethod
    def validate_configuration(self) -> bool:
        """Validate module-specific configuration.
        
        This method should verify that all required configuration values are present
        and valid for the module to operate correctly. It should check both the
        module's specific configuration file and any required framework configuration.
        
        Returns:
            bool: True if configuration is valid and complete, False otherwise
        """
        pass
    
    @abstractmethod
    def process(self, dry_run: bool = False) -> ProcessingResult:
        """Execute module processing logic.
        
        This is the main entry point for module processing. The implementation should
        perform all necessary processing steps while respecting the dry_run flag to
        avoid making actual changes when in testing mode.
        
        Args:
            dry_run: If True, perform all processing logic without making actual changes
            
        Returns:
            ProcessingResult: Standardized result object with success status, metrics, and errors
        """
        pass
    
    @abstractmethod
    def get_status(self) -> ModuleStatus:
        """Get current module processing status.
        
        This method should return the current operational status of the module,
        including configuration validity, last run information, and health check results.
        
        Returns:
            ModuleStatus: Current module status and health information
        """
        pass 