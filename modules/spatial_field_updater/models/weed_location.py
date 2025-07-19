"""WeedLocation Data Model

This module defines the Pydantic data model for weed location records with spatial assignments.
It provides validation for ArcGIS field data and ensures data integrity for spatial processing.
"""

from pydantic import BaseModel, Field, field_validator
from typing import Optional, Dict, Any
from datetime import datetime


class WeedLocation(BaseModel):
    """Data model for weed location records with spatial assignments.
    
    This model represents a weed location feature from ArcGIS with region and district
    assignments. It provides validation for all required and optional fields, ensuring
    data integrity throughout the spatial processing workflow.
    
    Attributes:
        object_id: ArcGIS OBJECTID primary key
        global_id: ArcGIS GlobalID unique identifier
        region_code: 2-character region assignment (calculated by spatial intersection)
        district_code: 5-character district assignment (calculated by spatial intersection)
        edit_date: Last modification timestamp from ArcGIS
        geometry: ArcGIS geometry object (point, polygon, etc.)
    """
    
    object_id: int = Field(
        ..., 
        description="ArcGIS OBJECTID primary key",
        ge=1  # Object IDs are always positive integers
    )
    
    global_id: str = Field(
        ..., 
        description="ArcGIS GlobalID unique identifier",
        min_length=36,
        max_length=38,  # UUID with or without braces
        pattern=r'^(\{?[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\}?)$'
    )
    
    region_code: Optional[str] = Field(
        None, 
        description="2-character region assignment from spatial intersection",
        max_length=2
    )
    
    district_code: Optional[str] = Field(
        None, 
        description="5-character district assignment from spatial intersection",
        max_length=5
    )
    
    edit_date: Optional[datetime] = Field(
        None, 
        description="Last modification timestamp from ArcGIS EditDate_1 field"
    )
    
    geometry: Dict[str, Any] = Field(
        ..., 
        description="ArcGIS geometry object (point, polygon, etc.)"
    )
    
    @field_validator('region_code')
    @classmethod
    def validate_region_code(cls, v: Optional[str]) -> Optional[str]:
        """Validate region code format.
        
        Region codes must be exactly 2 characters when provided.
        
        Args:
            v: The region code value to validate
            
        Returns:
            The validated region code or None
            
        Raises:
            ValueError: If region code is not exactly 2 characters
        """
        if v is not None:
            if len(v) != 2:
                raise ValueError('Region code must be exactly 2 characters')
            if not v.isalnum():
                raise ValueError('Region code must contain only alphanumeric characters')
        return v
    
    @field_validator('district_code')
    @classmethod
    def validate_district_code(cls, v: Optional[str]) -> Optional[str]:
        """Validate district code format.
        
        District codes must be exactly 5 characters when provided.
        
        Args:
            v: The district code value to validate
            
        Returns:
            The validated district code or None
            
        Raises:
            ValueError: If district code is not exactly 5 characters
        """
        if v is not None:
            if len(v) != 5:
                raise ValueError('District code must be exactly 5 characters')
            if not v.isalnum():
                raise ValueError('District code must contain only alphanumeric characters')
        return v
    
    @field_validator('geometry')
    @classmethod
    def validate_geometry(cls, v: Dict[str, Any]) -> Dict[str, Any]:
        """Validate ArcGIS geometry object structure.
        
        Ensures the geometry object has the required ArcGIS geometry structure.
        
        Args:
            v: The geometry dictionary to validate
            
        Returns:
            The validated geometry dictionary
            
        Raises:
            ValueError: If geometry is missing required fields
        """
        if not isinstance(v, dict):
            raise ValueError('Geometry must be a dictionary')
        
        # Basic validation for ArcGIS geometry structure
        if 'x' not in v and 'rings' not in v and 'paths' not in v:
            raise ValueError('Geometry must contain valid ArcGIS geometry structure')
        
        return v
    
    def has_spatial_assignments(self) -> bool:
        """Check if this weed location has both region and district assignments.
        
        Returns:
            True if both region_code and district_code are assigned, False otherwise
        """
        return self.region_code is not None and self.district_code is not None
    
    def needs_spatial_update(self) -> bool:
        """Check if this weed location needs spatial assignment updates.
        
        Returns:
            True if either region_code or district_code is missing, False otherwise
        """
        return self.region_code is None or self.district_code is None
    
    def get_location_summary(self) -> str:
        """Get a summary string for this weed location.
        
        Returns:
            A formatted string summarizing the weed location
        """
        region_text = f"Region: {self.region_code}" if self.region_code else "Region: Unassigned"
        district_text = f"District: {self.district_code}" if self.district_code else "District: Unassigned"
        
        return f"WeedLocation {self.object_id} - {region_text}, {district_text}"
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "object_id": 12345,
                "global_id": "{A1B2C3D4-E5F6-7890-ABCD-EF1234567890}",
                "region_code": "01",
                "district_code": "ABC01",
                "edit_date": "2024-01-15T10:30:00Z",
                "geometry": {
                    "x": 1750000.0,
                    "y": 5950000.0,
                    "spatialReference": {"wkid": 2193}
                }
            }
        }
    } 