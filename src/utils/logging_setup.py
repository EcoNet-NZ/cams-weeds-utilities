"""
Logging configuration for CAMS Spatial Query Optimization System.

This module provides centralized logging setup with environment-specific
configuration and structured logging capabilities.
"""

import logging
import logging.handlers
import os
import sys
from pathlib import Path
from typing import Optional, Dict, Any
import json


class JSONFormatter(logging.Formatter):
    """Custom JSON formatter for structured logging."""
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON."""
        log_entry = {
            'timestamp': self.formatTime(record, self.datefmt),
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
            'module': record.module,
            'function': record.funcName,
            'line': record.lineno,
        }
        
        # Add exception information if present
        if record.exc_info:
            log_entry['exception'] = self.formatException(record.exc_info)
        
        # Add extra fields from record
        for key, value in record.__dict__.items():
            if key not in ['name', 'msg', 'args', 'levelname', 'levelno', 'pathname',
                          'filename', 'module', 'exc_info', 'exc_text', 'stack_info',
                          'lineno', 'funcName', 'created', 'msecs', 'relativeCreated',
                          'thread', 'threadName', 'processName', 'process', 'getMessage']:
                log_entry[key] = value
        
        return json.dumps(log_entry)


def setup_logging(environment: str = "development", 
                  log_level: str = "INFO",
                  log_dir: Optional[str] = None) -> None:
    """
    Set up logging configuration for the CAMS system.
    
    Args:
        environment: Environment name (development/production)
        log_level: Logging level (DEBUG/INFO/WARNING/ERROR)
        log_dir: Directory for log files (optional)
    """
    # Create log directory if specified
    if log_dir:
        log_path = Path(log_dir)
        log_path.mkdir(parents=True, exist_ok=True)
    
    # Configure root logger
    logger = logging.getLogger()
    logger.setLevel(getattr(logging, log_level.upper()))
    
    # Remove existing handlers to avoid duplicates
    logger.handlers = []
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    
    if environment == "production":
        # Use JSON formatter for production
        console_handler.setFormatter(JSONFormatter(
            datefmt='%Y-%m-%d %H:%M:%S'
        ))
    else:
        # Use standard formatter for development
        console_handler.setFormatter(logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        ))
    
    logger.addHandler(console_handler)
    
    # File handler (if log directory is specified)
    if log_dir:
        file_handler = logging.handlers.RotatingFileHandler(
            filename=os.path.join(log_dir, f"cams_{environment}.log"),
            maxBytes=10 * 1024 * 1024,  # 10MB
            backupCount=5
        )
        
        if environment == "production":
            file_handler.setFormatter(JSONFormatter(
                datefmt='%Y-%m-%d %H:%M:%S'
            ))
        else:
            file_handler.setFormatter(logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            ))
        
        logger.addHandler(file_handler)
    
    # Set specific logger levels
    logging.getLogger("arcgis").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("requests").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance with the specified name.
    
    Args:
        name: Logger name (typically __name__)
        
    Returns:
        Logger instance
    """
    return logging.getLogger(name)


def log_performance(func):
    """
    Decorator to log function execution time.
    
    Args:
        func: Function to wrap
        
    Returns:
        Wrapped function with performance logging
    """
    import time
    import functools
    
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        logger = get_logger(func.__module__)
        start_time = time.time()
        
        logger.info(f"Starting {func.__name__}")
        try:
            result = func(*args, **kwargs)
            duration = time.time() - start_time
            logger.info(f"Completed {func.__name__} in {duration:.3f}s")
            return result
        except Exception as e:
            duration = time.time() - start_time
            logger.error(f"Failed {func.__name__} after {duration:.3f}s: {str(e)}")
            raise
    
    return wrapper 