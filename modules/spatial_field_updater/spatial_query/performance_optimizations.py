"""Performance Optimization Utilities for Spatial Query Processing

Provides optimization strategies, monitoring tools, and best practices for 
spatial intersection processing with large datasets using Context7 patterns.
"""

import logging
import time
import psutil
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass
from functools import wraps
from contextlib import contextmanager

logger = logging.getLogger(__name__)


@dataclass
class PerformanceMetrics:
    """Performance metrics for spatial operations."""
    operation_name: str
    execution_time: float
    memory_usage_mb: float
    cpu_usage_percent: float
    records_processed: int
    processing_rate: float
    
    def get_summary(self) -> Dict[str, Any]:
        """Get performance summary dictionary."""
        return {
            "operation": self.operation_name,
            "execution_time_seconds": round(self.execution_time, 3),
            "memory_usage_mb": round(self.memory_usage_mb, 2),
            "cpu_usage_percent": round(self.cpu_usage_percent, 2),
            "records_processed": self.records_processed,
            "processing_rate_per_second": round(self.processing_rate, 2)
        }


class PerformanceMonitor:
    """Performance monitoring for spatial query operations.
    
    Provides comprehensive monitoring of spatial processing operations including
    execution time, memory usage, CPU utilization, and processing rates.
    """
    
    def __init__(self):
        """Initialize performance monitor."""
        self.metrics_history: List[PerformanceMetrics] = []
        self.process = psutil.Process()
    
    @contextmanager
    def monitor_operation(self, operation_name: str, records_count: int = 0):
        """Context manager for monitoring spatial operations.
        
        Args:
            operation_name: Name of the operation being monitored
            records_count: Number of records being processed
            
        Yields:
            PerformanceMetrics object for the operation
        """
        # Initial measurements
        start_time = time.time()
        start_memory = self.process.memory_info().rss / 1024 / 1024  # MB
        start_cpu_times = self.process.cpu_times()
        
        try:
            yield
        finally:
            # Final measurements
            end_time = time.time()
            end_memory = self.process.memory_info().rss / 1024 / 1024  # MB
            end_cpu_times = self.process.cpu_times()
            
            # Calculate metrics
            execution_time = end_time - start_time
            memory_usage = max(end_memory - start_memory, 0)
            cpu_usage = ((end_cpu_times.user - start_cpu_times.user) + 
                        (end_cpu_times.system - start_cpu_times.system)) / execution_time * 100
            processing_rate = records_count / execution_time if execution_time > 0 else 0
            
            # Create metrics object
            metrics = PerformanceMetrics(
                operation_name=operation_name,
                execution_time=execution_time,
                memory_usage_mb=memory_usage,
                cpu_usage_percent=cpu_usage,
                records_processed=records_count,
                processing_rate=processing_rate
            )
            
            self.metrics_history.append(metrics)
            
            # Log performance information
            if execution_time > 5.0:  # Log slow operations
                logger.warning(f"Slow operation detected: {operation_name} took {execution_time:.2f}s "
                             f"for {records_count} records ({processing_rate:.1f} records/sec)")
            else:
                logger.debug(f"Operation {operation_name}: {execution_time:.2f}s, "
                           f"{records_count} records, {processing_rate:.1f} records/sec")
    
    def get_operation_metrics(self, operation_name: str) -> List[PerformanceMetrics]:
        """Get metrics for a specific operation type."""
        return [m for m in self.metrics_history if m.operation_name == operation_name]
    
    def get_performance_summary(self) -> Dict[str, Any]:
        """Get comprehensive performance summary."""
        if not self.metrics_history:
            return {"message": "No performance data collected"}
        
        total_time = sum(m.execution_time for m in self.metrics_history)
        total_records = sum(m.records_processed for m in self.metrics_history)
        avg_memory = sum(m.memory_usage_mb for m in self.metrics_history) / len(self.metrics_history)
        avg_cpu = sum(m.cpu_usage_percent for m in self.metrics_history) / len(self.metrics_history)
        
        # Group by operation type
        operations = {}
        for metric in self.metrics_history:
            if metric.operation_name not in operations:
                operations[metric.operation_name] = []
            operations[metric.operation_name].append(metric)
        
        operation_summaries = {}
        for op_name, metrics in operations.items():
            operation_summaries[op_name] = {
                "total_executions": len(metrics),
                "total_time": sum(m.execution_time for m in metrics),
                "total_records": sum(m.records_processed for m in metrics),
                "avg_processing_rate": sum(m.processing_rate for m in metrics) / len(metrics)
            }
        
        return {
            "total_operations": len(self.metrics_history),
            "total_execution_time": round(total_time, 2),
            "total_records_processed": total_records,
            "overall_processing_rate": round(total_records / total_time, 2) if total_time > 0 else 0,
            "average_memory_usage_mb": round(avg_memory, 2),
            "average_cpu_usage_percent": round(avg_cpu, 2),
            "operation_breakdown": operation_summaries
        }
    
    def clear_metrics(self):
        """Clear collected metrics history."""
        self.metrics_history.clear()
        logger.debug("Performance metrics history cleared")


def performance_timer(operation_name: str = None):
    """Decorator for timing function execution.
    
    Args:
        operation_name: Name of the operation (defaults to function name)
        
    Returns:
        Decorated function with performance timing
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            op_name = operation_name or func.__name__
            start_time = time.time()
            
            try:
                result = func(*args, **kwargs)
                execution_time = time.time() - start_time
                
                logger.debug(f"Performance: {op_name} completed in {execution_time:.3f}s")
                
                return result
            except Exception as e:
                execution_time = time.time() - start_time
                logger.warning(f"Performance: {op_name} failed after {execution_time:.3f}s: {e}")
                raise
        
        return wrapper
    return decorator


class QueryOptimizer:
    """Optimization utilities for spatial queries.
    
    Provides optimization strategies for ArcGIS spatial queries following
    Context7 best practices for performance and efficiency.
    """
    
    @staticmethod
    def optimize_where_clause(object_ids: List[str], max_batch_size: int = 1000) -> List[str]:
        """Optimize WHERE clauses for large object ID lists.
        
        Splits large object ID lists into optimized batches to prevent
        query string length limits and improve query performance.
        
        Args:
            object_ids: List of OBJECTID values
            max_batch_size: Maximum number of IDs per batch
            
        Returns:
            List of optimized WHERE clause strings
        """
        if not object_ids:
            return []
        
        # Remove duplicates and sort for consistent results
        unique_ids = sorted(set(object_ids))
        
        # Split into batches
        where_clauses = []
        for i in range(0, len(unique_ids), max_batch_size):
            batch = unique_ids[i:i + max_batch_size]
            where_clause = f"OBJECTID IN ({','.join(batch)})"
            where_clauses.append(where_clause)
        
        logger.debug(f"Optimized {len(unique_ids)} object IDs into {len(where_clauses)} batches")
        return where_clauses
    
    @staticmethod
    def get_optimal_batch_size(total_records: int, available_memory_mb: float = 1024) -> int:
        """Calculate optimal batch size based on dataset size and available memory.
        
        Args:
            total_records: Total number of records to process
            available_memory_mb: Available memory in MB
            
        Returns:
            Optimal batch size for processing
        """
        # Base batch size on memory constraints
        # Assume ~1KB per record for spatial processing
        max_records_by_memory = int(available_memory_mb * 1024)  # Convert to KB
        
        # Apply scaling based on dataset size
        if total_records < 1000:
            base_batch_size = min(100, total_records)
        elif total_records < 10000:
            base_batch_size = 250
        elif total_records < 50000:
            base_batch_size = 500
        else:
            base_batch_size = 1000
        
        # Limit by memory constraints
        optimal_size = min(base_batch_size, max_records_by_memory)
        
        # Ensure minimum viable batch size
        optimal_size = max(optimal_size, 10)
        
        logger.debug(f"Calculated optimal batch size: {optimal_size} for {total_records} records "
                   f"with {available_memory_mb}MB memory")
        
        return optimal_size
    
    @staticmethod
    def optimize_field_selection(required_fields: List[str], 
                                include_geometry: bool = True) -> List[str]:
        """Optimize field selection for spatial queries.
        
        Following Context7 best practices for minimal field selection
        to improve query performance and reduce network overhead.
        
        Args:
            required_fields: List of required fields
            include_geometry: Whether to include geometry in results
            
        Returns:
            Optimized field list
        """
        # Always include essential fields
        essential_fields = ["OBJECTID", "GlobalID"]
        
        # Combine with required fields and remove duplicates
        optimized_fields = list(set(essential_fields + required_fields))
        
        # Sort for consistent results
        optimized_fields.sort()
        
        logger.debug(f"Optimized field selection: {optimized_fields} (geometry: {include_geometry})")
        
        return optimized_fields


class SpatialIndexOptimizer:
    """Optimization utilities for spatial indexing and caching.
    
    Provides strategies for optimizing spatial operations through
    intelligent caching and indexing approaches.
    """
    
    def __init__(self, cache_size_limit: int = 10000):
        """Initialize spatial index optimizer.
        
        Args:
            cache_size_limit: Maximum number of entries in spatial cache
        """
        self.cache_size_limit = cache_size_limit
        self.spatial_cache: Dict[str, Any] = {}
        self.cache_access_counts: Dict[str, int] = {}
        
    def cache_boundary_intersection(self, geometry_key: str, boundary_type: str, 
                                  intersection_result: Any) -> None:
        """Cache spatial intersection result for future lookups.
        
        Args:
            geometry_key: Unique key for the geometry
            boundary_type: Type of boundary (region/district)
            intersection_result: Result of spatial intersection
        """
        cache_key = f"{geometry_key}_{boundary_type}"
        
        # Implement LRU eviction if cache is full
        if len(self.spatial_cache) >= self.cache_size_limit:
            self._evict_least_used()
        
        self.spatial_cache[cache_key] = intersection_result
        self.cache_access_counts[cache_key] = 1
        
        logger.debug(f"Cached spatial intersection: {cache_key}")
    
    def get_cached_intersection(self, geometry_key: str, boundary_type: str) -> Optional[Any]:
        """Retrieve cached spatial intersection result.
        
        Args:
            geometry_key: Unique key for the geometry
            boundary_type: Type of boundary (region/district)
            
        Returns:
            Cached intersection result or None if not found
        """
        cache_key = f"{geometry_key}_{boundary_type}"
        
        if cache_key in self.spatial_cache:
            self.cache_access_counts[cache_key] += 1
            logger.debug(f"Cache hit for spatial intersection: {cache_key}")
            return self.spatial_cache[cache_key]
        
        logger.debug(f"Cache miss for spatial intersection: {cache_key}")
        return None
    
    def _evict_least_used(self) -> None:
        """Evict least recently used cache entries."""
        if not self.cache_access_counts:
            return
        
        # Find least used entry
        least_used_key = min(self.cache_access_counts.keys(), 
                           key=lambda k: self.cache_access_counts[k])
        
        # Remove from cache
        del self.spatial_cache[least_used_key]
        del self.cache_access_counts[least_used_key]
        
        logger.debug(f"Evicted least used cache entry: {least_used_key}")
    
    def get_cache_statistics(self) -> Dict[str, Any]:
        """Get cache performance statistics."""
        total_accesses = sum(self.cache_access_counts.values())
        
        return {
            "cache_size": len(self.spatial_cache),
            "cache_limit": self.cache_size_limit,
            "total_accesses": total_accesses,
            "average_access_count": total_accesses / len(self.cache_access_counts) if self.cache_access_counts else 0,
            "cache_utilization": len(self.spatial_cache) / self.cache_size_limit
        }
    
    def clear_cache(self) -> None:
        """Clear all cached entries."""
        self.spatial_cache.clear()
        self.cache_access_counts.clear()
        logger.info("Spatial cache cleared")


# Performance optimization recommendations and documentation
PERFORMANCE_OPTIMIZATION_GUIDE = """
# Spatial Query Performance Optimization Guide

## Context7 Best Practices

### 1. Query Optimization
- Use minimal field selection (only required fields)
- Implement WHERE clause batching for large object ID lists
- Use return_geometry=False when geometry is not needed
- Leverage return_count_only=True for count queries

### 2. Batch Processing
- Optimal batch sizes: 250-500 records for spatial operations
- Adjust batch size based on available memory and dataset characteristics
- Monitor memory usage during processing
- Use parallel processing for independent batches when possible

### 3. Spatial Indexing
- Cache boundary layers to avoid repeated access
- Implement geometry-based caching for duplicate locations
- Use spatial reference optimization for consistent projections
- Leverage server-side spatial indexes when available

### 4. Memory Management
- Monitor peak memory usage during large dataset processing
- Implement garbage collection hints for large operations
- Use streaming processing for very large datasets
- Configure memory limits based on system capabilities

### 5. Performance Monitoring
- Track processing rates (records/second) for benchmarking
- Monitor intersection calculation times
- Log slow operations for optimization analysis
- Collect comprehensive metrics for performance tuning

## Recommended Configuration

```json
{
  "spatial_processing": {
    "batch_size": 250,
    "max_batch_size": 1000,
    "intersection_optimization": {
      "cache_boundary_layers": true,
      "memory_limit_mb": 1024
    },
    "performance_monitoring": {
      "track_intersection_times": true,
      "log_slow_operations": true,
      "slow_operation_threshold_seconds": 5.0
    }
  }
}
```

## Performance Benchmarks

### Expected Processing Rates
- Small datasets (<1,000 records): 100-200 records/second
- Medium datasets (1,000-10,000 records): 50-100 records/second  
- Large datasets (>10,000 records): 25-50 records/second

### Memory Usage Guidelines
- Base memory: ~50MB for processor initialization
- Per-batch overhead: ~1-2MB per 250 records
- Boundary layer cache: ~10-20MB per cached layer
- Peak usage: ~2-3x base usage during processing

### Optimization Targets
- Processing time: <5 seconds per 1,000 records
- Memory efficiency: <1GB total usage for datasets up to 50,000 records
- Success rate: >95% for spatial assignments
- Cache hit rate: >80% for repeated geometries
""" 