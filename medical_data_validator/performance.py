"""
Performance optimization utilities for medical data validation.

This module provides caching, batch processing, and performance monitoring
for large-scale medical data validation.
"""

import copy
import time
from collections import OrderedDict
from functools import lru_cache
from typing import Any, Callable, Dict, List, Optional, Tuple, TYPE_CHECKING
import pandas as pd
from .core import ValidationRule, ValidationIssue, ValidationResult
from .utils import dataframe_fingerprint

if TYPE_CHECKING:
    from .core import MedicalDataValidator


class ValidationCache:
    """
    LRU cache for validation results to avoid re-computing identical validations.

    Uses a deterministic hashlib-based fingerprint so cache keys are stable
    across process restarts and multiple worker processes.
    """

    def __init__(self, max_size: int = 1000):
        self.max_size = max_size
        # OrderedDict gives O(1) LRU tracking: move_to_end on hit, popitem(last=False) on evict
        self._cache: OrderedDict[str, ValidationResult] = OrderedDict()
        self._hits = 0
        self._misses = 0

    def _make_key(self, data: pd.DataFrame, rule_names: List[str]) -> str:
        fp = dataframe_fingerprint(data)
        rules_part = ",".join(sorted(rule_names))
        return f"{fp}:{rules_part}"

    def get(self, data: pd.DataFrame, rule_names: List[str]) -> Optional[ValidationResult]:
        key = self._make_key(data, rule_names)
        if key in self._cache:
            self._cache.move_to_end(key)
            self._hits += 1
            return self._cache[key]
        self._misses += 1
        return None

    def set(self, data: pd.DataFrame, rule_names: List[str], result: ValidationResult) -> None:
        key = self._make_key(data, rule_names)
        if key in self._cache:
            self._cache.move_to_end(key)
        else:
            if len(self._cache) >= self.max_size:
                self._cache.popitem(last=False)  # evict least-recently used
            self._cache[key] = result

    def clear(self) -> None:
        self._cache.clear()
        self._hits = 0
        self._misses = 0

    def stats(self) -> Dict[str, Any]:
        total = self._hits + self._misses
        return {
            "size": len(self._cache),
            "max_size": self.max_size,
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": self._hits / total if total else 0.0,
        }


class BatchValidator:
    """
    Validator for processing large datasets in batches.
    
    This is useful for memory-efficient validation of very large datasets
    that don't fit in memory all at once.
    """
    
    def __init__(
        self,
        validator: "MedicalDataValidator",
        batch_size: int = 10000,
        cache: Optional[ValidationCache] = None,
    ):
        self.validator = validator
        self.batch_size = batch_size
        self.cache = cache or ValidationCache()
    
    def validate_batches(
        self, 
        data: pd.DataFrame,
        progress_callback: Optional[Callable[[int, int], None]] = None
    ) -> ValidationResult:
        """
        Validate data in batches.
        
        Args:
            data: DataFrame to validate
            progress_callback: Optional callback for progress updates
            
        Returns:
            Combined validation result from all batches
        """
        total_rows = len(data)
        total_batches = (total_rows + self.batch_size - 1) // self.batch_size
        
        # Initialize combined result
        combined_result = ValidationResult(is_valid=True)
        combined_result.summary = {
            "total_rows": total_rows,
            "total_columns": len(data.columns),
            "batch_size": self.batch_size,
            "total_batches": total_batches,
            "batch_results": []
        }
        
        for batch_num in range(total_batches):
            start_idx = batch_num * self.batch_size
            end_idx = min(start_idx + self.batch_size, total_rows)
            
            # Extract batch
            batch_data = data.iloc[start_idx:end_idx].copy()
            
            # Check cache first
            rule_names = [rule.name for rule in self.validator.rules]
            cached_result = self.cache.get(batch_data, rule_names)
            
            if cached_result:
                # Deep-copy so row-offset mutations don't corrupt the cached object
                batch_result = copy.deepcopy(cached_result)
            else:
                # Run validation on batch
                batch_result = self.validator.validate(batch_data)
                # Cache the result
                self.cache.set(batch_data, rule_names, batch_result)

            # Combine results
            for issue in batch_result.issues:
                if issue.row is not None:
                    issue.row += start_idx
                combined_result.add_issue(issue)

            # Merge compliance_report from the last batch that produced one so
            # the monitoring system always sees a compliance summary.
            batch_summary = getattr(batch_result, 'summary', {}) or {}
            if 'compliance_report' in batch_summary:
                combined_result.summary['compliance_report'] = batch_summary['compliance_report']
            if 'analytics_report' in batch_summary:
                combined_result.summary['analytics_report'] = batch_summary['analytics_report']

            # Update summary
            combined_result.summary["batch_results"].append({
                "batch_num": batch_num,
                "start_row": start_idx,
                "end_row": end_idx,
                "issues_count": len(batch_result.issues),
                "is_valid": batch_result.is_valid
            })

            # Progress callback
            if progress_callback:
                progress_callback(batch_num + 1, total_batches)

        return combined_result


class PerformanceMonitor:
    """
    Monitor and track validation performance metrics.
    """
    
    def __init__(self):
        self.metrics: Dict[str, List[float]] = {
            "validation_times": [],
            "data_sizes": [],
            "issue_counts": [],
        }
    
    def start_timer(self) -> float:
        """Start a performance timer."""
        return time.time()
    
    def record_validation(
        self, 
        start_time: float, 
        data_size: int, 
        issue_count: int
    ) -> None:
        """Record validation performance metrics."""
        duration = time.time() - start_time
        
        self.metrics["validation_times"].append(duration)
        self.metrics["data_sizes"].append(data_size)
        self.metrics["issue_counts"].append(issue_count)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get performance statistics."""
        if not self.metrics["validation_times"]:
            return {"error": "No metrics recorded"}
        
        times = self.metrics["validation_times"]
        sizes = self.metrics["data_sizes"]
        
        return {
            "total_validations": len(times),
            "average_time": sum(times) / len(times),
            "min_time": min(times),
            "max_time": max(times),
            "total_rows_processed": sum(sizes),
            "average_rows_per_second": sum(sizes) / sum(times) if sum(times) > 0 else 0,
            "recent_performance": times[-10:] if len(times) >= 10 else times
        }
    
    def reset(self) -> None:
        """Reset all metrics."""
        for key in self.metrics:
            self.metrics[key].clear()


# Global performance monitor
performance_monitor = PerformanceMonitor()


def timed_validation(
    validator: "MedicalDataValidator",
    data: pd.DataFrame,
    monitor: Optional[PerformanceMonitor] = None
) -> Tuple[ValidationResult, float]:
    """
    Run validation with timing.
    
    Args:
        validator: The validator to use
        data: Data to validate
        monitor: Optional performance monitor
        
    Returns:
        Tuple of (validation_result, duration)
    """
    monitor = monitor or performance_monitor
    start_time = monitor.start_timer()
    
    result = validator.validate(data)
    
    duration = time.time() - start_time
    monitor.record_validation(
        start_time, 
        len(data), 
        len(result.issues)
    )
    
    return result, duration


@lru_cache(maxsize=128)
def cached_rule_validation(rule_name: str, data_hash: str) -> List[ValidationIssue]:
    """
    Cache validation results for individual rules.
    
    This is useful for expensive validation operations that might
    be repeated across different datasets.
    """
    # This is a placeholder - in practice, you'd implement the actual
    # rule validation logic here
    return []


class OptimizedMedicalDataValidator:
    """
    Performance-optimized version of MedicalDataValidator.
    
    This class provides caching, batch processing, and performance monitoring
    for large-scale validation operations.
    """
    
    def __init__(
        self,
        validator: "MedicalDataValidator",
        enable_caching: bool = True,
        enable_batching: bool = False,
        batch_size: int = 10000,
        monitor_performance: bool = True,
    ):
        self.validator = validator
        self.enable_caching = enable_caching
        self.enable_batching = enable_batching
        self.batch_size = batch_size
        self.monitor_performance = monitor_performance
        
        self.cache = ValidationCache() if enable_caching else None
        self.batch_validator = BatchValidator(validator, batch_size, self.cache) if enable_batching else None
        self.monitor = PerformanceMonitor() if monitor_performance else None
    
    def validate(self, data: pd.DataFrame) -> ValidationResult:
        """Validate data with performance optimizations."""
        if self.enable_batching and len(data) > self.batch_size and self.batch_validator is not None:
            return self.batch_validator.validate_batches(data)
        
        if self.monitor_performance:
            result, duration = timed_validation(self.validator, data, self.monitor)
            return result
        
        return self.validator.validate(data)
    
    def get_performance_stats(self) -> Dict[str, Any]:
        """Get performance statistics."""
        if not self.monitor:
            return {"error": "Performance monitoring not enabled"}
        
        stats = self.monitor.get_stats()
        
        if self.cache:
            stats["cache"] = self.cache.stats()
        
        return stats
    
    def clear_cache(self) -> None:
        """Clear the validation cache."""
        if self.cache:
            self.cache.clear()
    
    def reset_performance_monitor(self) -> None:
        """Reset performance monitoring metrics."""
        if self.monitor:
            self.monitor.reset() 