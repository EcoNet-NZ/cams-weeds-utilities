"""
Tests for AuthHandler class.

This module tests authentication handling functionality including credential
loading, validation, and security features.
"""

import os
import pytest
from unittest.mock import Mock, patch
from src.connection.auth_handler import AuthHandler
from src.config import ConfigLoader
from src.exceptions import CAMSAuthenticationError, CAMSConfigurationError


class TestAuthHandler:
    """Test cases for AuthHandler class."""
    
    @pytest.fixture
    def mock_config_loader(self):
        """Create a mock ConfigLoader for testing."""
        mock_loader = Mock()
        mock_loader.load_environment_config.return_value = {
            'arcgis_url': "https://econethub.maps.arcgis.com"
        }
        return mock_loader
    
    @pytest.fixture
    def auth_handler(self, mock_config_loader):
        """Create an AuthHandler instance for testing."""
        return AuthHandler(mock_config_loader)
    
    def test_init_success(self, mock_config_loader):
        """Test successful AuthHandler initialization."""
        handler = AuthHandler(mock_config_loader)
        assert handler.config_loader == mock_config_loader
        assert handler._credentials_cache is None
    
    @patch.dict(os.environ, {
        'ARCGIS_DEV_USERNAME': 'test@example.com',
        'ARCGIS_DEV_PASSWORD': 'validpassword123'
    })
    def test_get_dev_credentials_success(self, auth_handler):
        """Test successful retrieval of development credentials."""
        url, username, password = auth_handler.get_dev_credentials()
        
        assert url == "https://econethub.maps.arcgis.com"
        assert username == "test@example.com"
        assert password == "validpassword123"
    
    @patch.dict(os.environ, {}, clear=True)
    def test_get_dev_credentials_missing_username(self, auth_handler):
        """Test error when ARCGIS_DEV_USERNAME is missing."""
        with pytest.raises(CAMSAuthenticationError) as exc_info:
            auth_handler.get_dev_credentials()
        
        assert "ARCGIS_DEV_USERNAME environment variable not set" in str(exc_info.value)
    
    @patch.dict(os.environ, {
        'ARCGIS_DEV_USERNAME': 'test@example.com'
    })
    def test_get_dev_credentials_missing_password(self, auth_handler):
        """Test error when ARCGIS_DEV_PASSWORD is missing."""
        with pytest.raises(CAMSAuthenticationError) as exc_info:
            auth_handler.get_dev_credentials()
        
        assert "ARCGIS_DEV_PASSWORD environment variable not set" in str(exc_info.value)
    

    
    def test_get_dev_credentials_no_arcgis_url(self, auth_handler):
        """Test error when ArcGIS URL is not found in config."""
        auth_handler.config_loader.load_environment_config.return_value = {}
        
        with pytest.raises(CAMSAuthenticationError) as exc_info:
            auth_handler.get_dev_credentials()
        
        assert "ArcGIS URL not found in development configuration" in str(exc_info.value)
    
    def test_validate_credentials_empty_username(self, auth_handler):
        """Test validation error for empty username."""
        with pytest.raises(CAMSAuthenticationError) as exc_info:
            auth_handler._validate_credentials("", "validpassword123")
        
        assert "Username cannot be empty" in str(exc_info.value)
    
    def test_validate_credentials_empty_password(self, auth_handler):
        """Test validation error for empty password."""
        with pytest.raises(CAMSAuthenticationError) as exc_info:
            auth_handler._validate_credentials("test@example.com", "")
        
        assert "Password cannot be empty" in str(exc_info.value)
    
    def test_validate_credentials_whitespace_username(self, auth_handler):
        """Test validation error for whitespace-only username."""
        with pytest.raises(CAMSAuthenticationError) as exc_info:
            auth_handler._validate_credentials("   ", "validpassword123")
        
        assert "Username cannot be empty" in str(exc_info.value)
    
    def test_validate_credentials_whitespace_password(self, auth_handler):
        """Test validation error for whitespace-only password."""
        with pytest.raises(CAMSAuthenticationError) as exc_info:
            auth_handler._validate_credentials("test@example.com", "   ")
        
        assert "Password cannot be empty" in str(exc_info.value)
    
    def test_validate_credentials_success(self, auth_handler):
        """Test successful credential validation."""
        # Should not raise exception
        auth_handler._validate_credentials("testuser", "password123")
    
    @patch.dict(os.environ, {
        'ARCGIS_DEV_USERNAME': 'test@example.com',
        'ARCGIS_DEV_PASSWORD': 'validpassword123'
    })
    def test_validate_environment_variables_all_set(self, auth_handler):
        """Test validation when all environment variables are set."""
        results = auth_handler.validate_environment_variables()
        
        assert results['ARCGIS_DEV_USERNAME'] is True
        assert results['ARCGIS_DEV_PASSWORD'] is True
    
    @patch.dict(os.environ, {}, clear=True)
    def test_validate_environment_variables_none_set(self, auth_handler):
        """Test validation when no environment variables are set."""
        results = auth_handler.validate_environment_variables()
        
        assert results['ARCGIS_DEV_USERNAME'] is False
        assert results['ARCGIS_DEV_PASSWORD'] is False
    
    @patch.dict(os.environ, {
        'ARCGIS_DEV_USERNAME': 'test@example.com'
    })
    def test_validate_environment_variables_partial_set(self, auth_handler):
        """Test validation when only some environment variables are set."""
        results = auth_handler.validate_environment_variables()
        
        assert results['ARCGIS_DEV_USERNAME'] is True
        assert results['ARCGIS_DEV_PASSWORD'] is False
    
    def test_get_required_environment_variables(self, auth_handler):
        """Test getting list of required environment variables."""
        required_vars = auth_handler.get_required_environment_variables()
        
        expected_vars = ['ARCGIS_DEV_USERNAME', 'ARCGIS_DEV_PASSWORD']
        assert required_vars == expected_vars
    
    def test_clear_credentials_cache_empty(self, auth_handler):
        """Test clearing credentials cache when it's empty."""
        # Should not raise exception
        auth_handler.clear_credentials_cache()
        assert auth_handler._credentials_cache is None
    
    def test_clear_credentials_cache_with_data(self, auth_handler):
        """Test clearing credentials cache when it contains data."""
        # Simulate cached data
        auth_handler._credentials_cache = {
            'username': 'test@example.com',
            'password': 'secret123'
        }
        
        auth_handler.clear_credentials_cache()
        assert auth_handler._credentials_cache is None 