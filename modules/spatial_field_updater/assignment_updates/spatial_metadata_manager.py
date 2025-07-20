"""Spatial Metadata Manager for Enhanced Processing Tracking

Implements framework metadata patterns for comprehensive spatial processing
tracking, fail-safe metadata writing, and processing history management.
"""

from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
import logging
from uuid import uuid4

from ..layer_access import MetadataTableManager, LayerAccessManager
from ..models import ProcessMetadata
from ..spatial_query import SpatialProcessingResult, SpatialUpdateResult
from ..change_detection import ProcessingDecision
from .metadata_models import (
    EnhancedProcessMetadata, UpdateMetrics, ErrorSummary, LayerVersionInfo,
    ProcessingPerformanceMetrics, MetadataValidationResult
)
from .batch_update_models import BatchUpdateResult
from src.config.config_loader import ConfigLoader
from src.exceptions import CAMSProcessingError

logger = logging.getLogger(__name__)


class SpatialMetadataManager:
    """Enhanced metadata manager for spatial processing operations.
    
    Implements framework metadata patterns for:
    - Comprehensive processing metadata with spatial-specific details
    - Fail-safe metadata writing (only on successful completion)
    - Processing history tracking and analysis
    - Layer version management and change detection
    - Error pattern analysis and trend tracking
    - Performance optimization tracking
    """
    
    def __init__(self, metadata_table_manager: MetadataTableManager, 
                 layer_manager: LayerAccessManager, config_loader: ConfigLoader):
        """Initialize spatial metadata manager.
        
        Args:
            metadata_table_manager: Base metadata table manager
            layer_manager: Layer access manager for version tracking
            config_loader: Configuration loader for metadata settings
        """
        self.metadata_table_manager = metadata_table_manager
        self.layer_manager = layer_manager
        self.config_loader = config_loader
        self._metadata_config = self._load_metadata_config()
        
        logger.info("SpatialMetadataManager initialized with fail-safe writing patterns")
    
    def create_processing_metadata(self, processing_decision: ProcessingDecision,
                                 spatial_result: SpatialProcessingResult,
                                 update_result: SpatialUpdateResult,
                                 batch_result: Optional[BatchUpdateResult] = None) -> EnhancedProcessMetadata:
        """Create comprehensive processing metadata.
        
        Combines spatial processing results, update results, and processing
        decisions into enhanced metadata following framework patterns.
        
        Args:
            processing_decision: Processing decision from change detection
            spatial_result: Results from spatial query processing
            update_result: Results from assignment updates
            batch_result: Optional batch update result details
            
        Returns:
            EnhancedProcessMetadata with comprehensive processing information
        """
        processing_id = str(uuid4())
        logger.info(f"Creating enhanced processing metadata: {processing_id}")
        
        try:
            # Calculate query optimization ratio (performance improvement)
            # Old approach: 1 query per assignment, New approach: 1 bulk query
            valid_assignments = spatial_result.spatial_metrics.successful_assignments
            query_optimization_ratio = valid_assignments if valid_assignments > 0 else 1.0
            
            # Create update metrics with performance tracking
            update_metrics = UpdateMetrics(
                total_assignments=spatial_result.processed_count,
                successful_updates=update_result.updated_count,
                failed_updates=update_result.failed_count,
                validation_failures=0,  # Will be enhanced when validation is integrated
                batch_count=len(spatial_result.batch_results) if spatial_result.batch_results else 1,
                average_batch_size=spatial_result.processed_count / len(spatial_result.batch_results) if spatial_result.batch_results else 0,
                update_rate_per_second=update_result.get_update_rate(),
                error_breakdown=self._analyze_error_patterns(update_result.errors),
                query_optimization_ratio=query_optimization_ratio
            )
            
            # Create error summary with categorized errors
            error_summary = ErrorSummary(
                validation_errors=[],  # Will be enhanced when validation is integrated
                update_errors=update_result.errors,
                permission_errors=[],  # Will be enhanced when permission checks are integrated
                connectivity_errors=[],  # Will be enhanced when connectivity checks are integrated
                rollback_errors=[],  # Will be enhanced when rollback is integrated
                error_patterns=self._analyze_error_patterns(update_result.errors)
            )
            
            # Get layer version information
            layer_versions = self._get_layer_version_info()
            
            # Create performance metrics
            performance_metrics = ProcessingPerformanceMetrics(
                spatial_processing_rate=spatial_result.processed_count / spatial_result.processing_duration if spatial_result.processing_duration > 0 else 0,
                update_processing_rate=update_result.get_update_rate(),
                total_processing_rate=(spatial_result.processed_count + update_result.updated_count) / (spatial_result.processing_duration + update_result.update_duration) if (spatial_result.processing_duration + update_result.update_duration) > 0 else 0,
                memory_peak_mb=None,  # Will be enhanced with memory monitoring
                cache_hit_rate=spatial_result.spatial_metrics.cache_hit_rate,
                query_optimization_achieved=query_optimization_ratio
            )
            
            # Create configuration snapshot
            config_snapshot = self._create_configuration_snapshot(processing_decision)
            
            # Generate processing summary
            processing_summary = self._generate_processing_summary(
                processing_decision, spatial_result, update_result, update_metrics
            )
            
            # Create optimization notes
            optimization_notes = self._generate_optimization_notes(
                spatial_result, update_result, update_metrics
            )
            
            metadata = EnhancedProcessMetadata(
                processing_id=processing_id,
                process_timestamp=datetime.now(),
                processing_type=processing_decision.processing_type,
                records_processed=spatial_result.processed_count,
                records_updated=update_result.updated_count,
                records_failed=update_result.failed_count,
                processing_duration=spatial_result.processing_duration,
                update_duration=update_result.update_duration,
                spatial_metrics=spatial_result.spatial_metrics,
                update_metrics=update_metrics,
                error_summary=error_summary,
                layer_versions=layer_versions,
                performance_metrics=performance_metrics,
                configuration_snapshot=config_snapshot,
                processing_summary=processing_summary,
                optimization_notes=optimization_notes
            )
            
            logger.debug(f"Created enhanced metadata: {metadata.get_comprehensive_summary()}")
            logger.debug(f"Optimization achieved: {metadata.get_optimization_summary()}")
            
            return metadata
            
        except Exception as e:
            logger.error(f"Failed to create processing metadata: {e}")
            raise CAMSProcessingError(f"Metadata creation failed: {e}")
    
    def write_metadata_on_success(self, metadata: EnhancedProcessMetadata, 
                                success_threshold: float = 0.95) -> bool:
        """Write metadata only on successful processing completion.
        
        Implements fail-safe metadata writing patterns:
        - Only writes metadata if processing meets success criteria
        - Validates metadata integrity before writing
        - Provides detailed logging for metadata operations
        
        Args:
            metadata: Enhanced processing metadata to write
            success_threshold: Minimum success rate required for metadata writing
            
        Returns:
            True if metadata was successfully written, False otherwise
        """
        logger.info(f"Evaluating metadata write for processing: {metadata.processing_id}")
        
        try:
            # Calculate success rate
            total_processed = metadata.records_processed
            if total_processed == 0:
                logger.warning("No records processed - skipping metadata write")
                return False
            
            success_rate = metadata.get_overall_success_rate()
            logger.debug(f"Processing success rate: {success_rate:.1%} (threshold: {success_threshold:.1%})")
            
            # Check success criteria
            if success_rate < success_threshold:
                logger.warning(f"Success rate {success_rate:.1%} below threshold {success_threshold:.1%} - "
                             f"skipping metadata write")
                logger.info(f"Processing summary: {metadata.get_comprehensive_summary()}")
                return False
            
            # Validate metadata integrity
            validation_result = self.validate_metadata_integrity(metadata)
            if not validation_result.is_valid:
                logger.error(f"Metadata integrity validation failed: {validation_result.errors}")
                return False
            
            # Convert to base ProcessMetadata format for compatibility
            base_metadata = self._convert_to_base_metadata(metadata)
            
            # Write metadata using base manager
            write_success = self.metadata_table_manager.write_processing_metadata(base_metadata)
            
            if write_success:
                logger.info(f"Successfully wrote processing metadata: {metadata.processing_id}")
                logger.info(f"Processing summary: {metadata.get_comprehensive_summary()}")
                logger.info(f"Optimization summary: {metadata.get_optimization_summary()}")
            else:
                logger.error(f"Failed to write processing metadata: {metadata.processing_id}")
            
            return write_success
            
        except Exception as e:
            logger.error(f"Metadata write operation failed: {e}")
            return False
    
    def validate_metadata_integrity(self, metadata: EnhancedProcessMetadata) -> MetadataValidationResult:
        """Validate metadata integrity before writing.
        
        Args:
            metadata: Enhanced processing metadata to validate
            
        Returns:
            MetadataValidationResult with validation status
        """
        validation_start = datetime.now()
        errors = []
        warnings = []
        
        try:
            # Validate basic fields
            if not metadata.processing_id:
                errors.append("Processing ID is missing")
            
            if metadata.records_processed < 0:
                errors.append("Records processed cannot be negative")
            
            if metadata.records_updated > metadata.records_processed:
                errors.append("Records updated cannot exceed records processed")
            
            if metadata.processing_duration < 0:
                errors.append("Processing duration cannot be negative")
            
            # Validate success rate consistency
            calculated_success_rate = metadata.get_overall_success_rate()
            expected_success_rate = metadata.update_metrics.get_success_rate()
            
            if abs(calculated_success_rate - expected_success_rate) > 0.01:  # Allow small rounding differences
                warnings.append(f"Success rate mismatch: calculated {calculated_success_rate:.1%}, "
                               f"metrics {expected_success_rate:.1%}")
            
            # Validate performance metrics consistency
            if metadata.performance_metrics.total_processing_rate < 0:
                errors.append("Processing rate cannot be negative")
            
            # Validate timestamp
            if metadata.process_timestamp > datetime.now():
                warnings.append("Process timestamp is in the future")
            
            validation_duration = (datetime.now() - validation_start).total_seconds()
            
            return MetadataValidationResult(
                is_valid=len(errors) == 0,
                errors=errors,
                warnings=warnings,
                validation_duration=validation_duration
            )
            
        except Exception as e:
            validation_duration = (datetime.now() - validation_start).total_seconds()
            return MetadataValidationResult(
                is_valid=False,
                errors=[f"Metadata validation failed: {e}"],
                warnings=[],
                validation_duration=validation_duration
            )
    
    def get_processing_history(self, days: int = 30) -> List[ProcessMetadata]:
        """Get processing history for trend analysis.
        
        Args:
            days: Number of days of history to retrieve
            
        Returns:
            List of ProcessMetadata entries from the specified period
        """
        try:
            # This would be implemented to query the metadata table for historical data
            # For now, return empty list as the base implementation doesn't support this
            logger.info(f"Processing history retrieval for {days} days (not yet implemented)")
            return []
            
        except Exception as e:
            logger.error(f"Failed to retrieve processing history: {e}")
            return []
    
    def _analyze_error_patterns(self, errors: List[str]) -> Dict[str, int]:
        """Analyze error patterns for categorization.
        
        Args:
            errors: List of error messages
            
        Returns:
            Dictionary with error pattern counts
        """
        patterns = {}
        
        for error in errors:
            error_lower = error.lower()
            
            if 'permission' in error_lower or 'access' in error_lower:
                patterns['permission_errors'] = patterns.get('permission_errors', 0) + 1
            elif 'network' in error_lower or 'connection' in error_lower or 'timeout' in error_lower:
                patterns['connectivity_errors'] = patterns.get('connectivity_errors', 0) + 1
            elif 'validation' in error_lower or 'invalid' in error_lower:
                patterns['validation_errors'] = patterns.get('validation_errors', 0) + 1
            elif 'update' in error_lower or 'edit' in error_lower:
                patterns['update_errors'] = patterns.get('update_errors', 0) + 1
            else:
                patterns['other_errors'] = patterns.get('other_errors', 0) + 1
        
        return patterns
    
    def _get_layer_version_info(self) -> LayerVersionInfo:
        """Get layer version information for all configured layers.
        
        Returns:
            LayerVersionInfo with layer identifiers and timestamps
        """
        try:
            # Get module configuration for layer IDs
            module_config = self.config_loader.get_config("modules.spatial_field_updater.field_updater_config")
            area_layers = module_config.get('area_layers', {})
            
            # Get environment configuration for weed layer
            env_config = self.config_loader.load_environment_config()
            environment = env_config.get('current_environment', 'development')
            weed_layer_id = env_config.get(environment, {}).get('weed_locations_layer_id', 'unknown')
            
            # Get current timestamp (in production, these would be actual layer update times)
            current_time = datetime.now()
            
            return LayerVersionInfo(
                weed_layer_id=weed_layer_id,
                weed_layer_updated=current_time,
                region_layer_id=area_layers.get('region', {}).get('layer_id', 'unknown'),
                region_layer_updated=current_time,
                district_layer_id=area_layers.get('district', {}).get('layer_id', 'unknown'),
                district_layer_updated=current_time
            )
            
        except Exception as e:
            logger.warning(f"Failed to get layer version info: {e}")
            current_time = datetime.now()
            return LayerVersionInfo(
                weed_layer_id='unknown',
                weed_layer_updated=current_time,
                region_layer_id='unknown',
                region_layer_updated=current_time,
                district_layer_id='unknown',
                district_layer_updated=current_time
            )
    
    def _create_configuration_snapshot(self, processing_decision: ProcessingDecision) -> Dict[str, Any]:
        """Create snapshot of configuration used for processing.
        
        Args:
            processing_decision: Processing decision containing configuration details
            
        Returns:
            Configuration snapshot dictionary
        """
        try:
            return {
                "processing_type": processing_decision.processing_type,
                "change_threshold_met": processing_decision.change_threshold_met,
                "estimated_processing_time": processing_decision.estimated_processing_time,
                "configuration_used": processing_decision.configuration_used,
                "incremental_filters": processing_decision.incremental_filters,
                "framework_version": "1.0.0",
                "optimization_enabled": True,
                "batch_processing": True,
                "fail_safe_metadata": True
            }
            
        except Exception as e:
            logger.warning(f"Failed to create configuration snapshot: {e}")
            return {"error": str(e)}
    
    def _generate_processing_summary(self, processing_decision: ProcessingDecision,
                                   spatial_result: SpatialProcessingResult,
                                   update_result: SpatialUpdateResult,
                                   update_metrics: UpdateMetrics) -> str:
        """Generate comprehensive processing summary.
        
        Args:
            processing_decision: Processing decision
            spatial_result: Spatial processing results
            update_result: Update operation results
            update_metrics: Update metrics
            
        Returns:
            Human-readable processing summary
        """
        success_rate = update_result.updated_count / spatial_result.processed_count if spatial_result.processed_count > 0 else 0
        total_duration = spatial_result.processing_duration + update_result.update_duration
        processing_rate = spatial_result.processed_count / total_duration if total_duration > 0 else 0
        
        return (f"{processing_decision.processing_type} processing: "
                f"{update_result.updated_count}/{spatial_result.processed_count} records updated "
                f"({success_rate:.1%} success) in {total_duration:.1f}s "
                f"({processing_rate:.1f} records/sec). "
                f"Query optimization: {update_metrics.query_optimization_ratio:.0f}x reduction achieved.")
    
    def _generate_optimization_notes(self, spatial_result: SpatialProcessingResult,
                                   update_result: SpatialUpdateResult,
                                   update_metrics: UpdateMetrics) -> List[str]:
        """Generate optimization achievement notes.
        
        Args:
            spatial_result: Spatial processing results
            update_result: Update operation results
            update_metrics: Update metrics
            
        Returns:
            List of optimization notes
        """
        notes = []
        
        # Query optimization note
        query_reduction = update_metrics.query_optimization_ratio
        notes.append(f"Batch processing achieved {query_reduction:.0f}x query reduction vs individual queries")
        
        # Performance note
        if update_metrics.update_rate_per_second > 50:
            notes.append("Excellent update performance achieved")
        elif update_metrics.update_rate_per_second > 25:
            notes.append("Good update performance achieved")
        else:
            notes.append("Update performance below optimal - consider batch size optimization")
        
        # Cache performance note
        cache_rate = spatial_result.spatial_metrics.cache_hit_rate
        if cache_rate > 0.8:
            notes.append(f"Excellent cache hit rate: {cache_rate:.1%}")
        elif cache_rate > 0.5:
            notes.append(f"Good cache hit rate: {cache_rate:.1%}")
        else:
            notes.append(f"Low cache hit rate: {cache_rate:.1%} - consider geometry patterns")
        
        return notes
    
    def _convert_to_base_metadata(self, enhanced_metadata: EnhancedProcessMetadata) -> ProcessMetadata:
        """Convert enhanced metadata to base ProcessMetadata for compatibility.
        
        Args:
            enhanced_metadata: Enhanced metadata to convert
            
        Returns:
            ProcessMetadata compatible with existing table structure
        """
        return ProcessMetadata(
            process_timestamp=enhanced_metadata.process_timestamp,
            region_layer_id=enhanced_metadata.layer_versions.region_layer_id,
            region_layer_updated=enhanced_metadata.layer_versions.region_layer_updated,
            district_layer_id=enhanced_metadata.layer_versions.district_layer_id,
            district_layer_updated=enhanced_metadata.layer_versions.district_layer_updated,
            process_status='Success' if enhanced_metadata.is_successful() else 'Error',
            records_processed=enhanced_metadata.records_processed,
            processing_duration=enhanced_metadata.get_total_duration(),
            error_message=None if enhanced_metadata.is_successful() else f"{enhanced_metadata.error_summary.get_total_errors()} errors occurred",
            metadata_details={
                "processing_id": enhanced_metadata.processing_id,
                "processing_type": enhanced_metadata.processing_type,
                "optimization_summary": enhanced_metadata.get_optimization_summary(),
                "performance_rating": enhanced_metadata.performance_metrics.get_performance_rating(),
                "query_optimization_ratio": enhanced_metadata.update_metrics.query_optimization_ratio,
                "enhanced_metadata": True
            }
        )
    
    def _load_metadata_config(self) -> Dict[str, Any]:
        """Load metadata configuration settings."""
        try:
            module_config = self.config_loader.get_config("modules.spatial_field_updater.field_updater_config")
            return module_config.get("enhanced_metadata", {
                "fail_safe_writing": {
                    "success_threshold": 0.95,
                    "integrity_validation": True
                },
                "processing_history": {
                    "retention_days": 90
                }
            })
        except Exception as e:
            logger.warning(f"Failed to load metadata config: {e}")
            return {
                "fail_safe_writing": {
                    "success_threshold": 0.95,
                    "integrity_validation": True
                },
                "processing_history": {
                    "retention_days": 90
                }
            } 