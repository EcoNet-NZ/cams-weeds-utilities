"""
Tests for ArcGISConnector class.

This module tests ArcGIS connection functionality including retry logic,
timeout handling, and layer access validation.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from func_timeout import FunctionTimedOut

from src.connection.arcgis_connector import ArcGISConnector
from src.connection.auth_handler import AuthHandler
from src.config import ConfigLoader
from src.exceptions import CAMSConnectionError, CAMSAuthenticationError


class TestArcGISConnector:
    """Test cases for ArcGISConnector class."""
    
    @pytest.fixture
    def mock_config_loader(self):
        """Create a mock ConfigLoader for testing."""
        mock_loader = Mock()
        mock_loader.load_environment_config.return_value = {
            'arcgis_url': "https://econethub.maps.arcgis.com",
            'layers': {
                'weed_locations': 'weed_layer_id',
                'metadata': 'metadata_layer_id'
            }
        }
        return mock_loader
    
    @pytest.fixture
    def mock_auth_handler(self):
        """Create a mock AuthHandler for testing."""
        mock_handler = Mock(spec=AuthHandler)
        mock_handler.get_dev_credentials.return_value = (
            "https://econethub.maps.arcgis.com",
            "testuser",
            "testpass"
        )
        return mock_handler
    
    @pytest.fixture
    def connector(self, mock_config_loader):
        """Create an ArcGISConnector instance for testing."""
        return ArcGISConnector(mock_config_loader)
    
    def test_init_success(self, mock_config_loader):
        """Test successful ArcGISConnector initialization."""
        connector = ArcGISConnector(mock_config_loader)
        assert connector.config_loader == mock_config_loader
        assert connector._gis is None
        assert not connector.is_connected()
    
    @patch('src.connection.arcgis_connector.GIS')
    @patch('src.connection.arcgis_connector.func_timeout')
    def test_connect_success(self, mock_func_timeout, mock_gis_class, connector, mock_auth_handler):
        """Test successful connection to ArcGIS."""
        # Mock GIS instance
        mock_gis = Mock()
        mock_gis.properties.portalHostname = "econethub.maps.arcgis.com"
        mock_gis.properties.portalName = "Test Portal"
        
        # Mock func_timeout to return the GIS instance
        mock_func_timeout.return_value = mock_gis
        
        # Replace auth handler with mock
        connector.auth_handler = mock_auth_handler
        
        # Test connection
        result = connector.connect()
        
        assert result == mock_gis
        assert connector._gis == mock_gis
        assert connector.is_connected()
        
        # Verify auth handler was called
        mock_auth_handler.get_dev_credentials.assert_called_once()
        
        # Verify func_timeout was called with 30 second timeout
        mock_func_timeout.assert_called_once()
        args, kwargs = mock_func_timeout.call_args
        assert args[0] == 30  # timeout value
    
    @patch('src.connection.arcgis_connector.func_timeout')
    def test_connect_timeout(self, mock_func_timeout, connector, mock_auth_handler):
        """Test connection timeout handling."""
        # Mock timeout exception
        mock_func_timeout.side_effect = FunctionTimedOut()
        
        # Replace auth handler with mock
        connector.auth_handler = mock_auth_handler
        
        # Test connection timeout
        with pytest.raises(CAMSConnectionError) as exc_info:
            connector.connect()
        
        assert "Connection timeout" in str(exc_info.value)
    
    @patch('src.connection.arcgis_connector.GIS')
    @patch('src.connection.arcgis_connector.func_timeout')
    def test_connect_authentication_error(self, mock_func_timeout, mock_gis_class, connector, mock_auth_handler):
        """Test authentication error handling."""
        # Mock auth handler to raise authentication error
        mock_auth_handler.get_dev_credentials.side_effect = CAMSAuthenticationError("Invalid credentials")
        
        # Replace auth handler with mock
        connector.auth_handler = mock_auth_handler
        
        # Test authentication error
        with pytest.raises(CAMSAuthenticationError) as exc_info:
            connector.connect()
        
        assert "Invalid credentials" in str(exc_info.value)
    
    @patch('src.connection.arcgis_connector.GIS')
    @patch('src.connection.arcgis_connector.func_timeout')
    def test_connect_validation_failure(self, mock_func_timeout, mock_gis_class, connector, mock_auth_handler):
        """Test connection validation failure."""
        # Mock GIS instance with invalid properties
        mock_gis = Mock()
        mock_gis.properties.portalName = None
        
        # Mock func_timeout to return the GIS instance
        mock_func_timeout.return_value = mock_gis
        
        # Replace auth handler with mock
        connector.auth_handler = mock_auth_handler
        
        # Test validation failure
        with pytest.raises(CAMSConnectionError) as exc_info:
            connector.connect()
        
        assert "Unable to access portal properties" in str(exc_info.value)
    
    @patch('src.connection.arcgis_connector.GIS')
    @patch('src.connection.arcgis_connector.func_timeout')
    def test_connect_generic_error(self, mock_func_timeout, mock_gis_class, connector, mock_auth_handler):
        """Test generic connection error handling."""
        # Mock func_timeout to raise generic exception
        mock_func_timeout.side_effect = Exception("Network error")
        
        # Replace auth handler with mock
        connector.auth_handler = mock_auth_handler
        
        # Test generic error
        with pytest.raises(CAMSConnectionError) as exc_info:
            connector.connect()
        
        assert "Failed to connect to ArcGIS" in str(exc_info.value)
        assert "Network error" in str(exc_info.value)
    
    def test_test_layer_access_not_connected(self, connector):
        """Test layer access test when not connected."""
        with pytest.raises(CAMSConnectionError) as exc_info:
            connector.test_layer_access()
        
        assert "Not connected to ArcGIS" in str(exc_info.value)
    
    def test_test_layer_access_success(self, connector, mock_config_loader):
        """Test successful layer access testing."""
        # Mock connected GIS
        mock_gis = Mock()
        connector._gis = mock_gis
        
        # Mock layer items
        mock_item1 = Mock()
        mock_item2 = Mock()
        mock_gis.content.get.side_effect = [mock_item1, mock_item2]
        
        # Test layer access
        results = connector.test_layer_access()
        
        expected = {
            'weed_locations': True,
            'metadata': True
        }
        assert results == expected
        
        # Verify GIS content.get was called for each layer
        assert mock_gis.content.get.call_count == 2
    
    def test_test_layer_access_partial_failure(self, connector, mock_config_loader):
        """Test layer access testing with some failures."""
        # Mock connected GIS
        mock_gis = Mock()
        connector._gis = mock_gis
        
        # Mock one successful, one failed layer access
        mock_item = Mock()
        mock_gis.content.get.side_effect = [mock_item, None]
        
        # Test layer access
        results = connector.test_layer_access()
        
        expected = {
            'weed_locations': True,
            'metadata': False
        }
        assert results == expected
    
    def test_test_layer_access_with_shared_layers(self, connector):
        """Test layer access testing with shared layers."""
        # Mock config with shared layers
        connector.config_loader.load_environment_config.return_value = {
            'layers': {
                'weed_locations': 'weed_layer_id'
            },
            'shared': {
                'layers': {
                    'regions': 'regions_layer_id',
                    'districts': 'districts_layer_id'
                }
            }
        }
        
        # Mock connected GIS
        mock_gis = Mock()
        connector._gis = mock_gis
        
        # Mock all layers accessible
        mock_item = Mock()
        mock_gis.content.get.return_value = mock_item
        
        # Test layer access
        results = connector.test_layer_access()
        
        expected = {
            'weed_locations': True,
            'regions': True,
            'districts': True
        }
        assert results == expected
        assert mock_gis.content.get.call_count == 3
    
    def test_test_layer_access_exception(self, connector, mock_config_loader):
        """Test layer access testing with exceptions."""
        # Mock connected GIS
        mock_gis = Mock()
        connector._gis = mock_gis
        
        # Mock exception during layer access
        mock_gis.content.get.side_effect = Exception("API error")
        
        # Test layer access with exception
        results = connector.test_layer_access()
        
        expected = {
            'weed_locations': False,
            'metadata': False
        }
        assert results == expected
    
    def test_get_connection_when_connected(self, connector):
        """Test getting connection when connected."""
        mock_gis = Mock()
        connector._gis = mock_gis
        
        result = connector.get_connection()
        assert result == mock_gis
    
    def test_get_connection_when_not_connected(self, connector):
        """Test getting connection when not connected."""
        result = connector.get_connection()
        assert result is None
    
    def test_is_connected_true(self, connector):
        """Test is_connected when connected."""
        connector._gis = Mock()
        assert connector.is_connected() is True
    
    def test_is_connected_false(self, connector):
        """Test is_connected when not connected."""
        assert connector.is_connected() is False
    
    def test_disconnect(self, connector, mock_auth_handler):
        """Test disconnect functionality."""
        # Set up connected state
        mock_gis = Mock()
        connector._gis = mock_gis
        connector.auth_handler = mock_auth_handler
        
        # Test disconnect
        connector.disconnect()
        
        assert connector._gis is None
        assert not connector.is_connected()
        
        # Verify credentials cache was cleared
        mock_auth_handler.clear_credentials_cache.assert_called_once()
    
    def test_disconnect_when_not_connected(self, connector, mock_auth_handler):
        """Test disconnect when not connected."""
        connector.auth_handler = mock_auth_handler
        
        # Test disconnect when not connected
        connector.disconnect()
        
        assert connector._gis is None
        
        # Should still clear credentials cache
        mock_auth_handler.clear_credentials_cache.assert_called_once() 