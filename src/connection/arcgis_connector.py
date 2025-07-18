"""
ArcGIS connector for CAMS Spatial Query Optimization System.

This module provides basic ArcGIS connection functionality with retry logic
and timeout handling for development environment.
"""

from typing import Optional, Dict, Any
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from func_timeout import func_timeout, FunctionTimedOut
from arcgis.gis import GIS

from .auth_handler import AuthHandler
from ..config import ConfigLoader
from ..exceptions import CAMSConnectionError, CAMSAuthenticationError
from ..utils import get_logger

logger = get_logger(__name__)


class ArcGISConnector:
    """
    Basic ArcGIS connection manager with retry logic and timeout handling.
    
    This class handles connection establishment to ArcGIS Online for the development
    environment with basic error handling and validation.
    """
    
    def __init__(self, config_loader: ConfigLoader):
        """
        Initialize the ArcGIS connector.
        
        Args:
            config_loader: ConfigLoader instance for accessing configuration
        """
        self.config_loader = config_loader
        self.auth_handler = AuthHandler(config_loader)
        self._gis: Optional[GIS] = None
        logger.debug("ArcGISConnector initialized")
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        retry=retry_if_exception_type(ConnectionError)
    )
    def connect(self) -> GIS:
        """
        Establish connection to ArcGIS Online with retry logic.
        
        Returns:
            GIS: Connected GIS instance
            
        Raises:
            CAMSConnectionError: If connection fails after retries
            CAMSAuthenticationError: If authentication fails
        """
        try:
            # Get credentials from auth handler
            url, username, password = self.auth_handler.get_dev_credentials()
            
            logger.info(f"Attempting connection to ArcGIS at {url}")
            
            # Use timeout to prevent hanging connections
            def _connect_with_timeout():
                return GIS(url, username, password)
            
            # 30 second timeout for connection
            gis = func_timeout(30, _connect_with_timeout)
            
            # Basic connection validation
            self._validate_connection(gis)
            
            self._gis = gis
            logger.info(f"Successfully connected to {gis.properties.portalHostname}")
            return gis
            
        except FunctionTimedOut:
            raise CAMSConnectionError("Connection timeout - ArcGIS service may be unavailable")
        except CAMSAuthenticationError:
            # Re-raise authentication errors as-is
            raise
        except Exception as e:
            error_msg = f"Failed to connect to ArcGIS: {str(e)}"
            logger.error(error_msg)
            raise CAMSConnectionError(error_msg)
    
    def _validate_connection(self, gis: GIS) -> None:
        """
        Validate the GIS connection is working.
        
        Args:
            gis: GIS instance to validate
            
        Raises:
            CAMSConnectionError: If validation fails
        """
        try:
            # Basic validation - check we can access portal properties
            portal_name = gis.properties.portalName
            if not portal_name:
                raise CAMSConnectionError("Unable to access portal properties")
            
            logger.debug(f"Connection validation passed for portal: {portal_name}")
            
        except Exception as e:
            raise CAMSConnectionError(f"Connection validation failed: {str(e)}")
    
    def test_layer_access(self) -> Dict[str, bool]:
        """
        Test access to configured development layers.
        
        Returns:
            Dictionary mapping layer names to accessibility status
            
        Raises:
            CAMSConnectionError: If not connected or test fails
        """
        if not self._gis:
            raise CAMSConnectionError("Not connected to ArcGIS - call connect() first")
        
        try:
            env_config = self.config_loader.load_environment_config('development')
            layers = env_config.get('layers', {})
            
            # Add shared layers
            shared_config = env_config.get('shared', {})
            if 'layers' in shared_config:
                layers.update(shared_config['layers'])
            
            results = {}
            
            for layer_name, layer_id in layers.items():
                try:
                    # Try to get the layer item
                    item = self._gis.content.get(layer_id)
                    if item:
                        results[layer_name] = True
                        logger.debug(f"Layer {layer_name} ({layer_id}) is accessible")
                    else:
                        results[layer_name] = False
                        logger.warning(f"Layer {layer_name} ({layer_id}) not found")
                except Exception as e:
                    results[layer_name] = False
                    logger.warning(f"Layer {layer_name} ({layer_id}) access failed: {str(e)}")
            
            accessible_count = sum(results.values())
            total_count = len(results)
            logger.info(f"Layer access test: {accessible_count}/{total_count} layers accessible")
            
            return results
            
        except Exception as e:
            error_msg = f"Layer access test failed: {str(e)}"
            logger.error(error_msg)
            raise CAMSConnectionError(error_msg)
    
    def get_connection(self) -> Optional[GIS]:
        """
        Get the current GIS connection.
        
        Returns:
            GIS instance if connected, None otherwise
        """
        return self._gis
    
    def is_connected(self) -> bool:
        """
        Check if currently connected to ArcGIS.
        
        Returns:
            True if connected, False otherwise
        """
        return self._gis is not None
    
    def disconnect(self) -> None:
        """
        Disconnect from ArcGIS and clean up resources.
        """
        if self._gis:
            self._gis = None
            logger.info("Disconnected from ArcGIS")
        
        # Clear credentials cache for security
        self.auth_handler.clear_credentials_cache()
        logger.debug("Cleaned up connection resources") 