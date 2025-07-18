"""
Authentication handler for ArcGIS connections.

This module provides secure authentication handling for ArcGIS Online connections
using username/password authentication with environment variable support.
"""

import os
from typing import Optional, Tuple, Dict, Any
from ..config import ConfigLoader
from ..exceptions import CAMSAuthenticationError, CAMSConfigurationError
from ..utils import get_logger

logger = get_logger(__name__)


class AuthHandler:
    """
    Handles authentication credentials for ArcGIS connections.
    
    This class manages secure loading and validation of username/password credentials
    from environment variables, ensuring no credential exposure in logs.
    """
    
    def __init__(self, config_loader: ConfigLoader):
        """
        Initialize the authentication handler.
        
        Args:
            config_loader: ConfigLoader instance for accessing configuration
            
        Raises:
            CAMSConfigurationError: If configuration is invalid
        """
        self.config_loader = config_loader
        self._credentials_cache: Optional[Dict[str, str]] = None
        logger.debug("AuthHandler initialized")
    
    def get_dev_credentials(self) -> Tuple[str, str, str]:
        """
        Get development environment credentials from environment variables.
        
        Returns:
            Tuple of (url, username, password) for development environment
            
        Raises:
            CAMSAuthenticationError: If credentials are missing or invalid
        """
        try:
            # Get ArcGIS URL from config
            env_config = self.config_loader.load_environment_config('development')
            arcgis_url = env_config.get('arcgis_url')
            if not arcgis_url:
                raise CAMSAuthenticationError("ArcGIS URL not found in development configuration")
            
            # Get credentials from environment variables
            username = os.getenv('ARCGIS_DEV_USERNAME')
            password = os.getenv('ARCGIS_DEV_PASSWORD')
            
            if not username:
                raise CAMSAuthenticationError("ARCGIS_DEV_USERNAME environment variable not set")
            
            if not password:
                raise CAMSAuthenticationError("ARCGIS_DEV_PASSWORD environment variable not set")
            
            # Basic credential validation
            self._validate_credentials(username, password)
            
            logger.info("Successfully loaded development credentials from environment variables")
            return arcgis_url, username, password
            
        except Exception as e:
            if isinstance(e, CAMSAuthenticationError):
                raise
            logger.error("Failed to load development credentials")
            raise CAMSAuthenticationError(f"Error loading development credentials: {str(e)}")
    
    def _validate_credentials(self, username: str, password: str) -> None:
        """
        Validate credential basic requirements.
        
        Args:
            username: Username to validate
            password: Password to validate
            
        Raises:
            CAMSAuthenticationError: If credentials are invalid
        """
        if not username or len(username.strip()) == 0:
            raise CAMSAuthenticationError("Username cannot be empty")
        
        if not password or len(password.strip()) == 0:
            raise CAMSAuthenticationError("Password cannot be empty")
        
        logger.debug("Credential validation passed")
    
    def validate_environment_variables(self) -> Dict[str, bool]:
        """
        Validate that required environment variables are set.
        
        Returns:
            Dictionary indicating which environment variables are set
        """
        required_vars = ['ARCGIS_DEV_USERNAME', 'ARCGIS_DEV_PASSWORD']
        validation_results = {}
        
        for var in required_vars:
            is_set = bool(os.getenv(var))
            validation_results[var] = is_set
            
            # Log without exposing values
            if is_set:
                logger.debug(f"Environment variable {var} is set")
            else:
                logger.warning(f"Environment variable {var} is not set")
        
        return validation_results
    
    def get_required_environment_variables(self) -> list[str]:
        """
        Get list of required environment variables for authentication.
        
        Returns:
            List of required environment variable names
        """
        return ['ARCGIS_DEV_USERNAME', 'ARCGIS_DEV_PASSWORD']
    
    def clear_credentials_cache(self) -> None:
        """Clear any cached credentials for security."""
        if self._credentials_cache:
            # Overwrite sensitive data
            for key in self._credentials_cache:
                self._credentials_cache[key] = "CLEARED"
            self._credentials_cache = None
            logger.debug("Credentials cache cleared") 