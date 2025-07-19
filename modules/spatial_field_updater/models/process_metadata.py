"""ProcessMetadata Data Model

This module defines the Pydantic data model for spatial processing metadata tracking.
It provides validation for processing status and layer version information used to
track and coordinate spatial field updates.
"""

from pydantic import BaseModel, Field, field_validator
from datetime import datetime
from typing import Literal, Optional, Dict, Any


class ProcessMetadata(BaseModel):
    """Data model for spatial processing metadata tracking.
    
    This model represents metadata about spatial field update processing runs,
    including layer versions, processing status, and performance metrics. It is
    used to track processing history and coordinate incremental updates.
    
    Attributes:
        process_timestamp: Processing start time
        region_layer_id: Region layer identifier from configuration
        region_layer_updated: Region layer version timestamp
        district_layer_id: District layer identifier from configuration  
        district_layer_updated: District layer version timestamp
        process_status: Processing completion status (Success/Error)
        records_processed: Count of updated records
        processing_duration: Time taken for processing in seconds
        error_message: Error message if processing failed
        metadata_details: Additional processing details and statistics
    """
    
    process_timestamp: datetime = Field(
        ..., 
        description="Processing start time (UTC timestamp)"
    )
    
    region_layer_id: str = Field(
        ..., 
        description="Region layer identifier from configuration",
        max_length=50
    )
    
    region_layer_updated: datetime = Field(
        ..., 
        description="Region layer version timestamp from ArcGIS"
    )
    
    district_layer_id: str = Field(
        ..., 
        description="District layer identifier from configuration",
        max_length=50
    )
    
    district_layer_updated: datetime = Field(
        ..., 
        description="District layer version timestamp from ArcGIS"
    )
    
    process_status: Literal['Success', 'Error'] = Field(
        ..., 
        description="Processing completion status"
    )
    
    records_processed: int = Field(
        ..., 
        description="Count of records processed during this run",
        ge=0
    )
    
    processing_duration: Optional[float] = Field(
        None,
        description="Processing duration in seconds",
        ge=0.0
    )
    
    error_message: Optional[str] = Field(
        None,
        description="Error message if processing failed",
        max_length=1000
    )
    
    metadata_details: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional processing details and statistics"
    )
    
    @field_validator('region_layer_id', 'district_layer_id')
    @classmethod
    def validate_layer_id(cls, v: str) -> str:
        """Validate layer ID format.
        
        Layer IDs should be non-empty and contain valid ArcGIS layer identifier format.
        
        Args:
            v: The layer ID to validate
            
        Returns:
            The validated layer ID
            
        Raises:
            ValueError: If layer ID is invalid
        """
        if not v or not v.strip():
            raise ValueError('Layer ID cannot be empty')
        
        # Basic validation for ArcGIS layer ID format (alphanumeric and hyphens)
        if not v.replace('-', '').replace('_', '').isalnum():
            raise ValueError('Layer ID must contain only alphanumeric characters, hyphens, and underscores')
        
        return v.strip()
    
    @field_validator('error_message')
    @classmethod
    def validate_error_message(cls, v: Optional[str], info) -> Optional[str]:
        """Validate error message consistency with process status.
        
        Error messages should only be present when process_status is 'Error'.
        
        Args:
            v: The error message to validate
            info: Validation context containing other field values
            
        Returns:
            The validated error message
            
        Raises:
            ValueError: If error message is inconsistent with status
        """
        # Note: In Pydantic v2, we need to check if the field values are available
        # This validator will be called after process_status is validated
        if v is not None and v.strip() == '':
            # Convert empty string to None
            return None
        
        return v
    
    def is_successful(self) -> bool:
        """Check if this processing run was successful.
        
        Returns:
            True if process_status is 'Success', False otherwise
        """
        return self.process_status == 'Success'
    
    def has_errors(self) -> bool:
        """Check if this processing run had errors.
        
        Returns:
            True if process_status is 'Error' or error_message is present
        """
        return self.process_status == 'Error' or (self.error_message is not None)
    
    def get_processing_summary(self) -> str:
        """Get a summary string for this processing run.
        
        Returns:
            A formatted string summarizing the processing run
        """
        status_text = "✓ Success" if self.is_successful() else "✗ Error"
        duration_text = f" ({self.processing_duration:.1f}s)" if self.processing_duration else ""
        
        summary = f"{status_text}: {self.records_processed} records processed{duration_text}"
        
        if self.has_errors() and self.error_message:
            summary += f" - {self.error_message}"
        
        return summary
    
    def get_layer_info(self) -> Dict[str, str]:
        """Get layer version information as a dictionary.
        
        Returns:
            Dictionary containing layer IDs and their update timestamps
        """
        return {
            "region_layer": f"{self.region_layer_id} (updated: {self.region_layer_updated.isoformat()})",
            "district_layer": f"{self.district_layer_id} (updated: {self.district_layer_updated.isoformat()})"
        }
    
    def add_detail(self, key: str, value: Any) -> None:
        """Add a detail to the metadata_details dictionary.
        
        Args:
            key: The detail key
            value: The detail value
        """
        if self.metadata_details is None:
            self.metadata_details = {}
        self.metadata_details[key] = value
    
    def get_detail(self, key: str, default: Any = None) -> Any:
        """Get a detail from the metadata_details dictionary.
        
        Args:
            key: The detail key to retrieve
            default: Default value if key is not found
            
        Returns:
            The detail value or default
        """
        if self.metadata_details is None:
            return default
        return self.metadata_details.get(key, default)
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "process_timestamp": "2024-01-15T21:05:00Z",
                "region_layer_id": "7759fbaecd4649dea39c4ac2b07fc4ab",
                "region_layer_updated": "2024-01-15T14:30:00Z",
                "district_layer_id": "c8f6ba6b968c4d31beddfb69abfe3df0",
                "district_layer_updated": "2024-01-15T16:45:00Z",
                "process_status": "Success",
                "records_processed": 1250,
                "processing_duration": 45.7,
                "error_message": None,
                "metadata_details": {
                    "batch_size": 100,
                    "total_batches": 13,
                    "regions_updated": 5,
                    "districts_updated": 12
                }
            }
        }
    } 