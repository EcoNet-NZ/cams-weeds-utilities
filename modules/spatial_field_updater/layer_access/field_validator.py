"""Field Schema Validation System for ArcGIS layers.

Implements comprehensive field validation against expected schemas following
Context7 best practices for field type checking and compatibility.
"""

from typing import Dict, List, Set
from pydantic import BaseModel, Field
import logging
import json
from pathlib import Path

from .layer_access_manager import LayerAccessManager, FieldDefinition
from src.config.config_loader import ConfigLoader

logger = logging.getLogger(__name__)


class FieldValidationResult(BaseModel):
    """Result of field schema validation.
    
    Comprehensive validation result following Context7 recommendations
    for detailed error reporting and validation status tracking.
    """
    layer_id: str = Field(..., description="Layer ID that was validated")
    validation_passed: bool = Field(..., description="Overall validation result")
    missing_fields: List[str] = Field(default_factory=list, description="Required fields not found")
    unexpected_fields: List[str] = Field(default_factory=list, description="Unexpected fields found")
    type_mismatches: List[str] = Field(default_factory=list, description="Fields with incorrect types")
    validation_errors: List[str] = Field(default_factory=list, description="Detailed validation errors")


class FieldValidator:
    """Validates layer field schemas against expected configuration.
    
    Implements Context7 best practices for field validation:
    - Type compatibility checking using ArcGIS field type mappings
    - Comprehensive validation result reporting
    - Configuration-driven validation rules
    """
    
    def __init__(self, layer_manager: LayerAccessManager, config_loader: ConfigLoader):
        """Initialize field validator.
        
        Args:
            layer_manager: Layer access manager for metadata retrieval
            config_loader: Configuration loader for field validation rules
        """
        self.layer_manager = layer_manager
        self.config_loader = config_loader
        logger.info("FieldValidator initialized")
    
    def validate_layer_schema(self, layer_id: str, expected_fields: Dict[str, str]) -> FieldValidationResult:
        """Validate layer schema against expected field definitions.
        
        Following Context7 best practices for comprehensive field validation
        with detailed error reporting and type compatibility checking.
        
        Args:
            layer_id: ArcGIS layer identifier
            expected_fields: Dictionary of field_name -> expected_type
            
        Returns:
            FieldValidationResult with detailed validation status
        """
        result = FieldValidationResult(layer_id=layer_id, validation_passed=False)
        
        try:
            metadata = self.layer_manager.get_layer_metadata(layer_id)
            if not metadata:
                result.validation_errors.append(f"Could not retrieve metadata for layer {layer_id}")
                return result
            
            # Get actual field names and types (case-insensitive comparison)
            actual_fields = {field.name.lower(): field.field_type for field in metadata.field_definitions}
            expected_fields_lower = {k.lower(): v for k, v in expected_fields.items()}
            
            logger.debug(f"Validating {len(expected_fields_lower)} expected fields against {len(actual_fields)} actual fields")
            
            # Check for missing required fields
            missing = set(expected_fields_lower.keys()) - set(actual_fields.keys())
            result.missing_fields = list(missing)
            
            # Check for type mismatches using Context7 compatibility rules
            for field_name, expected_type in expected_fields_lower.items():
                if field_name in actual_fields:
                    actual_type = actual_fields[field_name]
                    if not self._types_compatible(expected_type, actual_type):
                        result.type_mismatches.append(
                            f"{field_name}: expected {expected_type}, got {actual_type}"
                        )
            
            # Check for unexpected fields (optional - can be informational)
            unexpected = set(actual_fields.keys()) - set(expected_fields_lower.keys())
            # Only report critical unexpected fields (system fields are expected)
            system_fields = {'objectid', 'globalid', 'shape', 'shape_length', 'shape_area'}
            result.unexpected_fields = [f for f in unexpected if f.lower() not in system_fields]
            
            # Determine overall validation result
            result.validation_passed = len(result.missing_fields) == 0 and len(result.type_mismatches) == 0
            
            if not result.validation_passed:
                error_msg = f"Schema validation failed for layer {layer_id}"
                if result.missing_fields:
                    error_msg += f" - Missing fields: {', '.join(result.missing_fields)}"
                if result.type_mismatches:
                    error_msg += f" - Type mismatches: {'; '.join(result.type_mismatches)}"
                result.validation_errors.append(error_msg)
            else:
                logger.info(f"Schema validation passed for layer {layer_id}")
            
            return result
            
        except Exception as e:
            result.validation_errors.append(f"Schema validation error: {e}")
            logger.error(f"Field validation failed for {layer_id}: {e}")
            return result
    
    def _types_compatible(self, expected: str, actual: str) -> bool:
        """Check if field types are compatible.
        
        Implements Context7 recommended type compatibility mappings for ArcGIS field types.
        
        Args:
            expected: Expected field type (simplified)
            actual: Actual ArcGIS field type
            
        Returns:
            True if types are compatible, False otherwise
        """
        # Context7 ArcGIS field type compatibility mappings
        type_mappings = {
            'string': [
                'esriFieldTypeString', 'esriFieldTypeGUID', 'esriFieldTypeGlobalID'
            ],
            'integer': [
                'esriFieldTypeInteger', 'esriFieldTypeSmallInteger', 
                'esriFieldTypeOID', 'esriFieldTypeBigInteger'
            ],
            'double': [
                'esriFieldTypeDouble', 'esriFieldTypeSingle'
            ],
            'date': [
                'esriFieldTypeDate', 'esriFieldTypeDateOnly', 'esriFieldTypeTimeOnly'
            ],
            'geometry': [
                'esriFieldTypeGeometry'
            ],
            'blob': [
                'esriFieldTypeBlob'
            ]
        }
        
        expected_lower = expected.lower()
        
        # Check if expected type matches any compatible ArcGIS types
        for type_group, arcgis_types in type_mappings.items():
            if expected_lower == type_group and actual in arcgis_types:
                return True
        
        # Direct match (case-insensitive)
        if expected.lower() == actual.lower():
            return True
        
        # Log compatibility check for debugging
        logger.debug(f"Type compatibility check: expected '{expected}' vs actual '{actual}' = False")
        return False
    
    def validate_all_configured_layers(self) -> Dict[str, FieldValidationResult]:
        """Validate all layers defined in module configuration.
        
        Following Context7 best practices for comprehensive layer validation
        across all configured spatial layers.
        
        Returns:
            Dictionary mapping layer names to validation results
        """
        results = {}
        
        try:
            # Load module configuration
            module_config = self._load_module_config()
            
            # Validate weed locations layer
            env_config = self.config_loader.load_environment_config()
            environment = env_config.get('current_environment', 'development')
            weed_layer_id = env_config.get(environment, {}).get('weed_locations_layer_id')
            
            if weed_layer_id:
                expected_fields = module_config.get('validation', {}).get('field_types', {})
                if expected_fields:
                    results['weed_locations'] = self.validate_layer_schema(weed_layer_id, expected_fields)
                    logger.info(f"Validated weed locations layer: {results['weed_locations'].validation_passed}")
                else:
                    logger.warning("No field type validation configured for weed locations layer")
            
            # Validate area layers (region, district)
            area_layers = module_config.get('area_layers', {})
            for area_type, area_config in area_layers.items():
                layer_id = area_config.get('layer_id')
                if layer_id:
                    # Use expected fields from configuration or defaults
                    expected_fields = area_config.get('expected_fields', {
                        area_config.get('source_code_field', 'CODE'): 'string',
                        'OBJECTID': 'integer',
                        'GlobalID': 'string',
                        'Shape': 'geometry'
                    })
                    results[area_type] = self.validate_layer_schema(layer_id, expected_fields)
                    logger.info(f"Validated {area_type} layer: {results[area_type].validation_passed}")
            
            # Summary logging
            total_layers = len(results)
            passed_layers = sum(1 for result in results.values() if result.validation_passed)
            logger.info(f"Layer validation summary: {passed_layers}/{total_layers} layers passed validation")
            
            return results
            
        except Exception as e:
            logger.error(f"Failed to validate configured layers: {e}")
            return {}
    
    def _load_module_config(self) -> Dict:
        """Load module configuration.
        
        Returns:
            Module configuration dictionary
        """
        try:
            config_path = Path("modules/spatial_field_updater/config/field_updater_config.json")
            if not config_path.exists():
                logger.warning(f"Module config not found at {config_path}")
                return {}
                
            with open(config_path) as f:
                config = json.load(f)
                logger.debug("Successfully loaded module configuration")
                return config
                
        except Exception as e:
            logger.error(f"Failed to load module configuration: {e}")
            return {}
    
    def get_field_type_mappings(self) -> Dict[str, List[str]]:
        """Get the field type compatibility mappings.
        
        Returns:
            Dictionary of simplified types to ArcGIS field types
        """
        return {
            'string': ['esriFieldTypeString', 'esriFieldTypeGUID', 'esriFieldTypeGlobalID'],
            'integer': ['esriFieldTypeInteger', 'esriFieldTypeSmallInteger', 'esriFieldTypeOID', 'esriFieldTypeBigInteger'],
            'double': ['esriFieldTypeDouble', 'esriFieldTypeSingle'],
            'date': ['esriFieldTypeDate', 'esriFieldTypeDateOnly', 'esriFieldTypeTimeOnly'],
            'geometry': ['esriFieldTypeGeometry'],
            'blob': ['esriFieldTypeBlob']
        } 