"""Metadata Table Manager for processing metadata tracking.

Manages access to the Weeds Area Metadata table with environment-aware naming
and comprehensive processing metadata tracking following Context7 best practices.
"""

from typing import Optional
import logging
from datetime import datetime
import json
from pathlib import Path

from src.connection.arcgis_connector import ArcGISConnector
from src.config.config_loader import ConfigLoader
from ..models import ProcessMetadata
from .layer_access_manager import LayerAccessManager

logger = logging.getLogger(__name__)


class MetadataTableManager:
    """Manages access to the Weeds Area Metadata table for processing tracking.
    
    Implements Context7 best practices for:
    - Environment-aware table access (dev/prod naming)
    - Robust metadata table search and validation
    - Comprehensive error handling and logging
    - Processing metadata read/write operations
    """
    
    def __init__(self, connector: ArcGISConnector, config_loader: ConfigLoader, 
                 layer_manager: LayerAccessManager):
        """Initialize metadata table manager.
        
        Args:
            connector: Authenticated ArcGIS connector
            config_loader: Configuration loader for environment settings
            layer_manager: Layer access manager for table operations
        """
        self.connector = connector
        self.config_loader = config_loader
        self.layer_manager = layer_manager
        self._metadata_table = None
        logger.info("MetadataTableManager initialized")
    
    def get_metadata_table_name(self) -> str:
        """Get the appropriate metadata table name for current environment.
        
        Following Context7 best practices for environment-specific configurations.
        
        Returns:
            Environment-appropriate metadata table name
        """
        try:
            # Load module configuration
            module_config = self._load_module_config()
            
            # Determine environment
            env_config = self.config_loader.load_environment_config()
            environment = env_config.get('current_environment', 'development')
            
            metadata_config = module_config.get('metadata_table', {})
            if environment == 'production':
                table_name = metadata_config.get('production_name', 'Weeds Area Metadata')
            else:
                table_name = metadata_config.get('development_name', 'XXX Weeds Area Metadata DEV')
            
            logger.debug(f"Metadata table name for {environment}: {table_name}")
            return table_name
                
        except Exception as e:
            logger.error(f"Failed to determine metadata table name: {e}")
            return 'Weeds Area Metadata'  # Default fallback
    
    def access_metadata_table(self) -> Optional[object]:
        """Access the metadata table layer.
        
        Implements Context7 best practices for table access with comprehensive
        error handling and multiple access patterns (tables vs layers).
        
        Returns:
            Metadata table/layer object or None if not accessible
        """
        if self._metadata_table:
            logger.debug("Returning cached metadata table")
            return self._metadata_table
        
        try:
            # Search for metadata table by name using Context7 approach
            gis = self.connector.get_gis()
            table_name = self.get_metadata_table_name()
            
            logger.info(f"Searching for metadata table: {table_name}")
            
            # Search for the metadata table in content
            search_results = gis.content.search(f'title:"{table_name}"', item_type='Feature Service')
            
            if not search_results:
                logger.warning(f"Metadata table '{table_name}' not found in content search")
                return None
            
            # Get the first matching service
            metadata_service = search_results[0]
            logger.info(f"Found metadata service: {metadata_service.title}")
            
            # Access the table (Context7 best practice: check tables then layers)
            if hasattr(metadata_service, 'tables') and metadata_service.tables:
                self._metadata_table = metadata_service.tables[0]
                logger.info(f"Accessed metadata table: {self._metadata_table.properties.name}")
            elif hasattr(metadata_service, 'layers') and metadata_service.layers:
                # Sometimes stored as a layer instead of table
                self._metadata_table = metadata_service.layers[0]
                logger.info(f"Accessed metadata layer: {self._metadata_table.properties.name}")
            else:
                logger.error(f"No accessible tables or layers found in metadata service")
                return None
            
            return self._metadata_table
            
        except Exception as e:
            logger.error(f"Failed to access metadata table: {e}")
            return None
    
    def read_last_processing_metadata(self) -> Optional[ProcessMetadata]:
        """Read the most recent processing metadata from the table.
        
        Following Context7 best practices for efficient querying with
        proper ordering and error handling.
        
        Returns:
            Most recent ProcessMetadata or None if not found
        """
        metadata_table = self.access_metadata_table()
        if not metadata_table:
            logger.warning("Cannot read metadata: metadata table not accessible")
            return None
        
        try:
            # Query for the most recent record using Context7 recommended approach
            query_result = metadata_table.query(
                where="1=1",
                order_by_fields="ProcessTimestamp DESC",
                result_record_count=1
            )
            
            if not query_result.features:
                logger.info("No previous processing metadata found")
                return None
            
            # Extract metadata from the most recent record
            feature = query_result.features[0]
            attributes = feature.attributes
            
            logger.debug(f"Retrieved metadata record with timestamp: {attributes.get('ProcessTimestamp')}")
            
            # Map table fields to ProcessMetadata model with safe conversions
            metadata = ProcessMetadata(
                process_timestamp=self._safe_timestamp_conversion(attributes.get('ProcessTimestamp', 0)),
                region_layer_id=attributes.get('RegionLayerID', ''),
                region_layer_updated=self._safe_timestamp_conversion(attributes.get('RegionLayerUpdated', 0)),
                district_layer_id=attributes.get('DistrictLayerID', ''),
                district_layer_updated=self._safe_timestamp_conversion(attributes.get('DistrictLayerUpdated', 0)),
                process_status=attributes.get('ProcessStatus', 'Error'),
                records_processed=attributes.get('RecordsProcessed', 0),
                processing_duration=attributes.get('ProcessingDuration'),
                error_message=attributes.get('ErrorMessage'),
                metadata_details={}  # Can be extended with additional fields
            )
            
            logger.info(f"Successfully read processing metadata: {metadata.process_status}")
            return metadata
            
        except Exception as e:
            logger.error(f"Failed to read processing metadata: {e}")
            return None
    
    def write_processing_metadata(self, metadata: ProcessMetadata) -> bool:
        """Write processing metadata to the table.
        
        Following Context7 best practices for feature editing with
        proper error handling and result validation.
        
        Args:
            metadata: ProcessMetadata instance to write
            
        Returns:
            True if successful, False otherwise
        """
        metadata_table = self.access_metadata_table()
        if not metadata_table:
            logger.error("Cannot write metadata: metadata table not accessible")
            return False
        
        try:
            # Convert ProcessMetadata to table record format
            attributes = {
                'ProcessTimestamp': int(metadata.process_timestamp.timestamp() * 1000),
                'RegionLayerID': metadata.region_layer_id,
                'RegionLayerUpdated': int(metadata.region_layer_updated.timestamp() * 1000),
                'DistrictLayerID': metadata.district_layer_id,
                'DistrictLayerUpdated': int(metadata.district_layer_updated.timestamp() * 1000),
                'ProcessStatus': metadata.process_status,
                'RecordsProcessed': metadata.records_processed,
                'ProcessingDuration': metadata.processing_duration,
                'ErrorMessage': metadata.error_message
            }
            
            # Create feature for insertion (Context7 best practice)
            feature = {
                'attributes': attributes
            }
            
            logger.debug(f"Writing metadata record for status: {metadata.process_status}")
            
            # Add the record to the table using Context7 recommended approach
            result = metadata_table.edit_features(adds=[feature])
            
            # Validate result using Context7 error checking pattern
            if result.get('addResults') and result['addResults'][0].get('success'):
                logger.info("Processing metadata written successfully")
                return True
            else:
                error_details = result.get('addResults', [{}])[0].get('error', 'Unknown error')
                logger.error(f"Failed to write metadata: {error_details}")
                return False
                
        except Exception as e:
            logger.error(f"Error writing processing metadata: {e}")
            return False
    
    def verify_metadata_table_schema(self) -> bool:
        """Verify that the metadata table has the expected schema.
        
        Following Context7 best practices for schema validation and
        comprehensive field checking.
        
        Returns:
            True if schema is valid, False otherwise
        """
        metadata_table = self.access_metadata_table()
        if not metadata_table:
            logger.error("Cannot verify schema: metadata table not accessible")
            return False
        
        try:
            # Load expected fields from configuration
            module_config = self._load_module_config()
            expected_fields = module_config.get('metadata_table', {}).get('required_fields', {
                'ProcessTimestamp': 'date',
                'RegionLayerID': 'string',
                'RegionLayerUpdated': 'date',
                'DistrictLayerID': 'string',
                'DistrictLayerUpdated': 'date',
                'ProcessStatus': 'string',
                'RecordsProcessed': 'integer',
                'ProcessingDuration': 'double',
                'ErrorMessage': 'string'
            })
            
            # Get actual fields using Context7 approach
            properties = metadata_table.properties
            actual_fields = {field.name: field.type for field in properties.fields}
            
            # Check for missing required fields
            missing_fields = []
            for field_name, expected_type in expected_fields.items():
                if field_name not in actual_fields:
                    missing_fields.append(field_name)
            
            if missing_fields:
                logger.error(f"Metadata table missing required fields: {missing_fields}")
                return False
            
            logger.info("Metadata table schema validation passed")
            return True
            
        except Exception as e:
            logger.error(f"Failed to verify metadata table schema: {e}")
            return False
    
    def _safe_timestamp_conversion(self, timestamp_ms: int) -> datetime:
        """Safely convert timestamp from milliseconds to datetime.
        
        Args:
            timestamp_ms: Timestamp in milliseconds
            
        Returns:
            datetime object or current time as fallback
        """
        try:
            if timestamp_ms and timestamp_ms > 0:
                return datetime.fromtimestamp(timestamp_ms / 1000)
            else:
                return datetime.now()
        except (ValueError, OSError) as e:
            logger.warning(f"Invalid timestamp {timestamp_ms}, using current time: {e}")
            return datetime.now()
    
    def _load_module_config(self) -> dict:
        """Load module configuration.
        
        Returns:
            Module configuration dictionary
        """
        try:
            config_path = Path("modules/spatial_field_updater/config/field_updater_config.json")
            if not config_path.exists():
                logger.warning(f"Module config not found at {config_path}")
                return {}
                
            with open(config_path) as f:
                config = json.load(f)
                logger.debug("Successfully loaded module configuration")
                return config
                
        except Exception as e:
            logger.error(f"Failed to load module configuration: {e}")
            return {}
    
    def clear_table_cache(self) -> None:
        """Clear cached metadata table reference.
        
        Useful for forcing re-authentication or table reaccess.
        """
        self._metadata_table = None
        logger.info("Cleared metadata table cache") 