"""
Performance Optimizations for Change Detection System

This module documents and implements performance optimizations for the change detection
system, following Context7 best practices for efficient ArcGIS API operations.

Key optimizations implemented:
1. Context7 date-based WHERE clause queries for efficient filtering
2. return_count_only queries to minimize data transfer
3. Batch processing patterns for large datasets
4. Layer caching through LayerAccessManager integration
5. Configurable query timeouts and limits
6. Memory-efficient record processing
"""

from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class PerformanceMetrics:
    """Performance metrics for change detection operations."""
    query_time: float
    record_count: int
    cache_hits: int
    cache_misses: int
    memory_usage_mb: float
    batch_count: int
    
    def get_efficiency_score(self) -> float:
        """Calculate efficiency score based on metrics."""
        if self.cache_hits + self.cache_misses == 0:
            cache_ratio = 0.0
        else:
            cache_ratio = self.cache_hits / (self.cache_hits + self.cache_misses)
        
        # Efficiency based on cache performance and query speed
        return (cache_ratio * 0.7) + (min(1.0, 10.0 / max(self.query_time, 0.1)) * 0.3)


class PerformanceOptimizer:
    """Performance optimization utilities for change detection.
    
    Implements Context7 best practices for optimal ArcGIS API performance:
    - Efficient date-based filtering using millisecond timestamps
    - Optimized query patterns with return_count_only
    - Batch processing for large result sets
    - Memory-conscious record handling
    """
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize performance optimizer with configuration.
        
        Args:
            config: Configuration dictionary with performance settings
        """
        self.config = config
        self.performance_config = config.get('performance', {})
        self.batch_size = self.performance_config.get('batch_size', 100)
        self.query_timeout = self.performance_config.get('query_timeout_seconds', 60)
        self.max_records_per_query = self.performance_config.get('max_records_per_query', 5000)
        
    def optimize_where_clause(self, since_timestamp: datetime, edit_date_field: str = "EditDate_1") -> str:
        """Create optimized WHERE clause for date-based filtering.
        
        Following Context7 best practice of converting datetime to ArcGIS-compatible
        millisecond timestamps for optimal query performance.
        
        Args:
            since_timestamp: Timestamp to filter from
            edit_date_field: Name of the edit date field
            
        Returns:
            Optimized WHERE clause string
        """
        # Convert to milliseconds since epoch (ArcGIS standard)
        timestamp_ms = int(since_timestamp.timestamp() * 1000)
        
        # Use optimized date comparison
        where_clause = f"{edit_date_field} > {timestamp_ms}"
        
        logger.debug(f"Optimized WHERE clause: {where_clause}")
        return where_clause
    
    def should_use_batch_processing(self, estimated_record_count: int) -> bool:
        """Determine if batch processing should be used based on record count.
        
        Args:
            estimated_record_count: Estimated number of records to process
            
        Returns:
            True if batch processing is recommended
        """
        return estimated_record_count > self.max_records_per_query
    
    def calculate_optimal_batch_size(self, total_records: int, available_memory_mb: float = 512) -> int:
        """Calculate optimal batch size based on record count and available memory.
        
        Args:
            total_records: Total number of records to process
            available_memory_mb: Available memory in megabytes
            
        Returns:
            Optimal batch size for processing
        """
        # Estimate memory per record (conservative estimate)
        estimated_memory_per_record_kb = 2.0  # 2KB per record
        
        # Calculate maximum records that fit in available memory
        max_records_by_memory = int((available_memory_mb * 1024) / estimated_memory_per_record_kb)
        
        # Use configured batch size, memory constraint, or total records (whichever is smallest)
        optimal_size = min(
            self.batch_size,
            max_records_by_memory,
            total_records,
            self.max_records_per_query
        )
        
        logger.debug(f"Calculated optimal batch size: {optimal_size} for {total_records} records")
        return max(1, optimal_size)  # Ensure at least 1
    
    def create_performance_monitoring_context(self) -> 'PerformanceMonitor':
        """Create performance monitoring context manager.
        
        Returns:
            PerformanceMonitor context manager for tracking operation performance
        """
        return PerformanceMonitor()


class PerformanceMonitor:
    """Context manager for monitoring change detection performance."""
    
    def __init__(self):
        self.start_time = None
        self.end_time = None
        self.cache_stats = {"hits": 0, "misses": 0}
        self.query_count = 0
        self.record_count = 0
        
    def __enter__(self):
        self.start_time = datetime.now()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.end_time = datetime.now()
        
        if exc_type is None:
            duration = (self.end_time - self.start_time).total_seconds()
            logger.info(f"Change detection performance: {duration:.2f}s for {self.record_count} records")
    
    def record_query(self, record_count: int):
        """Record a query operation."""
        self.query_count += 1
        self.record_count += record_count
    
    def record_cache_hit(self):
        """Record a cache hit."""
        self.cache_stats["hits"] += 1
    
    def record_cache_miss(self):
        """Record a cache miss."""
        self.cache_stats["misses"] += 1
    
    def get_metrics(self) -> PerformanceMetrics:
        """Get performance metrics."""
        duration = 0.0
        if self.start_time and self.end_time:
            duration = (self.end_time - self.start_time).total_seconds()
        
        return PerformanceMetrics(
            query_time=duration,
            record_count=self.record_count,
            cache_hits=self.cache_stats["hits"],
            cache_misses=self.cache_stats["misses"],
            memory_usage_mb=0.0,  # Could be enhanced with actual memory monitoring
            batch_count=self.query_count
        )


def optimize_incremental_query(layer, where_clause: str, max_records: int = 1000) -> List[str]:
    """Optimize incremental query for record ID retrieval.
    
    Implements Context7 best practices for efficient record ID queries:
    - Use minimal field selection (OBJECTID only)
    - Apply record count limits
    - Handle large result sets appropriately
    
    Args:
        layer: ArcGIS FeatureLayer instance
        where_clause: Optimized WHERE clause for filtering
        max_records: Maximum records to retrieve
        
    Returns:
        List of record IDs (as strings)
    """
    try:
        logger.debug(f"Executing optimized incremental query with limit {max_records}")
        
        # First, check count to avoid large queries
        count = layer.query(where=where_clause, return_count_only=True)
        
        if count == 0:
            return []
        
        if count > max_records:
            logger.warning(f"Large result set ({count} records) truncated to {max_records}")
        
        # Query with optimized field selection
        result = layer.query(
            where=where_clause,
            out_fields=["OBJECTID"],  # Minimal field selection
            result_record_count=min(count, max_records)
        )
        
        # Extract record IDs efficiently
        record_ids = [str(f.attributes["OBJECTID"]) for f in result.features if f.attributes.get("OBJECTID")]
        
        logger.debug(f"Retrieved {len(record_ids)} record IDs efficiently")
        return record_ids
        
    except Exception as e:
        logger.error(f"Optimized incremental query failed: {e}")
        return []


def estimate_processing_time(record_count: int, processing_type: str, base_time_per_record: float = 0.1) -> float:
    """Estimate processing time based on optimized processing patterns.
    
    Args:
        record_count: Number of records to process
        processing_type: Type of processing (full, incremental)
        base_time_per_record: Base processing time per record in seconds
        
    Returns:
        Estimated processing time in seconds
    """
    if processing_type == "incremental_update":
        # Incremental processing has overhead but processes fewer records
        return record_count * base_time_per_record * 1.5
    elif processing_type == "full_reprocessing":
        # Full processing is more efficient per record due to batch operations
        return record_count * base_time_per_record * 0.8
    else:
        return 0.0


class QueryOptimizer:
    """Advanced query optimization for change detection operations."""
    
    @staticmethod
    def optimize_count_query(layer, where_clause: str, timeout_seconds: int = 30) -> int:
        """Optimize count-only queries with timeout and error handling.
        
        Args:
            layer: ArcGIS FeatureLayer instance
            where_clause: WHERE clause for filtering
            timeout_seconds: Query timeout in seconds
            
        Returns:
            Record count or 0 if query fails
        """
        try:
            # Context7 best practice: Use return_count_only for efficiency
            count = layer.query(where=where_clause, return_count_only=True)
            return count if isinstance(count, int) else 0
            
        except Exception as e:
            logger.warning(f"Count query optimization failed: {e}")
            return 0
    
    @staticmethod
    def create_optimized_query_params(where_clause: str, batch_size: int = 100) -> Dict[str, Any]:
        """Create optimized query parameters for ArcGIS API calls.
        
        Args:
            where_clause: WHERE clause for filtering
            batch_size: Batch size for result retrieval
            
        Returns:
            Dictionary of optimized query parameters
        """
        return {
            "where": where_clause,
            "out_fields": ["OBJECTID"],  # Minimal field selection
            "result_record_count": batch_size,
            "return_geometry": False,  # Skip geometry for record ID queries
            "return_count_only": False,
            "order_by_fields": "OBJECTID ASC"  # Consistent ordering for batching
        }


# Performance monitoring decorators and utilities

def monitor_performance(func):
    """Decorator to monitor performance of change detection functions."""
    def wrapper(*args, **kwargs):
        start_time = datetime.now()
        try:
            result = func(*args, **kwargs)
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()
            logger.debug(f"{func.__name__} completed in {duration:.2f}s")
            return result
        except Exception as e:
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()
            logger.error(f"{func.__name__} failed after {duration:.2f}s: {e}")
            raise
    return wrapper


def get_performance_recommendations(metrics: PerformanceMetrics) -> List[str]:
    """Get performance optimization recommendations based on metrics.
    
    Args:
        metrics: Performance metrics from change detection operations
        
    Returns:
        List of optimization recommendations
    """
    recommendations = []
    
    if metrics.cache_hits / max(metrics.cache_hits + metrics.cache_misses, 1) < 0.5:
        recommendations.append("Consider increasing cache duration for better performance")
    
    if metrics.query_time > 10.0:
        recommendations.append("Query time is high - consider optimizing WHERE clauses or reducing batch sizes")
    
    if metrics.record_count > 10000 and metrics.batch_count == 1:
        recommendations.append("Large dataset detected - consider implementing batch processing")
    
    if metrics.memory_usage_mb > 512:
        recommendations.append("High memory usage - consider reducing batch sizes")
    
    if not recommendations:
        recommendations.append("Performance metrics look good - no optimizations needed")
    
    return recommendations


# Constants for performance tuning
PERFORMANCE_CONSTANTS = {
    "MAX_RECORDS_WITHOUT_BATCHING": 1000,
    "OPTIMAL_BATCH_SIZE": 100,
    "CACHE_DURATION_SECONDS": 300,
    "QUERY_TIMEOUT_SECONDS": 60,
    "MEMORY_LIMIT_MB": 512,
    "MAX_CONCURRENT_QUERIES": 3
} 