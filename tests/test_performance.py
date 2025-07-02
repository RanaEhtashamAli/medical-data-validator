"""
Tests for the performance module.

This module tests caching, batch processing, and performance monitoring features.
"""

import pytest
import pandas as pd
import time
from unittest.mock import Mock, patch

from medical_data_validator.performance import (
    ValidationCache,
    BatchValidator,
    PerformanceMonitor,
    timed_validation,
    cached_rule_validation,
    OptimizedMedicalDataValidator,
    performance_monitor,
)
from medical_data_validator.core import ValidationResult, ValidationIssue, MedicalDataValidator
from medical_data_validator.validators import SchemaValidator, PHIDetector


class TestValidationCache:
    """Test ValidationCache class."""
    
    def test_cache_creation(self):
        """Test creating a validation cache."""
        cache = ValidationCache(max_size=500)
        
        assert cache.max_size == 500
        assert len(cache._cache) == 0
        assert len(cache._access_count) == 0
    
    def test_cache_get_set(self):
        """Test basic cache get and set operations."""
        cache = ValidationCache()
        df = pd.DataFrame({"col1": [1, 2, 3]})
        result = ValidationResult(is_valid=True)
        
        # Initially not in cache
        assert cache.get(df, ["rule1"]) is None
        
        # Set in cache
        cache.set(df, ["rule1"], result)
        
        # Now should be in cache
        cached_result = cache.get(df, ["rule1"])
        assert cached_result == result
    
    def test_cache_key_generation(self):
        """Test cache key generation."""
        cache = ValidationCache()
        df1 = pd.DataFrame({"col1": [1, 2, 3]})
        df2 = pd.DataFrame({"col1": [1, 2, 3]})  # Same data
        df3 = pd.DataFrame({"col1": [4, 5, 6]})  # Different data
        
        # Same data should generate same key
        key1 = cache._generate_key(cache._get_data_hash(df1), ["rule1"])
        key2 = cache._generate_key(cache._get_data_hash(df2), ["rule1"])
        assert key1 == key2
        
        # Different data should generate different key
        key3 = cache._generate_key(cache._get_data_hash(df3), ["rule1"])
        assert key1 != key3
    
    def test_cache_lru_eviction(self):
        """Test LRU eviction when cache is full."""
        cache = ValidationCache(max_size=2)
        df1 = pd.DataFrame({"col1": [1, 2, 3]})
        df2 = pd.DataFrame({"col1": [4, 5, 6]})
        df3 = pd.DataFrame({"col1": [7, 8, 9]})
        
        result1 = ValidationResult(is_valid=True)
        result2 = ValidationResult(is_valid=False)
        result3 = ValidationResult(is_valid=True)
        
        # Fill cache
        cache.set(df1, ["rule1"], result1)
        cache.set(df2, ["rule1"], result2)
        
        # Access first item to make it more recently used
        cache.get(df1, ["rule1"])
        
        # Add third item - should evict second item (least recently used)
        cache.set(df3, ["rule1"], result3)
        
        # First and third should still be in cache
        assert cache.get(df1, ["rule1"]) == result1
        assert cache.get(df3, ["rule1"]) == result3
        
        # Second should be evicted
        assert cache.get(df2, ["rule1"]) is None
    
    def test_cache_clear(self):
        """Test clearing the cache."""
        cache = ValidationCache()
        df = pd.DataFrame({"col1": [1, 2, 3]})
        result = ValidationResult(is_valid=True)
        
        cache.set(df, ["rule1"], result)
        assert len(cache._cache) == 1
        
        cache.clear()
        assert len(cache._cache) == 0
        assert len(cache._access_count) == 0
    
    def test_cache_stats(self):
        """Test cache statistics."""
        cache = ValidationCache(max_size=100)
        df = pd.DataFrame({"col1": [1, 2, 3]})
        result = ValidationResult(is_valid=True)
        
        cache.set(df, ["rule1"], result)
        cache.get(df, ["rule1"])  # Access once
        cache.get(df, ["rule1"])  # Access again
        
        stats = cache.stats()
        
        assert stats["size"] == 1
        assert stats["max_size"] == 100
        assert stats["hit_rate"] == 3  # 1 set + 2 gets
        assert len(stats["most_accessed"]) == 1


class TestBatchValidator:
    """Test BatchValidator class."""
    
    def test_batch_validator_creation(self):
        """Test creating a batch validator."""
        validator = MedicalDataValidator([SchemaValidator()])
        batch_validator = BatchValidator(validator, batch_size=5000)
        
        assert batch_validator.validator == validator
        assert batch_validator.batch_size == 5000
        assert batch_validator.cache is not None
    
    def test_batch_validation_small_data(self):
        """Test batch validation with data smaller than batch size."""
        validator = MedicalDataValidator([SchemaValidator()])
        batch_validator = BatchValidator(validator, batch_size=10000)
        
        df = pd.DataFrame({"col1": [1, 2, 3, 4, 5]})
        
        result = batch_validator.validate_batches(df)
        
        assert isinstance(result, ValidationResult)
        assert result.is_valid is True
        assert result.summary["total_rows"] == 5
        assert result.summary["total_batches"] == 1
    
    def test_batch_validation_large_data(self):
        """Test batch validation with data larger than batch size."""
        validator = MedicalDataValidator([SchemaValidator()])
        batch_validator = BatchValidator(validator, batch_size=3)
        
        df = pd.DataFrame({"col1": [1, 2, 3, 4, 5, 6, 7]})
        
        result = batch_validator.validate_batches(df)
        
        assert isinstance(result, ValidationResult)
        assert result.summary["total_rows"] == 7
        assert result.summary["total_batches"] == 3
        assert len(result.summary["batch_results"]) == 3
    
    def test_batch_validation_with_issues(self):
        """Test batch validation with validation issues."""
        validator = MedicalDataValidator([PHIDetector()])
        batch_validator = BatchValidator(validator, batch_size=2)
        
        df = pd.DataFrame({
            "patient_name": ["John", "Jane", "Bob", "Alice"],
            "ssn": ["123-45-6789", "987-65-4321", "555-12-3456", "111-22-3333"]
        })
        
        result = batch_validator.validate_batches(df)
        
        # Should have PHI detection issues
        assert len(result.issues) > 0
        assert result.summary["total_batches"] == 2
    
    def test_batch_validation_with_progress_callback(self):
        """Test batch validation with progress callback."""
        validator = MedicalDataValidator([SchemaValidator()])
        batch_validator = BatchValidator(validator, batch_size=2)
        
        df = pd.DataFrame({"col1": [1, 2, 3, 4]})
        
        progress_calls = []
        def progress_callback(current, total):
            progress_calls.append((current, total))
        
        result = batch_validator.validate_batches(df, progress_callback)
        
        assert len(progress_calls) == 2
        assert progress_calls[0] == (1, 2)
        assert progress_calls[1] == (2, 2)
    
    def test_batch_validation_row_adjustment(self):
        """Test that row numbers are adjusted correctly across batches."""
        validator = MedicalDataValidator([SchemaValidator()])
        batch_validator = BatchValidator(validator, batch_size=2)
        
        # Create a custom validator that returns issues with batch-local row numbers
        def custom_validator(df):
            issues = []
            for batch_row, (i, row) in enumerate(df.iterrows()):
                issues.append(ValidationIssue(
                    severity="warning",
                    message=f"Issue at row {batch_row}",
                    row=batch_row,
                    rule_name="CustomValidator"
                ))
            return issues
        
        validator.add_validator("custom", custom_validator)
        
        df = pd.DataFrame({"col1": [1, 2, 3, 4]})
        
        result = batch_validator.validate_batches(df)
        
        # Should have 4 issues, one for each row
        assert len(result.issues) == 4
        
        # Row numbers should be adjusted to global positions
        row_numbers = [issue.row for issue in result.issues if issue.row is not None]
        assert set(row_numbers) == {0, 1, 2, 3}


class TestPerformanceMonitor:
    """Test PerformanceMonitor class."""
    
    def test_monitor_creation(self):
        """Test creating a performance monitor."""
        monitor = PerformanceMonitor()
        
        assert len(monitor.metrics["validation_times"]) == 0
        assert len(monitor.metrics["data_sizes"]) == 0
        assert len(monitor.metrics["issue_counts"]) == 0
    
    def test_start_timer(self):
        """Test starting a timer."""
        monitor = PerformanceMonitor()
        start_time = monitor.start_timer()
        
        assert isinstance(start_time, float)
        assert start_time > 0
    
    def test_record_validation(self):
        """Test recording validation metrics."""
        monitor = PerformanceMonitor()
        start_time = monitor.start_timer()
        
        # Simulate some processing time
        time.sleep(0.01)
        
        monitor.record_validation(start_time, 1000, 5)
        
        assert len(monitor.metrics["validation_times"]) == 1
        assert len(monitor.metrics["data_sizes"]) == 1
        assert len(monitor.metrics["issue_counts"]) == 1
        
        assert monitor.metrics["data_sizes"][0] == 1000
        assert monitor.metrics["issue_counts"][0] == 5
    
    def test_get_stats_empty(self):
        """Test getting stats when no metrics recorded."""
        monitor = PerformanceMonitor()
        stats = monitor.get_stats()
        
        assert "error" in stats
        assert "No metrics recorded" in stats["error"]
    
    def test_get_stats_with_data(self):
        """Test getting stats with recorded metrics."""
        monitor = PerformanceMonitor()
        
        # Record some test data
        monitor.metrics["validation_times"] = [1.0, 2.0, 3.0]
        monitor.metrics["data_sizes"] = [100, 200, 300]
        monitor.metrics["issue_counts"] = [5, 10, 15]
        
        stats = monitor.get_stats()
        
        assert stats["total_validations"] == 3
        assert stats["average_time"] == 2.0
        assert stats["min_time"] == 1.0
        assert stats["max_time"] == 3.0
        assert stats["total_rows_processed"] == 600
        assert stats["average_rows_per_second"] == 100.0  # 600/6.0
    
    def test_reset(self):
        """Test resetting the monitor."""
        monitor = PerformanceMonitor()
        
        # Add some data
        monitor.metrics["validation_times"] = [1.0, 2.0]
        monitor.metrics["data_sizes"] = [100, 200]
        monitor.metrics["issue_counts"] = [5, 10]
        
        monitor.reset()
        
        assert len(monitor.metrics["validation_times"]) == 0
        assert len(monitor.metrics["data_sizes"]) == 0
        assert len(monitor.metrics["issue_counts"]) == 0


class TestTimedValidation:
    """Test timed_validation function."""
    
    def test_timed_validation(self):
        """Test timed validation function."""
        validator = MedicalDataValidator([SchemaValidator()])
        df = pd.DataFrame({"col1": [1, 2, 3]})
        
        result, duration = timed_validation(validator, df)
        
        assert isinstance(result, ValidationResult)
        assert isinstance(duration, float)
        assert duration >= 0.0  # Duration should be non-negative
        assert result.is_valid is True
    
    def test_timed_validation_with_custom_monitor(self):
        """Test timed validation with custom monitor."""
        validator = MedicalDataValidator([SchemaValidator()])
        df = pd.DataFrame({"col1": [1, 2, 3]})
        monitor = PerformanceMonitor()
        
        result, duration = timed_validation(validator, df, monitor)
        
        assert isinstance(result, ValidationResult)
        assert isinstance(duration, float)
        assert len(monitor.metrics["validation_times"]) == 1
        assert monitor.metrics["data_sizes"][0] == 3


class TestCachedRuleValidation:
    """Test cached_rule_validation function."""
    
    def test_cached_rule_validation(self):
        """Test cached rule validation function."""
        issues = cached_rule_validation("test_rule", "test_hash")
        
        assert isinstance(issues, list)
        # This is a placeholder function, so it should return empty list
        assert len(issues) == 0


class TestOptimizedMedicalDataValidator:
    """Test OptimizedMedicalDataValidator class."""
    
    def test_optimized_validator_creation(self):
        """Test creating an optimized validator."""
        base_validator = MedicalDataValidator([SchemaValidator()])
        optimized = OptimizedMedicalDataValidator(
            base_validator,
            enable_caching=True,
            enable_batching=False,
            batch_size=5000,
            monitor_performance=True
        )
        
        assert optimized.validator == base_validator
        assert optimized.enable_caching is True
        assert optimized.enable_batching is False
        assert optimized.batch_size == 5000
        assert optimized.monitor_performance is True
        assert optimized.cache is not None
        assert optimized.batch_validator is None
        assert optimized.monitor is not None
    
    def test_optimized_validation_without_batching(self):
        """Test optimized validation without batching."""
        base_validator = MedicalDataValidator([SchemaValidator()])
        optimized = OptimizedMedicalDataValidator(
            base_validator,
            enable_caching=True,
            enable_batching=False,
            monitor_performance=True
        )
        
        df = pd.DataFrame({"col1": [1, 2, 3]})
        
        result = optimized.validate(df)
        
        assert isinstance(result, ValidationResult)
        assert result.is_valid is True
    
    def test_optimized_validation_with_batching(self):
        """Test optimized validation with batching."""
        base_validator = MedicalDataValidator([SchemaValidator()])
        optimized = OptimizedMedicalDataValidator(
            base_validator,
            enable_caching=True,
            enable_batching=True,
            batch_size=2,
            monitor_performance=True
        )
        
        df = pd.DataFrame({"col1": [1, 2, 3, 4, 5]})
        
        result = optimized.validate(df)
        
        assert isinstance(result, ValidationResult)
        assert result.is_valid is True
        assert result.summary["total_batches"] == 3
    
    def test_optimized_validation_without_monitoring(self):
        """Test optimized validation without performance monitoring."""
        base_validator = MedicalDataValidator([SchemaValidator()])
        optimized = OptimizedMedicalDataValidator(
            base_validator,
            enable_caching=True,
            enable_batching=False,
            monitor_performance=False
        )
        
        df = pd.DataFrame({"col1": [1, 2, 3]})
        
        result = optimized.validate(df)
        
        assert isinstance(result, ValidationResult)
        assert result.is_valid is True
    
    def test_get_performance_stats(self):
        """Test getting performance statistics."""
        base_validator = MedicalDataValidator([SchemaValidator()])
        optimized = OptimizedMedicalDataValidator(
            base_validator,
            enable_caching=True,
            enable_batching=False,
            monitor_performance=True
        )
        
        # Run some validations
        df = pd.DataFrame({"col1": [1, 2, 3]})
        optimized.validate(df)
        optimized.validate(df)
        
        stats = optimized.get_performance_stats()
        
        assert "total_validations" in stats
        assert stats["total_validations"] == 2
        assert "cache" in stats
    
    def test_get_performance_stats_no_monitoring(self):
        """Test getting performance stats when monitoring is disabled."""
        base_validator = MedicalDataValidator([SchemaValidator()])
        optimized = OptimizedMedicalDataValidator(
            base_validator,
            enable_caching=True,
            enable_batching=False,
            monitor_performance=False
        )
        
        stats = optimized.get_performance_stats()
        
        assert "error" in stats
        assert "not enabled" in stats["error"]
    
    def test_clear_cache(self):
        """Test clearing the cache."""
        base_validator = MedicalDataValidator([SchemaValidator()])
        optimized = OptimizedMedicalDataValidator(
            base_validator,
            enable_caching=True,
            enable_batching=False,
            monitor_performance=False
        )
        
        # Add some data to cache
        df = pd.DataFrame({"col1": [1, 2, 3]})
        optimized.validate(df)
        
        # Clear cache
        optimized.clear_cache()
        
        # Cache should be empty
        assert optimized.cache is not None
        cache_stats = optimized.cache.stats()
        assert cache_stats["size"] == 0
    
    def test_reset_performance_monitor(self):
        """Test resetting performance monitor."""
        base_validator = MedicalDataValidator([SchemaValidator()])
        optimized = OptimizedMedicalDataValidator(
            base_validator,
            enable_caching=True,
            enable_batching=False,
            monitor_performance=True
        )
        
        # Run some validations
        df = pd.DataFrame({"col1": [1, 2, 3]})
        optimized.validate(df)
        
        # Reset monitor
        optimized.reset_performance_monitor()
        
        # Monitor should be reset
        assert optimized.monitor is not None
        stats = optimized.monitor.get_stats()
        assert "error" in stats  # No metrics after reset


class TestGlobalPerformanceMonitor:
    """Test the global performance monitor."""
    
    def test_global_monitor_exists(self):
        """Test that global performance monitor exists."""
        assert performance_monitor is not None
        assert isinstance(performance_monitor, PerformanceMonitor)


if __name__ == "__main__":
    pytest.main([__file__]) 