"""
Medical Data Validator - A comprehensive validation library for healthcare datasets.

This package provides tools for validating medical data including schema validation,
PHI/PII detection, data quality checks, and medical code validation.
"""

__version__ = "0.2.3"
__author__ = "Rana Ehtasham Ali"
__email__ = "ranaehtashamali1@gmail.com"

from .core import (
    MedicalDataValidator,
    ValidationResult,
    ValidationIssue,
    ValidationRule,
)

from .validators import (
    SchemaValidator,
    PHIDetector,
    DataQualityChecker,
    MedicalCodeValidator,
    RangeValidator,
    DateValidator,
)

from .extensions import (
    CustomValidator,
    ValidationProfile,
    ValidationRegistry,
    MedicalProfiles,
    create_custom_validator,
    get_profile,
    list_available_profiles,
    registry,
)

from .performance import (
    ValidationCache,
    BatchValidator,
    PerformanceMonitor,
    OptimizedMedicalDataValidator,
    timed_validation,
    performance_monitor,
)

__all__ = [
    # Core classes
    "MedicalDataValidator",
    "ValidationResult", 
    "ValidationIssue",
    "ValidationRule",
    
    # Built-in validators
    "SchemaValidator",
    "PHIDetector",
    "DataQualityChecker",
    "MedicalCodeValidator",
    "RangeValidator",
    "DateValidator",
    
    # Extension framework
    "CustomValidator",
    "ValidationProfile",
    "ValidationRegistry",
    "MedicalProfiles",
    "create_custom_validator",
    "get_profile",
    "list_available_profiles",
    "registry",
    
    # Performance optimization
    "ValidationCache",
    "BatchValidator",
    "PerformanceMonitor",
    "OptimizedMedicalDataValidator",
    "timed_validation",
    "performance_monitor",
] 