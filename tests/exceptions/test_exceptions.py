"""
Unit tests for custom exceptions module.

This module contains tests for the custom exception classes
and their context handling.
"""

import pytest
from src.exceptions import (
    CAMSBaseException,
    CAMSConfigurationError,
    CAMSValidationError,
    CAMSConnectionError,
    CAMSProcessingError,
)


class TestCAMSBaseException:
    """Test suite for CAMSBaseException class."""
    
    def test_base_exception_without_context(self):
        """Test CAMSBaseException without context."""
        exception = CAMSBaseException("Test error message")
        
        assert str(exception) == "Test error message"
        assert exception.message == "Test error message"
        assert exception.context == {}
    
    def test_base_exception_with_context(self):
        """Test CAMSBaseException with context."""
        context = {"layer": "weed_locations", "field": "OBJECTID"}
        exception = CAMSBaseException("Test error message", context)
        
        assert exception.message == "Test error message"
        assert exception.context == context
        assert "layer=weed_locations" in str(exception)
        assert "field=OBJECTID" in str(exception)
    
    def test_base_exception_with_empty_context(self):
        """Test CAMSBaseException with empty context."""
        exception = CAMSBaseException("Test error message", {})
        
        assert str(exception) == "Test error message"
        assert exception.context == {}
    
    def test_base_exception_with_none_context(self):
        """Test CAMSBaseException with None context."""
        exception = CAMSBaseException("Test error message", None)
        
        assert str(exception) == "Test error message"
        assert exception.context == {}
    
    def test_base_exception_context_string_representation(self):
        """Test string representation with various context types."""
        context = {
            "string_value": "test",
            "int_value": 42,
            "bool_value": True,
            "none_value": None
        }
        exception = CAMSBaseException("Test error", context)
        
        error_str = str(exception)
        assert "string_value=test" in error_str
        assert "int_value=42" in error_str
        assert "bool_value=True" in error_str
        assert "none_value=None" in error_str


class TestCAMSConfigurationError:
    """Test suite for CAMSConfigurationError class."""
    
    def test_configuration_error_inheritance(self):
        """Test that CAMSConfigurationError inherits from CAMSBaseException."""
        exception = CAMSConfigurationError("Configuration error")
        
        assert isinstance(exception, CAMSBaseException)
        assert isinstance(exception, Exception)
    
    def test_configuration_error_with_context(self):
        """Test CAMSConfigurationError with context."""
        context = {"config_file": "environment_config.json", "environment": "development"}
        exception = CAMSConfigurationError("Invalid configuration", context)
        
        assert exception.message == "Invalid configuration"
        assert exception.context == context
        assert "config_file=environment_config.json" in str(exception)
    
    def test_configuration_error_can_be_raised(self):
        """Test that CAMSConfigurationError can be raised and caught."""
        with pytest.raises(CAMSConfigurationError) as exc_info:
            raise CAMSConfigurationError("Test configuration error")
        
        assert str(exc_info.value) == "Test configuration error"
    
    def test_configuration_error_can_be_caught_as_base_exception(self):
        """Test that CAMSConfigurationError can be caught as CAMSBaseException."""
        with pytest.raises(CAMSBaseException) as exc_info:
            raise CAMSConfigurationError("Test configuration error")
        
        assert isinstance(exc_info.value, CAMSConfigurationError)


class TestCAMSValidationError:
    """Test suite for CAMSValidationError class."""
    
    def test_validation_error_inheritance(self):
        """Test that CAMSValidationError inherits from CAMSBaseException."""
        exception = CAMSValidationError("Validation error")
        
        assert isinstance(exception, CAMSBaseException)
        assert isinstance(exception, Exception)
    
    def test_validation_error_with_context(self):
        """Test CAMSValidationError with context."""
        context = {"field": "RegionCode", "value": "invalid", "expected": "string"}
        exception = CAMSValidationError("Invalid field value", context)
        
        assert exception.message == "Invalid field value"
        assert exception.context == context
        assert "field=RegionCode" in str(exception)
    
    def test_validation_error_can_be_raised(self):
        """Test that CAMSValidationError can be raised and caught."""
        with pytest.raises(CAMSValidationError) as exc_info:
            raise CAMSValidationError("Test validation error")
        
        assert str(exc_info.value) == "Test validation error"


class TestCAMSConnectionError:
    """Test suite for CAMSConnectionError class."""
    
    def test_connection_error_inheritance(self):
        """Test that CAMSConnectionError inherits from CAMSBaseException."""
        exception = CAMSConnectionError("Connection error")
        
        assert isinstance(exception, CAMSBaseException)
        assert isinstance(exception, Exception)
    
    def test_connection_error_with_context(self):
        """Test CAMSConnectionError with context."""
        context = {"url": "https://test.arcgis.com", "status_code": 401}
        exception = CAMSConnectionError("Authentication failed", context)
        
        assert exception.message == "Authentication failed"
        assert exception.context == context
        assert "url=https://test.arcgis.com" in str(exception)
        assert "status_code=401" in str(exception)
    
    def test_connection_error_can_be_raised(self):
        """Test that CAMSConnectionError can be raised and caught."""
        with pytest.raises(CAMSConnectionError) as exc_info:
            raise CAMSConnectionError("Test connection error")
        
        assert str(exc_info.value) == "Test connection error"


class TestCAMSProcessingError:
    """Test suite for CAMSProcessingError class."""
    
    def test_processing_error_inheritance(self):
        """Test that CAMSProcessingError inherits from CAMSBaseException."""
        exception = CAMSProcessingError("Processing error")
        
        assert isinstance(exception, CAMSBaseException)
        assert isinstance(exception, Exception)
    
    def test_processing_error_with_context(self):
        """Test CAMSProcessingError with context."""
        context = {"operation": "spatial_query", "layer": "weed_locations", "record_count": 1500}
        exception = CAMSProcessingError("Spatial query failed", context)
        
        assert exception.message == "Spatial query failed"
        assert exception.context == context
        assert "operation=spatial_query" in str(exception)
        assert "layer=weed_locations" in str(exception)
        assert "record_count=1500" in str(exception)
    
    def test_processing_error_can_be_raised(self):
        """Test that CAMSProcessingError can be raised and caught."""
        with pytest.raises(CAMSProcessingError) as exc_info:
            raise CAMSProcessingError("Test processing error")
        
        assert str(exc_info.value) == "Test processing error"


class TestExceptionInteraction:
    """Test suite for exception interaction and inheritance."""
    
    def test_all_exceptions_inherit_from_base(self):
        """Test that all custom exceptions inherit from CAMSBaseException."""
        exceptions = [
            CAMSConfigurationError("test"),
            CAMSValidationError("test"),
            CAMSConnectionError("test"),
            CAMSProcessingError("test"),
        ]
        
        for exception in exceptions:
            assert isinstance(exception, CAMSBaseException)
            assert isinstance(exception, Exception)
    
    def test_exception_hierarchy_catching(self):
        """Test that exceptions can be caught at different levels."""
        # Test catching specific exception
        with pytest.raises(CAMSConfigurationError):
            raise CAMSConfigurationError("specific error")
        
        # Test catching as base exception
        with pytest.raises(CAMSBaseException):
            raise CAMSConfigurationError("base error")
        
        # Test catching as generic exception
        with pytest.raises(Exception):
            raise CAMSConfigurationError("generic error")
    
    def test_exception_chaining(self):
        """Test exception chaining with context."""
        original_error = ValueError("Original error")
        
        try:
            try:
                raise original_error
            except ValueError as e:
                context = {"original_error": str(e)}
                raise CAMSProcessingError("Processing failed", context) from e
        except CAMSProcessingError as chained_error:
            # Verify the chained exception has the correct properties
            assert chained_error.message == "Processing failed"
            assert chained_error.context["original_error"] == "Original error"
            assert chained_error.__cause__ is original_error
    
    def test_context_preservation_across_exception_types(self):
        """Test that context is preserved across different exception types."""
        base_context = {"module": "test", "function": "test_function"}
        
        exceptions = [
            CAMSConfigurationError("config error", base_context),
            CAMSValidationError("validation error", base_context),
            CAMSConnectionError("connection error", base_context),
            CAMSProcessingError("processing error", base_context),
        ]
        
        for exception in exceptions:
            assert exception.context == base_context
            assert "module=test" in str(exception)
            assert "function=test_function" in str(exception) 