"""
Environment validator for CAMS Spatial Query Optimization System.

This module provides basic validation for development environment configuration.
"""

import os
from typing import Dict, Any, List
from ..config import ConfigLoader
from ..exceptions import CAMSValidationError
from ..utils import get_logger

logger = get_logger(__name__)


class EnvironmentValidator:
    """Basic environment validator for development configuration."""
    
    def __init__(self, config_loader: ConfigLoader):
        """Initialize the environment validator."""
        self.config_loader = config_loader
        logger.debug("EnvironmentValidator initialized")
    
    def validate_dev_environment(self) -> Dict[str, Any]:
        """
        Validate development environment configuration.
        
        Returns:
            Dictionary with validation results
            
        Raises:
            CAMSValidationError: If validation fails
        """
        results = {
            'environment_variables': False,
            'config_structure': False,
            'layer_ids': False
        }
        
        try:
            # Check environment variables
            required_vars = ['ARCGIS_DEV_USERNAME', 'ARCGIS_DEV_PASSWORD']
            missing_vars = [var for var in required_vars if not os.getenv(var)]
            
            if missing_vars:
                logger.warning(f"Missing environment variables: {missing_vars}")
            else:
                results['environment_variables'] = True
                logger.debug("Environment variables validation passed")
            
            # Check config structure
            env_config = self.config_loader.load_environment_config('development')
            if env_config.get('arcgis_url') and env_config.get('layers'):
                results['config_structure'] = True
                logger.debug("Configuration structure validation passed")
            
            # Check layer IDs exist
            layers = env_config.get('layers', {})
            if layers:
                results['layer_ids'] = True
                logger.debug(f"Found {len(layers)} layer configurations")
            
            passed_count = sum(results.values())
            logger.info(f"Environment validation: {passed_count}/3 checks passed")
            
            return results
            
        except Exception as e:
            error_msg = f"Environment validation failed: {str(e)}"
            logger.error(error_msg)
            raise CAMSValidationError(error_msg) 