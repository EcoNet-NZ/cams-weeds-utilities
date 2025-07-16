"""
Unit tests for logging setup module.

This module contains tests for logging configuration, formatting,
and performance decorators.
"""

import json
import logging
import tempfile
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
import sys

from src.utils.logging_setup import (
    setup_logging, 
    get_logger, 
    log_performance,
    JSONFormatter
)


class TestJSONFormatter:
    """Test suite for JSONFormatter class."""
    
    def test_json_formatter_basic(self):
        """Test basic JSON formatting."""
        formatter = JSONFormatter(datefmt='%Y-%m-%d %H:%M:%S')
        
        # Create a mock log record
        record = logging.LogRecord(
            name="test.logger",
            level=logging.INFO,
            pathname="/path/to/file.py",
            lineno=42,
            msg="Test message",
            args=(),
            exc_info=None
        )
        record.funcName = "test_function"
        record.module = "test_module"
        
        result = formatter.format(record)
        parsed = json.loads(result)
        
        assert parsed["level"] == "INFO"
        assert parsed["logger"] == "test.logger"
        assert parsed["message"] == "Test message"
        assert parsed["module"] == "test_module"
        assert parsed["function"] == "test_function"
        assert parsed["line"] == 42
        assert "timestamp" in parsed
    
    def test_json_formatter_with_exception(self):
        """Test JSON formatting with exception information."""
        formatter = JSONFormatter()
        
        try:
            raise ValueError("Test exception")
        except ValueError as e:
            record = logging.LogRecord(
                name="test.logger",
                level=logging.ERROR,
                pathname="/path/to/file.py",
                lineno=42,
                msg="Error occurred",
                args=(),
                exc_info=sys.exc_info()
            )
            record.funcName = "test_function"
            record.module = "test_module"
            
            result = formatter.format(record)
            parsed = json.loads(result)
            
            assert parsed["level"] == "ERROR"
            assert parsed["message"] == "Error occurred"
            assert "exception" in parsed
            assert "ValueError" in parsed["exception"]
    
    def test_json_formatter_with_extra_fields(self):
        """Test JSON formatting with extra fields."""
        formatter = JSONFormatter()
        
        record = logging.LogRecord(
            name="test.logger",
            level=logging.INFO,
            pathname="/path/to/file.py",
            lineno=42,
            msg="Test message",
            args=(),
            exc_info=None
        )
        record.funcName = "test_function"
        record.module = "test_module"
        record.custom_field = "custom_value"
        record.request_id = "123456"
        
        result = formatter.format(record)
        parsed = json.loads(result)
        
        assert parsed["custom_field"] == "custom_value"
        assert parsed["request_id"] == "123456"


class TestSetupLogging:
    """Test suite for setup_logging function."""
    
    def setup_method(self):
        """Reset logging configuration before each test."""
        # Clear all existing handlers
        logger = logging.getLogger()
        logger.handlers.clear()
        logger.setLevel(logging.WARNING)
    
    def test_setup_logging_development(self):
        """Test logging setup for development environment."""
        setup_logging(environment="development", log_level="DEBUG")
        
        logger = logging.getLogger()
        assert logger.level == logging.DEBUG
        assert len(logger.handlers) == 1
        
        handler = logger.handlers[0]
        assert isinstance(handler, logging.StreamHandler)
        assert handler.stream is sys.stdout
        assert not isinstance(handler.formatter, JSONFormatter)
    
    def test_setup_logging_production(self):
        """Test logging setup for production environment."""
        setup_logging(environment="production", log_level="INFO")
        
        logger = logging.getLogger()
        assert logger.level == logging.INFO
        assert len(logger.handlers) == 1
        
        handler = logger.handlers[0]
        assert isinstance(handler, logging.StreamHandler)
        assert isinstance(handler.formatter, JSONFormatter)
    
    def test_setup_logging_with_log_dir(self):
        """Test logging setup with log directory."""
        with tempfile.TemporaryDirectory() as temp_dir:
            setup_logging(
                environment="development",
                log_level="INFO",
                log_dir=temp_dir
            )
            
            logger = logging.getLogger()
            assert len(logger.handlers) == 2  # Console + File
            
            # Check file handler exists
            file_handlers = [h for h in logger.handlers if isinstance(h, logging.handlers.RotatingFileHandler)]
            assert len(file_handlers) == 1
            
            # Check log file was created
            log_file = Path(temp_dir) / "cams_development.log"
            assert log_file.exists()
    
    def test_setup_logging_removes_existing_handlers(self):
        """Test that setup_logging removes existing handlers."""
        logger = logging.getLogger()
        
        # Clear existing handlers first
        logger.handlers.clear()
        
        # Add a dummy handler
        dummy_handler = logging.StreamHandler()
        logger.addHandler(dummy_handler)
        assert len(logger.handlers) == 1
        
        # Setup logging should remove existing handlers
        setup_logging(environment="development")
        assert len(logger.handlers) == 1
        assert logger.handlers[0] is not dummy_handler
    
    def test_setup_logging_sets_third_party_levels(self):
        """Test that setup_logging sets appropriate levels for third-party loggers."""
        setup_logging(environment="development", log_level="DEBUG")
        
        assert logging.getLogger("arcgis").level == logging.WARNING
        assert logging.getLogger("urllib3").level == logging.WARNING
        assert logging.getLogger("requests").level == logging.WARNING
    
    def test_setup_logging_invalid_level(self):
        """Test that setup_logging handles invalid log levels."""
        with pytest.raises(AttributeError):
            setup_logging(environment="development", log_level="INVALID")


class TestGetLogger:
    """Test suite for get_logger function."""
    
    def test_get_logger_returns_logger(self):
        """Test that get_logger returns a logger instance."""
        logger = get_logger("test.module")
        assert isinstance(logger, logging.Logger)
        assert logger.name == "test.module"
    
    def test_get_logger_same_name_returns_same_logger(self):
        """Test that get_logger returns the same logger for the same name."""
        logger1 = get_logger("test.module")
        logger2 = get_logger("test.module")
        assert logger1 is logger2


class TestLogPerformance:
    """Test suite for log_performance decorator."""
    
    def test_log_performance_success(self, caplog):
        """Test log_performance decorator with successful function."""
        @log_performance
        def test_function():
            return "success"
        
        with caplog.at_level(logging.INFO):
            result = test_function()
        
        assert result == "success"
        assert "Starting test_function" in caplog.text
        assert "Completed test_function" in caplog.text
    
    def test_log_performance_with_exception(self, caplog):
        """Test log_performance decorator with function that raises exception."""
        @log_performance
        def test_function():
            raise ValueError("Test error")
        
        with caplog.at_level(logging.INFO):
            with pytest.raises(ValueError):
                test_function()
        
        assert "Starting test_function" in caplog.text
        assert "Failed test_function" in caplog.text
        assert "Test error" in caplog.text
    
    def test_log_performance_with_args_and_kwargs(self, caplog):
        """Test log_performance decorator with function arguments."""
        @log_performance
        def test_function(arg1, arg2, kwarg1=None):
            return f"{arg1}-{arg2}-{kwarg1}"
        
        with caplog.at_level(logging.INFO):
            result = test_function("a", "b", kwarg1="c")
        
        assert result == "a-b-c"
        assert "Starting test_function" in caplog.text
        assert "Completed test_function" in caplog.text
    
    def test_log_performance_preserves_metadata(self):
        """Test that log_performance preserves function metadata."""
        @log_performance
        def test_function():
            """Test function docstring."""
            pass
        
        assert test_function.__name__ == "test_function"
        assert test_function.__doc__ == "Test function docstring."


class TestLoggingIntegration:
    """Integration tests for logging components."""
    
    def test_logging_integration_with_config_loader(self):
        """Test logging integration with ConfigLoader."""
        # This would be an integration test that verifies
        # the logging setup works with the ConfigLoader
        setup_logging(environment="development", log_level="DEBUG")
        
        # Import ConfigLoader after logging setup
        from src.config import ConfigLoader
        
        # Create a ConfigLoader instance
        config_loader = ConfigLoader()
        
        # Verify that the ConfigLoader can create log messages
        logger = config_loader.logger
        assert isinstance(logger, logging.Logger)
        assert logger.name == "src.config.config_loader"
    
    def test_json_logging_output_format(self):
        """Test that JSON logging produces parseable output."""
        with tempfile.TemporaryDirectory() as temp_dir:
            setup_logging(
                environment="production",
                log_level="INFO",
                log_dir=temp_dir
            )
            
            logger = get_logger("test.module")
            logger.info("Test message", extra={"request_id": "123", "user_id": "456"})
            
            # Read the log file
            log_file = Path(temp_dir) / "cams_production.log"
            if log_file.exists():
                with open(log_file, 'r') as f:
                    log_content = f.read().strip()
                    if log_content:
                        # Should be valid JSON
                        parsed = json.loads(log_content)
                        assert parsed["message"] == "Test message"
                        assert parsed["request_id"] == "123"
                        assert parsed["user_id"] == "456" 