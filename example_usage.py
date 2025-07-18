#!/usr/bin/env python3
"""
Example usage of the CAMS Spatial Query Optimization System foundation components.

This script demonstrates how to use the ConfigLoader, logging setup, and exception handling
components that form the foundation of the CAMS system.
"""

import os
import sys
from pathlib import Path

# Add src directory to path for imports
sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.config import ConfigLoader
from src.exceptions import CAMSConfigurationError, CAMSValidationError
from src.utils import setup_logging, get_logger, log_performance


def main():
    """Main function demonstrating the foundation components."""
    print("CAMS Spatial Query Optimization System - Foundation Demo")
    print("=" * 60)
    
    # 1. Setup logging
    print("\n1. Setting up logging...")
    setup_logging(environment="development", log_level="INFO")
    logger = get_logger(__name__)
    logger.info("Logging system initialized successfully")
    
    # 2. Load configuration
    print("\n2. Loading configuration...")
    config_loader = ConfigLoader()
    
    try:
        # Load environment configuration
        dev_config = config_loader.load_environment_config("development")
        logger.info(f"Loaded development configuration: {dev_config['arcgis_url']}")
        
        # Load field mapping
        field_mapping = config_loader.load_field_mapping()
        logger.info(f"Loaded field mapping for {len(field_mapping['layers'])} layers")
        
        # Demonstrate field name lookup
        weed_object_id_field = config_loader.get_field_name("weed_locations", "object_id")
        logger.info(f"WeedLocations ObjectID field name: {weed_object_id_field}")
        
        # Demonstrate layer configuration
        weed_config = config_loader.get_layer_config("weed_locations")
        logger.info(f"WeedLocations layer has {len(weed_config['fields'])} fields")
        
    except CAMSConfigurationError as e:
        logger.error(f"Configuration error: {e}")
        print(f"Configuration error: {e}")
    except CAMSValidationError as e:
        logger.error(f"Validation error: {e}")
        print(f"Validation error: {e}")
    
    # 3. Demonstrate performance logging
    print("\n3. Demonstrating performance logging...")
    
    @log_performance
    def sample_processing_function():
        """Sample function to demonstrate performance logging."""
        import time
        logger.info("Performing sample processing...")
        time.sleep(0.1)  # Simulate some work
        return "Processing completed successfully"
    
    result = sample_processing_function()
    logger.info(f"Function result: {result}")
    
    # 4. Demonstrate exception handling
    print("\n4. Demonstrating exception handling...")
    
    try:
        # This will raise a configuration error
        config_loader.load_environment_config("nonexistent_environment")
    except CAMSConfigurationError as e:
        logger.error(f"Caught configuration error: {e}")
        print(f"Successfully caught and handled error: {e}")
    
    # 5. Demonstrate environment variable validation
    print("\n5. Demonstrating environment variable validation...")
    
    # Set some test environment variables
    os.environ["ARCGIS_USERNAME"] = "test_user"
    os.environ["ARCGIS_PASSWORD"] = "test_password"
    os.environ["CAMS_ENVIRONMENT"] = "development"
    
    try:
        config_loader.validate_environment_variables("development")
        logger.info("Environment variables validated successfully")
    except CAMSValidationError as e:
        logger.error(f"Environment validation failed: {e}")
        print(f"Environment validation failed: {e}")
    
    # 6. Demonstrate configuration caching
    print("\n6. Demonstrating configuration caching...")
    
    # First load (will hit the file system)
    config1 = config_loader.load_environment_config("development")
    # Second load (will use cache)
    config2 = config_loader.load_environment_config("development")
    
    # Verify it's the same cached object
    if config1 is config2:
        logger.info("Configuration caching is working correctly")
        print("Configuration caching is working correctly")
    else:
        logger.warning("Configuration caching may not be working")
        print("Configuration caching may not be working")
    
    # Clear cache
    config_loader.clear_cache()
    logger.info("Configuration cache cleared")
    
    print("\n" + "=" * 60)
    print("Foundation demo completed successfully!")
    print("All components are working as expected.")


def demo_arcgis_connectivity():
    """Demonstrate ArcGIS connectivity functionality."""
    print("\n=== ArcGIS Connectivity Demo ===")
    
    try:
        from src.connection import (
            ArcGISConnector, 
            EnvironmentValidator, 
            ConnectionTester
        )
        
        # Initialize components
        config_loader = ConfigLoader()
        
        # Validate environment
        print("\n1. Environment Validation:")
        validator = EnvironmentValidator(config_loader)
        validation_results = validator.validate_dev_environment()
        
        for check, passed in validation_results.items():
            status = "✅ PASS" if passed else "❌ FAIL"
            print(f"   {check}: {status}")
        
        # Test connection (if environment variables are set)
        if validation_results.get('environment_variables'):
            print("\n2. Connection Testing:")
            tester = ConnectionTester(config_loader)
            test_results = tester.test_connection()
            
            connection_status = "✅ PASS" if test_results['connection'] else "❌ FAIL"
            print(f"   Connection: {connection_status}")
            
            print(f"   Layer Access:")
            for layer, accessible in test_results['layer_access'].items():
                status = "✅" if accessible else "❌"
                print(f"     {layer}: {status}")
                
            if test_results['errors']:
                print(f"   Errors: {test_results['errors']}")
        else:
            print("\n2. Connection Testing: Skipped (missing environment variables)")
            print("   Set ARCGIS_DEV_USERNAME and ARCGIS_DEV_PASSWORD to test connection")
        
    except Exception as e:
        print(f"ArcGIS connectivity demo failed: {e}")


if __name__ == "__main__":
    main()
    demo_arcgis_connectivity() 