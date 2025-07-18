"""
Connection tester for CAMS Spatial Query Optimization System.

This module provides basic connectivity and layer access testing.
"""

from typing import Dict, Any
from .arcgis_connector import ArcGISConnector
from ..config import ConfigLoader
from ..exceptions import CAMSConnectionError
from ..utils import get_logger

logger = get_logger(__name__)


class ConnectionTester:
    """Basic connection tester for ArcGIS connectivity."""
    
    def __init__(self, config_loader: ConfigLoader):
        """Initialize the connection tester."""
        self.config_loader = config_loader
        self.connector = ArcGISConnector(config_loader)
        logger.debug("ConnectionTester initialized")
    
    def test_connection(self) -> Dict[str, Any]:
        """
        Test basic ArcGIS connection and layer access.
        
        Returns:
            Dictionary with test results
        """
        results = {
            'connection': False,
            'layer_access': {},
            'errors': []
        }
        
        try:
            # Test connection
            logger.info("Testing ArcGIS connection...")
            gis = self.connector.connect()
            results['connection'] = True
            logger.info("Connection test passed")
            
            # Test layer access
            logger.info("Testing layer access...")
            layer_results = self.connector.test_layer_access()
            results['layer_access'] = layer_results
            
            accessible_count = sum(layer_results.values())
            total_count = len(layer_results)
            logger.info(f"Layer access test: {accessible_count}/{total_count} layers accessible")
            
        except Exception as e:
            error_msg = f"Connection test failed: {str(e)}"
            results['errors'].append(error_msg)
            logger.error(error_msg)
        
        finally:
            # Clean up connection
            self.connector.disconnect()
        
        return results 