"""
Spatial Change Detector

This module implements the core change detection logic for the spatial field updater,
following Context7 best practices for date-based queries and metadata comparison.

The SpatialChangeDetector monitors EditDate_1 field changes in ArcGIS layers to make
intelligent processing decisions between full reprocessing and incremental updates.
"""

from typing import Optional, Dict, List, Any, Tuple
from datetime import datetime, timedelta
import logging

from ..layer_access import LayerAccessManager, MetadataTableManager
from ..models import ProcessMetadata
from .change_detection_models import (
    ChangeDetectionResult, ProcessingDecision, ProcessingType, ChangeMetrics
)
from src.config.config_loader import ConfigLoader

logger = logging.getLogger(__name__)


class SpatialChangeDetector:
    """Detects changes in spatial layers requiring reprocessing.
    
    Implements Context7 best practices for:
    - Date-based WHERE clause queries for EditDate_1 monitoring
    - Efficient change detection using query(return_count_only=True)
    - Metadata comparison for processing decisions
    - Batch processing patterns for large datasets
    
    The detector analyzes layer changes and provides intelligent recommendations
    for processing type (full, incremental, or none) based on configurable thresholds.
    """
    
    def __init__(self, layer_manager: LayerAccessManager, 
                 metadata_manager: MetadataTableManager, 
                 config_loader: ConfigLoader):
        """Initialize change detector with layer access and metadata management.
        
        Args:
            layer_manager: Manager for ArcGIS layer access and operations
            metadata_manager: Manager for processing metadata operations
            config_loader: Configuration loader for change detection settings
        """
        self.layer_manager = layer_manager
        self.metadata_manager = metadata_manager
        self.config_loader = config_loader
        self._change_config = self._load_change_detection_config()
        logger.info("SpatialChangeDetector initialized with configuration: %s", 
                   {k: v for k, v in self._change_config.items() if k != 'performance'})
    
    def detect_changes(self, layer_id: str, since_timestamp: Optional[datetime] = None) -> ChangeDetectionResult:
        """Detect changes in a layer since the specified timestamp.
        
        Following Context7 best practices for efficient change detection using
        date-based WHERE clauses and optimized queries. Uses EditDate_1 field
        monitoring to identify modified records.
        
        Args:
            layer_id: ArcGIS layer identifier to analyze
            since_timestamp: Timestamp to check changes since (defaults to last processing)
            
        Returns:
            ChangeDetectionResult with comprehensive change analysis and processing recommendation
            
        Raises:
            ValueError: If layer cannot be accessed or layer_id is invalid
        """
        start_time = datetime.now()
        logger.info(f"Starting change detection for layer {layer_id}")
        
        try:
            # Validate layer accessibility
            layer_metadata = self.layer_manager.get_layer_metadata(layer_id)
            if not layer_metadata:
                raise ValueError(f"Could not access layer metadata for {layer_id}")
            
            # Determine since timestamp from last processing if not provided
            if since_timestamp is None:
                since_timestamp = self._get_last_processing_timestamp()
                logger.debug(f"Using last processing timestamp: {since_timestamp}")
            
            # Get layer instance for querying
            layer = self.layer_manager.get_layer_by_id(layer_id)
            if not layer:
                raise ValueError(f"Could not access layer instance for {layer_id}")
            
            # Get total record count using Context7 best practice
            total_records = self._get_total_record_count(layer)
            logger.debug(f"Total records in layer: {total_records}")
            
            # Detect modified records using EditDate_1 field
            modified_count, modified_records = self._get_modified_records(
                layer, since_timestamp
            )
            
            # Detect new records (records created after last processing)
            new_count = self._get_new_records_count(layer, since_timestamp)
            
            # Calculate change metrics
            change_percentage = (modified_count / total_records * 100) if total_records > 0 else 0
            processing_duration = (datetime.now() - start_time).total_seconds()
            
            # Create detailed change metrics
            change_metrics = ChangeMetrics(
                records_analyzed=total_records,
                edit_date_changes=modified_count,
                geometry_changes=0,  # Could be enhanced to detect geometry changes
                attribute_changes=modified_count,  # Assuming all EditDate_1 changes are attribute changes
                processing_duration=processing_duration,
                last_check_timestamp=datetime.now()
            )
            
            # Determine processing recommendation based on change analysis
            processing_recommendation = self._determine_processing_type(
                total_records, modified_count, change_percentage
            )
            
            # Build comprehensive change detection result
            result = ChangeDetectionResult(
                layer_id=layer_id,
                detection_timestamp=datetime.now(),
                total_records=total_records,
                modified_records=modified_count,
                new_records=new_count,
                deleted_records=0,  # Could be enhanced to detect deletions via tombstone records
                change_percentage=change_percentage,
                processing_recommendation=processing_recommendation,
                change_details={
                    "since_timestamp": since_timestamp.isoformat(),
                    "edit_date_field": self._change_config.get("edit_date_field", "EditDate_1"),
                    "detection_method": "edit_date_monitoring",
                    "layer_name": layer_metadata.layer_name,
                    "modified_record_ids": modified_records[:100] if len(modified_records) <= 100 else modified_records[:100] + ["...truncated"]
                },
                change_metrics=change_metrics
            )
            
            logger.info(f"Change detection completed: {modified_count}/{total_records} records changed ({change_percentage:.2f}%) - {processing_recommendation}")
            return result
            
        except Exception as e:
            processing_duration = (datetime.now() - start_time).total_seconds()
            logger.error(f"Change detection failed for layer {layer_id}: {e}")
            
            # Return error result indicating failure
            return ChangeDetectionResult(
                layer_id=layer_id,
                detection_timestamp=datetime.now(),
                total_records=0,
                modified_records=0,
                new_records=0,
                deleted_records=0,
                change_percentage=0.0,
                processing_recommendation=ProcessingType.NO_PROCESSING_NEEDED,
                change_details={
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "detection_failed": True
                },
                change_metrics=ChangeMetrics(
                    records_analyzed=0,
                    edit_date_changes=0,
                    geometry_changes=0,
                    attribute_changes=0,
                    processing_duration=processing_duration,
                    last_check_timestamp=datetime.now()
                )
            )
    
    def compare_with_last_processing(self, layer_id: str) -> ProcessingDecision:
        """Compare current layer state with last processing metadata to make processing decision.
        
        This method integrates change detection with metadata management to provide
        intelligent processing decisions based on actual changes since last processing.
        
        Args:
            layer_id: ArcGIS layer identifier to analyze
            
        Returns:
            ProcessingDecision with recommended processing type and configuration
        """
        try:
            # Get last processing metadata from metadata table
            last_metadata = self.metadata_manager.read_last_processing_metadata()
            
            if not last_metadata:
                logger.info("No previous processing metadata found - recommending full processing")
                return ProcessingDecision(
                    processing_type=ProcessingType.FULL_REPROCESSING,
                    target_records=[],
                    change_threshold_met=True,
                    full_reprocess_required=True,
                    incremental_filters={},
                    reasoning="No previous processing metadata found - initial processing required",
                    configuration_used=self._get_configuration_summary()
                )
            
            # Detect changes since last processing
            change_result = self.detect_changes(layer_id, last_metadata.process_timestamp)
            
            # Handle detection errors
            if "error" in change_result.change_details:
                logger.warning(f"Change detection failed: {change_result.change_details['error']}")
                return ProcessingDecision(
                    processing_type=ProcessingType.FORCE_FULL_UPDATE,
                    target_records=[],
                    change_threshold_met=True,
                    full_reprocess_required=True,
                    incremental_filters={},
                    reasoning=f"Change detection failed: {change_result.change_details['error']}",
                    configuration_used=self._get_configuration_summary()
                )
            
            # Extract modified record IDs for incremental processing
            modified_record_ids = change_result.change_details.get("modified_record_ids", [])
            if isinstance(modified_record_ids, list) and "...truncated" in modified_record_ids:
                modified_record_ids = modified_record_ids[:-1]  # Remove truncation marker
            
            # Create processing decision based on change detection
            decision = ProcessingDecision(
                processing_type=change_result.processing_recommendation,
                target_records=modified_record_ids if change_result.processing_recommendation == ProcessingType.INCREMENTAL_UPDATE else [],
                change_threshold_met=change_result.change_percentage > self._change_config.get("thresholds", {}).get("incremental_threshold_percentage", 1.0),
                full_reprocess_required=change_result.processing_recommendation in [ProcessingType.FULL_REPROCESSING, ProcessingType.FORCE_FULL_UPDATE],
                incremental_filters={
                    "where_clause": f"{self._change_config.get('edit_date_field', 'EditDate_1')} > {int(last_metadata.process_timestamp.timestamp() * 1000)}",
                    "modified_count": change_result.modified_records,
                    "since_timestamp": last_metadata.process_timestamp.isoformat()
                } if change_result.processing_recommendation == ProcessingType.INCREMENTAL_UPDATE else {},
                reasoning=f"Change detection found {change_result.modified_records} modified records ({change_result.change_percentage:.2f}% change) since {last_metadata.process_timestamp.strftime('%Y-%m-%d %H:%M:%S')}",
                estimated_processing_time=self._estimate_processing_time(change_result),
                configuration_used=self._get_configuration_summary()
            )
            
            logger.info(f"Processing decision: {decision.processing_type} - {decision.reasoning}")
            return decision
            
        except Exception as e:
            logger.error(f"Failed to compare with last processing: {e}")
            return ProcessingDecision(
                processing_type=ProcessingType.FORCE_FULL_UPDATE,
                target_records=[],
                change_threshold_met=True,
                full_reprocess_required=True,
                incremental_filters={},
                reasoning=f"Error in change detection comparison: {e}",
                configuration_used=self._get_configuration_summary()
            )
    
    def _get_total_record_count(self, layer) -> int:
        """Get total record count using Context7 optimized query."""
        try:
            return layer.query(return_count_only=True)
        except Exception as e:
            logger.warning(f"Failed to get total record count: {e}")
            return 0
    
    def _get_modified_records(self, layer, since_timestamp: datetime) -> Tuple[int, List[str]]:
        """Get modified records using Context7 date-based WHERE clause query.
        
        Uses efficient ArcGIS API patterns for date-based filtering and record retrieval.
        
        Args:
            layer: ArcGIS FeatureLayer instance
            since_timestamp: Timestamp to check changes since
            
        Returns:
            Tuple of (modified_count, list_of_record_ids)
        """
        try:
            # Convert datetime to ArcGIS compatible format (milliseconds since epoch)
            timestamp_ms = int(since_timestamp.timestamp() * 1000)
            edit_date_field = self._change_config.get("edit_date_field", "EditDate_1")
            
            # Context7 best practice: Use date-based WHERE clause for efficient filtering
            where_clause = f"{edit_date_field} > {timestamp_ms}"
            logger.debug(f"Using WHERE clause: {where_clause}")
            
            # Get count efficiently using return_count_only
            modified_count = layer.query(where=where_clause, return_count_only=True)
            
            # Get record IDs for incremental processing (limit to reasonable size)
            modified_records = []
            max_records = self._change_config.get("thresholds", {}).get("max_incremental_records", 1000)
            
            if modified_count > 0 and modified_count <= max_records:
                try:
                    # Query for OBJECTID to get specific record identifiers
                    result = layer.query(
                        where=where_clause, 
                        out_fields=["OBJECTID"],
                        result_record_count=min(modified_count, max_records)
                    )
                    modified_records = [str(f.attributes["OBJECTID"]) for f in result.features if f.attributes.get("OBJECTID")]
                except Exception as e:
                    logger.warning(f"Failed to get modified record IDs: {e}")
                    # Continue with count only
            
            logger.debug(f"Found {modified_count} modified records since {since_timestamp}")
            return modified_count, modified_records
            
        except Exception as e:
            logger.warning(f"Failed to get modified records: {e}")
            return 0, []
    
    def _get_new_records_count(self, layer, since_timestamp: datetime) -> int:
        """Get count of new records since timestamp.
        
        Assumes new records have EditDate_1 near their creation time.
        This is a simplified implementation that could be enhanced with
        creation date tracking if available.
        """
        try:
            timestamp_ms = int(since_timestamp.timestamp() * 1000)
            edit_date_field = self._change_config.get("edit_date_field", "EditDate_1")
            
            # For simplicity, assume new records have EditDate_1 >= since_timestamp
            # This could be enhanced with a dedicated creation date field
            where_clause = f"{edit_date_field} >= {timestamp_ms}"
            return layer.query(where=where_clause, return_count_only=True)
            
        except Exception as e:
            logger.warning(f"Failed to get new records count: {e}")
            return 0
    
    def _determine_processing_type(self, total_records: int, modified_count: int, 
                                 change_percentage: float) -> ProcessingType:
        """Determine processing type based on change metrics and configuration thresholds.
        
        Decision logic:
        1. No changes -> NO_PROCESSING_NEEDED
        2. Changes > full_reprocess_threshold -> FULL_REPROCESSING
        3. Modified count > max_incremental_records -> FULL_REPROCESSING
        4. Changes >= incremental_threshold -> INCREMENTAL_UPDATE
        5. Changes < incremental_threshold -> NO_PROCESSING_NEEDED
        
        Args:
            total_records: Total records in layer
            modified_count: Number of modified records
            change_percentage: Percentage of records changed
            
        Returns:
            ProcessingType recommendation
        """
        # Load thresholds from configuration
        thresholds = self._change_config.get("thresholds", {})
        
        full_reprocess_threshold = thresholds.get("full_reprocess_percentage", 25.0)
        incremental_threshold = thresholds.get("incremental_threshold_percentage", 1.0)
        max_incremental_records = thresholds.get("max_incremental_records", 1000)
        
        # Decision logic with detailed logging
        if modified_count == 0:
            logger.debug("No changes detected - no processing needed")
            return ProcessingType.NO_PROCESSING_NEEDED
        elif change_percentage >= full_reprocess_threshold:
            logger.debug(f"Change percentage {change_percentage:.2f}% exceeds full reprocess threshold {full_reprocess_threshold}%")
            return ProcessingType.FULL_REPROCESSING
        elif modified_count > max_incremental_records:
            logger.debug(f"Modified records {modified_count} exceeds max incremental limit {max_incremental_records}")
            return ProcessingType.FULL_REPROCESSING
        elif change_percentage >= incremental_threshold:
            logger.debug(f"Change percentage {change_percentage:.2f}% meets incremental threshold {incremental_threshold}%")
            return ProcessingType.INCREMENTAL_UPDATE
        else:
            logger.debug(f"Change percentage {change_percentage:.2f}% below incremental threshold {incremental_threshold}%")
            return ProcessingType.NO_PROCESSING_NEEDED
    
    def _get_last_processing_timestamp(self) -> datetime:
        """Get timestamp of last processing or default fallback.
        
        Returns:
            Timestamp of last processing, or 30 days ago as fallback
        """
        try:
            last_metadata = self.metadata_manager.read_last_processing_metadata()
            if last_metadata and last_metadata.process_timestamp:
                return last_metadata.process_timestamp
            else:
                # Default fallback to 30 days ago if no previous processing
                fallback = datetime.now() - timedelta(days=30)
                logger.info(f"No previous processing found, using fallback timestamp: {fallback}")
                return fallback
        except Exception as e:
            logger.warning(f"Could not get last processing timestamp: {e}")
            fallback = datetime.now() - timedelta(days=30)
            logger.info(f"Using fallback timestamp due to error: {fallback}")
            return fallback
    
    def _estimate_processing_time(self, change_result: ChangeDetectionResult) -> float:
        """Estimate processing time based on change metrics and processing type.
        
        Provides rough time estimates for processing planning and user feedback.
        
        Args:
            change_result: Change detection result with metrics
            
        Returns:
            Estimated processing time in seconds
        """
        # Simple estimation based on record count and processing type
        # These values could be calibrated based on actual performance data
        base_time_per_record = 0.1  # seconds per record (configurable)
        
        if change_result.processing_recommendation == ProcessingType.FULL_REPROCESSING:
            # Full processing: process all records
            estimated_time = change_result.total_records * base_time_per_record
        elif change_result.processing_recommendation == ProcessingType.INCREMENTAL_UPDATE:
            # Incremental processing: slightly slower per record due to filtering overhead
            estimated_time = change_result.modified_records * base_time_per_record * 2
        else:
            # No processing or force update
            estimated_time = 0.0
        
        return round(estimated_time, 1)
    
    def _get_configuration_summary(self) -> Dict[str, Any]:
        """Get summary of configuration used for processing decisions."""
        return {
            "thresholds": self._change_config.get("thresholds", {}),
            "edit_date_field": self._change_config.get("edit_date_field", "EditDate_1"),
            "enabled": self._change_config.get("enabled", True)
        }
    
    def _load_change_detection_config(self) -> Dict[str, Any]:
        """Load change detection configuration with defaults.
        
        Loads configuration from the module config file, providing sensible
        defaults if configuration is not available.
        
        Returns:
            Dictionary containing change detection configuration
        """
        try:
            # Attempt to load from module configuration
            import json
            from pathlib import Path
            
            config_path = Path("modules/spatial_field_updater/config/field_updater_config.json")
            if config_path.exists():
                with open(config_path) as f:
                    config = json.load(f)
                
                change_config = config.get("change_detection", {})
                logger.debug(f"Loaded change detection config from {config_path}")
                return change_config
            else:
                logger.warning(f"Config file not found: {config_path}")
                
        except Exception as e:
            logger.warning(f"Could not load change detection config: {e}")
        
        # Return default configuration
        default_config = {
            "enabled": True,
            "edit_date_field": "EditDate_1",
            "thresholds": {
                "full_reprocess_percentage": 25.0,
                "incremental_threshold_percentage": 1.0,
                "max_incremental_records": 1000,
                "no_change_threshold_percentage": 0.1
            },
            "processing_decisions": {
                "default_processing_type": "incremental_update",
                "force_full_reprocess_days": 7,
                "max_incremental_age_hours": 24
            },
            "performance": {
                "batch_size": 100,
                "query_timeout_seconds": 60,
                "max_records_per_query": 5000
            }
        }
        
        logger.info("Using default change detection configuration")
        return default_config 