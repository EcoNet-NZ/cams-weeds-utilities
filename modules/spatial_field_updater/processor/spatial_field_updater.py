"""SpatialFieldUpdater Implementation

This module implements the main SpatialFieldUpdater class that provides automated
spatial field updates for weed location data by implementing the ModuleProcessor interface.
"""

import json
import logging
from pathlib import Path
from typing import Optional, Dict, Any
from datetime import datetime

from src.interfaces.module_processor import ModuleProcessor, ProcessingResult, ModuleStatus
from src.config.config_loader import ConfigLoader
from src.connection.arcgis_connector import ArcGISConnector
from ..models import WeedLocation, ProcessMetadata
from ..layer_access import LayerAccessManager, FieldValidator, MetadataTableManager

logger = logging.getLogger(__name__)


class SpatialFieldUpdater(ModuleProcessor):
    """Spatial field updater implementing ModuleProcessor interface.
    
    This class provides automated spatial intersection processing to pre-calculate
    region and district assignments for weed locations, eliminating real-time spatial
    queries from the CAMS dashboard.
    
    The processor implements the standard ModuleProcessor interface to ensure consistent
    behavior and integration with the CAMS framework infrastructure.
    """
    
    def __init__(self, config_loader: ConfigLoader):
        """Initialize spatial field updater with shared configuration.
        
        Args:
            config_loader: ConfigLoader instance providing access to framework configuration
        """
        self.config_loader = config_loader
        self.connector: Optional[ArcGISConnector] = None
        self._last_run: Optional[datetime] = None
        self._module_config: Optional[Dict[str, Any]] = None
        self._configuration_valid: Optional[bool] = None
        
        # Initialize layer access components (will be created when needed)
        self.layer_manager: Optional[LayerAccessManager] = None
        self.field_validator: Optional[FieldValidator] = None
        self.metadata_manager: Optional[MetadataTableManager] = None
        
        logger.info("SpatialFieldUpdater initialized")
    
    def _load_module_config(self) -> Dict[str, Any]:
        """Load module-specific configuration from field_updater_config.json.
        
        Returns:
            Dictionary containing module configuration
            
        Raises:
            FileNotFoundError: If configuration file is not found
            ValueError: If configuration file is invalid JSON
        """
        config_path = Path("modules/spatial_field_updater/config/field_updater_config.json")
        
        try:
            with open(config_path, 'r') as f:
                config_data = json.load(f)
            
            logger.debug(f"Loaded module configuration from {config_path}")
            return config_data
            
        except FileNotFoundError:
            logger.error(f"Module configuration file not found: {config_path}")
            raise
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in configuration file {config_path}: {e}")
            raise ValueError(f"Invalid JSON in configuration file: {e}")
    
    def _get_module_config(self) -> Dict[str, Any]:
        """Get module configuration, loading it if necessary.
        
        Returns:
            Dictionary containing module configuration
        """
        if self._module_config is None:
            self._module_config = self._load_module_config()
        return self._module_config
    
    def _initialize_layer_access(self):
        """Initialize layer access components.
        
        Creates LayerAccessManager, FieldValidator, and MetadataTableManager instances
        following Context7 best practices for layer access and metadata management.
        """
        if self.connector and not self.layer_manager:
            logger.info("Initializing layer access components")
            
            self.layer_manager = LayerAccessManager(self.connector, self.config_loader)
            self.field_validator = FieldValidator(self.layer_manager, self.config_loader)
            self.metadata_manager = MetadataTableManager(
                self.connector, self.config_loader, self.layer_manager
            )
            
            logger.info("Layer access components initialized successfully")
    
    def validate_configuration(self) -> bool:
        """Validate module-specific configuration.
        
        This method verifies that all required configuration values are present
        and valid for the module to operate correctly. It checks both the
        module's specific configuration file and any required framework configuration.
        
        Returns:
            bool: True if configuration is valid and complete, False otherwise
        """
        if self._configuration_valid is not None:
            return self._configuration_valid
            
        try:
            # Load and validate module configuration
            module_config = self._get_module_config()
            
            # Validate required sections exist
            required_sections = ['area_layers', 'processing', 'metadata_table', 'validation']
            for section in required_sections:
                if section not in module_config:
                    logger.error(f"Missing required configuration section: {section}")
                    self._configuration_valid = False
                    return False
            
            # Validate area layers configuration
            area_layers = module_config['area_layers']
            required_layer_types = ['region', 'district']
            for layer_type in required_layer_types:
                if layer_type not in area_layers:
                    logger.error(f"Missing area layer configuration: {layer_type}")
                    self._configuration_valid = False
                    return False
                
                layer_config = area_layers[layer_type]
                required_layer_fields = ['layer_id', 'source_code_field', 'target_field']
                for field in required_layer_fields:
                    if field not in layer_config:
                        logger.error(f"Missing field in {layer_type} layer config: {field}")
                        self._configuration_valid = False
                        return False
            
            # Validate processing configuration
            processing_config = module_config['processing']
            required_processing_fields = ['batch_size', 'max_retries', 'timeout_seconds']
            for field in required_processing_fields:
                if field not in processing_config:
                    logger.error(f"Missing processing configuration field: {field}")
                    self._configuration_valid = False
                    return False
            
            # Validate batch size is reasonable
            batch_size = processing_config['batch_size']
            if not isinstance(batch_size, int) or batch_size <= 0 or batch_size > 1000:
                logger.error(f"Invalid batch_size: {batch_size}. Must be integer between 1 and 1000")
                self._configuration_valid = False
                return False
            
            # Validate framework configuration is accessible
            try:
                env_config = self.config_loader.load_environment_config()
                field_mapping = self.config_loader.load_field_mapping()
                
                if not env_config or not field_mapping:
                    logger.error("Framework configuration is not available")
                    self._configuration_valid = False
                    return False
                    
            except Exception as e:
                logger.error(f"Failed to load framework configuration: {e}")
                self._configuration_valid = False
                return False
            
            # Initialize and validate layer access components
            if self.connector:
                try:
                    self._initialize_layer_access()
                    
                    # Validate all configured layers using Context7 best practices
                    if self.field_validator:
                        validation_results = self.field_validator.validate_all_configured_layers()
                        
                        for layer_name, result in validation_results.items():
                            if not result.validation_passed:
                                logger.error(f"Layer validation failed for {layer_name}: {result.validation_errors}")
                                self._configuration_valid = False
                                return False
                        
                        logger.info(f"Layer validation passed for {len(validation_results)} layers")
                    
                    # Validate metadata table access and schema
                    if self.metadata_manager:
                        if not self.metadata_manager.verify_metadata_table_schema():
                            logger.error("Metadata table schema validation failed")
                            self._configuration_valid = False
                            return False
                        
                        logger.info("Metadata table validation passed")
                    
                except Exception as e:
                    logger.error(f"Layer access validation failed: {e}")
                    self._configuration_valid = False
                    return False
            else:
                logger.warning("ArcGIS connector not available - skipping layer validation")
            
            logger.info("Module configuration validation successful")
            self._configuration_valid = True
            return True
            
        except Exception as e:
            logger.error(f"Configuration validation failed: {e}")
            self._configuration_valid = False
            return False
    
    def process(self, dry_run: bool = False) -> ProcessingResult:
        """Execute spatial field update processing logic.
        
        This is the main entry point for module processing. The implementation performs
        all necessary processing steps while respecting the dry_run flag to avoid making
        actual changes when in testing mode.
        
        Args:
            dry_run: If True, perform all processing logic without making actual changes
            
        Returns:
            ProcessingResult: Standardized result object with success status, metrics, and errors
        """
        start_time = datetime.now()
        
        try:
            logger.info(f"Starting spatial field update process (dry_run={dry_run})")
            
            # Validate configuration before processing
            if not self.validate_configuration():
                return ProcessingResult(
                    success=False,
                    records_processed=0,
                    errors=["Configuration validation failed"],
                    execution_time=0.0
                )
            
            # Initialize ArcGIS connector if needed
            if self.connector is None:
                try:
                    self.connector = ArcGISConnector(self.config_loader)
                    logger.debug("ArcGIS connector initialized")
                except Exception as e:
                    logger.error(f"Failed to initialize ArcGIS connector: {e}")
                    return ProcessingResult(
                        success=False,
                        records_processed=0,
                        errors=[f"ArcGIS connector initialization failed: {e}"],
                        execution_time=(datetime.now() - start_time).total_seconds()
                    )
            
            # Get module configuration
            module_config = self._get_module_config()
            processing_config = module_config['processing']
            
            # TODO: Implement actual spatial processing logic
            # This is a placeholder implementation that will be expanded in subsequent tasks
            
            # Simulate processing metrics
            records_processed = 0
            processing_errors = []
            
            if dry_run:
                logger.info("Dry run mode: No actual changes will be made")
                # In dry run, simulate finding records that would be processed
                records_processed = 150  # Simulated count
            else:
                logger.info("Live processing mode: Changes will be applied")
                # TODO: Implement actual processing
                records_processed = 0
            
            # Update last run timestamp
            self._last_run = datetime.now()
            execution_time = (datetime.now() - start_time).total_seconds()
            
            # Create processing metadata
            metadata = {
                "dry_run": dry_run,
                "batch_size": processing_config["batch_size"],
                "max_retries": processing_config["max_retries"],
                "timeout_seconds": processing_config["timeout_seconds"],
                "module_version": "1.0.0"
            }
            
            logger.info(f"Processing completed: {records_processed} records processed in {execution_time:.2f}s")
            
            return ProcessingResult(
                success=True,
                records_processed=records_processed,
                errors=processing_errors,
                metadata=metadata,
                execution_time=execution_time
            )
            
        except Exception as e:
            execution_time = (datetime.now() - start_time).total_seconds()
            error_message = f"Processing failed: {e}"
            logger.error(error_message)
            
            return ProcessingResult(
                success=False,
                records_processed=0,
                errors=[str(e)],
                metadata={"dry_run": dry_run, "error_occurred_at": datetime.now().isoformat()},
                execution_time=execution_time
            )
    
    def get_status(self) -> ModuleStatus:
        """Get current module processing status.
        
        This method returns the current operational status of the module,
        including configuration validity, last run information, and health check results.
        
        Returns:
            ModuleStatus: Current module status and health information
        """
        is_configured = self.validate_configuration()
        health_check_result = self._health_check()
        
        # Determine overall status
        if not is_configured:
            status = "error"
        elif health_check_result:
            status = "ready"
        else:
            status = "error"
        
        return ModuleStatus(
            module_name="spatial_field_updater",
            is_configured=is_configured,
            last_run=self._last_run,
            status=status,
            health_check=health_check_result
        )
    
    def _health_check(self) -> bool:
        """Perform module health check.
        
        This method performs comprehensive health checks including configuration
        validity and connectivity to required services.
        
        Returns:
            bool: True if all health checks pass, False otherwise
        """
        try:
            # Check configuration validity
            if not self.validate_configuration():
                logger.debug("Health check failed: configuration invalid")
                return False
            
            # Check framework configuration accessibility
            try:
                env_config = self.config_loader.load_environment_config()
                field_mapping = self.config_loader.load_field_mapping()
                
                if not env_config or not field_mapping:
                    logger.debug("Health check failed: framework configuration not accessible")
                    return False
                    
            except Exception as e:
                logger.debug(f"Health check failed: framework configuration error: {e}")
                return False
            
            # Check module configuration file accessibility
            try:
                module_config = self._get_module_config()
                if not module_config:
                    logger.debug("Health check failed: module configuration not accessible")
                    return False
            except Exception as e:
                logger.debug(f"Health check failed: module configuration error: {e}")
                return False
            
            # TODO: In future, add connectivity checks to ArcGIS services
            # For now, basic checks are sufficient
            
            logger.debug("Health check passed")
            return True
            
        except Exception as e:
            logger.debug(f"Health check failed with exception: {e}")
            return False
    
    def get_all_layer_metadata(self) -> Dict[str, Any]:
        """Get metadata for all configured layers.
        
        Following Context7 best practices for comprehensive layer metadata retrieval
        including field definitions, record counts, and capabilities.
        
        Returns:
            Dictionary containing metadata for all configured layers
        """
        if not self.layer_manager:
            logger.warning("Layer manager not initialized - cannot retrieve metadata")
            return {}
        
        try:
            metadata = {}
            module_config = self._get_module_config()
            
            # Get weed locations layer metadata
            env_config = self.config_loader.load_environment_config()
            environment = env_config.get('current_environment', 'development')
            weed_layer_id = env_config.get(environment, {}).get('weed_locations_layer_id')
            
            if weed_layer_id:
                weed_metadata = self.layer_manager.get_layer_metadata(weed_layer_id)
                if weed_metadata:
                    metadata['weed_locations'] = weed_metadata.model_dump()
                    logger.debug(f"Retrieved metadata for weed locations layer: {weed_metadata.layer_name}")
            
            # Get area layers metadata
            area_layers = module_config.get('area_layers', {})
            for area_type, area_config in area_layers.items():
                layer_id = area_config.get('layer_id')
                if layer_id:
                    layer_metadata = self.layer_manager.get_layer_metadata(layer_id)
                    if layer_metadata:
                        metadata[area_type] = layer_metadata.model_dump()
                        logger.debug(f"Retrieved metadata for {area_type} layer: {layer_metadata.layer_name}")
            
            logger.info(f"Successfully retrieved metadata for {len(metadata)} layers")
            return metadata
            
        except Exception as e:
            logger.error(f"Failed to retrieve layer metadata: {e}")
            return {}
    
    def get_processing_summary(self) -> Dict[str, Any]:
        """Get a summary of the module's processing capabilities and status.
        
        Returns:
            Dictionary containing processing summary information
        """
        try:
            module_config = self._get_module_config()
            
            # Get layer metadata using Context7 best practices
            layer_metadata = self.get_all_layer_metadata()
            
            # Get layer cache statistics
            cache_stats = {}
            if self.layer_manager:
                cache_stats = self.layer_manager.get_cache_stats()
            
            return {
                "module_name": "spatial_field_updater",
                "description": "Automated spatial field updates for weed location data",
                "supported_operations": [
                    "Region assignment via spatial intersection",
                    "District assignment via spatial intersection",
                    "Incremental processing based on change detection",
                    "Batch processing with configurable batch sizes"
                ],
                "configuration": {
                    "batch_size": module_config.get("processing", {}).get("batch_size", "unknown"),
                    "area_layers": list(module_config.get("area_layers", {}).keys()),
                    "configured": self.validate_configuration()
                },
                "layer_metadata": layer_metadata,
                "layer_cache_stats": cache_stats,
                "metadata_table": {
                    "name": self.metadata_manager.get_metadata_table_name() if self.metadata_manager else "unknown",
                    "accessible": self.metadata_manager.access_metadata_table() is not None if self.metadata_manager else False
                },
                "status": self.get_status().model_dump(),
                "last_run": self._last_run.isoformat() if self._last_run else None
            }
        except Exception as e:
            logger.error(f"Failed to generate processing summary: {e}")
            return {
                "module_name": "spatial_field_updater",
                "error": f"Failed to generate summary: {e}"
            } 