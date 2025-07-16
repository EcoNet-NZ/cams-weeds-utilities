"""
Configuration loader for CAMS Spatial Query Optimization System.

This module provides the ConfigLoader class that handles loading and validating
JSON configuration files for multi-environment deployments.
"""

import json
import os
from pathlib import Path
from typing import Dict, Any, Optional, List, Union
from functools import lru_cache

from ..exceptions import CAMSConfigurationError, CAMSValidationError
from ..utils import get_logger


class ConfigLoader:
    """
    Configuration loader and validator for CAMS system.
    
    This class handles loading environment-specific configuration from JSON files,
    validating required fields, and providing type-safe access to configuration values.
    """
    
    def __init__(self, config_dir: Optional[str] = None):
        """
        Initialize the configuration loader.
        
        Args:
            config_dir: Directory containing configuration files (defaults to 'config/')
        """
        self.logger = get_logger(__name__)
        self.config_dir = Path(config_dir) if config_dir else Path("config")
        self._config_cache: Dict[str, Dict[str, Any]] = {}
    
    @lru_cache(maxsize=2)
    def load_environment_config(self, environment: str) -> Dict[str, Any]:
        """
        Load configuration for a specific environment.
        
        Args:
            environment: Environment name (development/production)
            
        Returns:
            Dictionary containing environment-specific configuration merged with shared config
            
        Raises:
            CAMSConfigurationError: If configuration cannot be loaded or validated
        """
        try:
            env_config_path = self.config_dir / "environment_config.json"
            
            if not env_config_path.exists():
                raise CAMSConfigurationError(
                    f"Environment configuration file not found: {env_config_path}"
                )
            
            with open(env_config_path, 'r') as f:
                config_data = json.load(f)
            
            # Validate structure
            self._validate_environment_config(config_data, environment)
            
            # Extract environment-specific configuration
            env_config = config_data["environments"][environment].copy()
            
            # Merge shared configuration with environment-specific configuration
            if "shared" in config_data:
                shared_config = config_data["shared"]
                
                # Merge shared layers with environment-specific layers
                if "layers" in shared_config and "layers" in env_config:
                    # Start with shared layers and update with environment-specific ones
                    merged_layers = shared_config["layers"].copy()
                    merged_layers.update(env_config["layers"])
                    env_config["layers"] = merged_layers
                elif "layers" in shared_config:
                    # Only shared layers exist
                    env_config["layers"] = shared_config["layers"].copy()
                
                # Add other shared configuration items if needed
                for key, value in shared_config.items():
                    if key != "layers" and key not in env_config:
                        env_config[key] = value
            
            # Add validation metadata
            env_config["_validation"] = config_data.get("validation", {})
            
            self.logger.info(f"Loaded configuration for environment: {environment}")
            return env_config
            
        except json.JSONDecodeError as e:
            raise CAMSConfigurationError(
                f"Invalid JSON in environment configuration: {str(e)}"
            )
        except Exception as e:
            raise CAMSConfigurationError(
                f"Failed to load environment configuration: {str(e)}"
            )
    
    @lru_cache(maxsize=1)
    def load_field_mapping(self) -> Dict[str, Any]:
        """
        Load field mapping configuration.
        
        Returns:
            Dictionary containing field mapping configuration
            
        Raises:
            CAMSConfigurationError: If field mapping cannot be loaded or validated
        """
        try:
            field_mapping_path = self.config_dir / "field_mapping.json"
            
            if not field_mapping_path.exists():
                raise CAMSConfigurationError(
                    f"Field mapping configuration file not found: {field_mapping_path}"
                )
            
            with open(field_mapping_path, 'r') as f:
                mapping_data = json.load(f)
            
            # Validate structure
            self._validate_field_mapping(mapping_data)
            
            self.logger.info("Loaded field mapping configuration")
            return mapping_data
            
        except json.JSONDecodeError as e:
            raise CAMSConfigurationError(
                f"Invalid JSON in field mapping configuration: {str(e)}"
            )
        except Exception as e:
            raise CAMSConfigurationError(
                f"Failed to load field mapping configuration: {str(e)}"
            )
    
    def get_layer_config(self, layer_name: str) -> Dict[str, Any]:
        """
        Get configuration for a specific layer.
        
        Args:
            layer_name: Name of the layer (weed_locations, regions, districts, metadata)
            
        Returns:
            Dictionary containing layer configuration
            
        Raises:
            CAMSConfigurationError: If layer configuration is not found
        """
        field_mapping = self.load_field_mapping()
        
        if layer_name not in field_mapping["layers"]:
            raise CAMSConfigurationError(
                f"Layer '{layer_name}' not found in field mapping configuration"
            )
        
        return field_mapping["layers"][layer_name]
    
    def get_field_name(self, layer_name: str, field_key: str) -> str:
        """
        Get the actual field name for a layer and field key.
        
        Args:
            layer_name: Name of the layer
            field_key: Key for the field (e.g., 'object_id', 'edit_date')
            
        Returns:
            Actual field name from the configuration
            
        Raises:
            CAMSConfigurationError: If field is not found
        """
        layer_config = self.get_layer_config(layer_name)
        
        if field_key not in layer_config["fields"]:
            raise CAMSConfigurationError(
                f"Field '{field_key}' not found in layer '{layer_name}' configuration"
            )
        
        return layer_config["fields"][field_key]["field_name"]
    
    def validate_environment_variables(self, environment: str) -> None:
        """
        Validate that required environment variables are set.
        
        Args:
            environment: Environment name to validate
            
        Raises:
            CAMSValidationError: If required environment variables are missing
        """
        env_config = self.load_environment_config(environment)
        required_vars = env_config.get("_validation", {}).get("required_environment_variables", [])
        
        missing_vars = []
        for var in required_vars:
            if not os.getenv(var):
                missing_vars.append(var)
        
        if missing_vars:
            raise CAMSValidationError(
                f"Missing required environment variables: {', '.join(missing_vars)}"
            )
        
        self.logger.info(f"Environment variables validated for: {environment}")
    
    def _validate_environment_config(self, config_data: Dict[str, Any], environment: str) -> None:
        """
        Validate environment configuration structure.
        
        Args:
            config_data: Configuration data to validate
            environment: Environment name to validate
            
        Raises:
            CAMSValidationError: If configuration is invalid
        """
        # Check for required top-level keys
        if "environments" not in config_data:
            raise CAMSValidationError("Missing 'environments' key in configuration")
        
        # Check if specified environment exists
        if environment not in config_data["environments"]:
            available_envs = list(config_data["environments"].keys())
            raise CAMSValidationError(
                f"Environment '{environment}' not found. Available: {available_envs}"
            )
        
        # Validate environment configuration structure
        env_config = config_data["environments"][environment]
        required_keys = ["arcgis_url", "layers", "logging", "processing"]
        
        for key in required_keys:
            if key not in env_config:
                raise CAMSValidationError(
                    f"Missing required key '{key}' in {environment} configuration"
                )
        
        # Validate that we have all required layers after merging
        required_layers = ["weed_locations", "regions", "districts", "metadata"]
        
        # Get layers from environment config
        env_layers = set(env_config.get("layers", {}).keys())
        
        # Get layers from shared config if it exists
        shared_layers = set()
        if "shared" in config_data and "layers" in config_data["shared"]:
            shared_layers = set(config_data["shared"]["layers"].keys())
        
        # Combine all available layers
        all_layers = env_layers | shared_layers
        
        # Check if all required layers are present
        missing_layers = [layer for layer in required_layers if layer not in all_layers]
        if missing_layers:
            raise CAMSValidationError(
                f"Missing required layers in {environment} configuration (including shared): {missing_layers}"
            )
    
    def _validate_field_mapping(self, mapping_data: Dict[str, Any]) -> None:
        """
        Validate field mapping configuration structure.
        
        Args:
            mapping_data: Field mapping data to validate
            
        Raises:
            CAMSValidationError: If field mapping is invalid
        """
        if "layers" not in mapping_data:
            raise CAMSValidationError("Missing 'layers' key in field mapping")
        
        if "data_types" not in mapping_data:
            raise CAMSValidationError("Missing 'data_types' key in field mapping")
        
        # Validate each layer has required structure
        for layer_name, layer_config in mapping_data["layers"].items():
            if "fields" not in layer_config:
                raise CAMSValidationError(
                    f"Missing 'fields' key in layer '{layer_name}' configuration"
                )
            
            if "validation" not in layer_config:
                raise CAMSValidationError(
                    f"Missing 'validation' key in layer '{layer_name}' configuration"
                )
            
            # Validate each field has required structure
            for field_key, field_config in layer_config["fields"].items():
                required_field_keys = ["field_name", "data_type", "required"]
                
                for key in required_field_keys:
                    if key not in field_config:
                        raise CAMSValidationError(
                            f"Missing required key '{key}' in field '{field_key}' "
                            f"of layer '{layer_name}'"
                        )
    
    def clear_cache(self) -> None:
        """Clear the configuration cache."""
        self._config_cache.clear()
        self.load_environment_config.cache_clear()
        self.load_field_mapping.cache_clear()
        self.logger.info("Configuration cache cleared") 