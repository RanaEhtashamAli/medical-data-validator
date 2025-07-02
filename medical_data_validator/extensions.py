"""
Extension framework for custom validators and validation profiles.

This module provides utilities for creating custom validation rules
and pre-configured validation profiles for different medical domains.
"""

from typing import Any, Callable, Dict, List, Optional, Union, TYPE_CHECKING
import pandas as pd
from .core import ValidationRule, ValidationIssue

if TYPE_CHECKING:
    from .core import MedicalDataValidator


class CustomValidator(ValidationRule):
    """
    A flexible validator that uses a custom function to validate data.
    
    This allows users to create their own validation logic without
    subclassing ValidationRule.
    """
    
    def __init__(
        self,
        validator_func: Callable[[pd.DataFrame], List[ValidationIssue]],
        name: str = "CustomValidator",
        description: str = "Custom validation rule",
        severity: str = "error",
    ):
        super().__init__(name=name, description=description, severity=severity)
        self.validator_func = validator_func
    
    def validate(self, data: pd.DataFrame) -> List[ValidationIssue]:
        """Run the custom validation function."""
        return self.validator_func(data)


class ValidationProfile:
    """
    A pre-configured set of validation rules for specific medical domains.
    
    Profiles provide convenient, domain-specific validation configurations
    that can be easily applied to datasets.
    """
    
    def __init__(
        self,
        name: str,
        description: str,
        rules: List[ValidationRule],
        metadata: Optional[Dict[str, Any]] = None,
    ):
        self.name = name
        self.description = description
        self.rules = rules
        self.metadata = metadata or {}
    
    def create_validator(self) -> "MedicalDataValidator":
        """Create a MedicalDataValidator with this profile's rules."""
        from .core import MedicalDataValidator
        return MedicalDataValidator(self.rules)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert profile to dictionary representation."""
        return {
            "name": self.name,
            "description": self.description,
            "rule_count": len(self.rules),
            "rules": [rule.name for rule in self.rules],
            "metadata": self.metadata,
        }


# Pre-configured validation profiles
class MedicalProfiles:
    """Collection of pre-configured validation profiles for medical domains."""
    
    @staticmethod
    def clinical_trials() -> ValidationProfile:
        """Profile for clinical trial data validation."""
        from .validators import (
            SchemaValidator,
            PHIDetector,
            DataQualityChecker,
            RangeValidator,
            DateValidator,
        )
        
        rules = [
            SchemaValidator(
                required_columns=["subject_id", "visit_date", "treatment_group"],
                column_types={"subject_id": "string", "visit_date": "datetime"}
            ),
            PHIDetector(),
            DataQualityChecker(),
            DateValidator(
                date_columns=["visit_date", "screening_date"],
                min_date="2000-01-01"
            ),
            RangeValidator(ranges={
                "age": {"min": 18, "max": 100},
                "bmi": {"min": 15, "max": 60},
            })
        ]
        
        return ValidationProfile(
            name="Clinical Trials",
            description="Comprehensive validation for clinical trial datasets",
            rules=rules,
            metadata={
                "domain": "clinical_research",
                "compliance": ["ICH-GCP", "FDA-21-CFR-11"],
                "data_types": ["demographics", "vitals", "lab_results"]
            }
        )
    
    @staticmethod
    def electronic_health_records() -> ValidationProfile:
        """Profile for electronic health records validation."""
        from .validators import (
            SchemaValidator,
            PHIDetector,
            DataQualityChecker,
            MedicalCodeValidator,
            DateValidator,
        )
        
        rules = [
            SchemaValidator(
                required_columns=["patient_id", "encounter_date"],
                column_types={"patient_id": "string", "encounter_date": "datetime"}
            ),
            PHIDetector(),
            DataQualityChecker(),
            MedicalCodeValidator(code_columns={
                "diagnosis_code": "icd10",
                "procedure_code": "cpt",
                "medication_code": "ndc"
            }),
            DateValidator(
                date_columns=["encounter_date", "birth_date"],
                min_date="1900-01-01"
            )
        ]
        
        return ValidationProfile(
            name="Electronic Health Records",
            description="Validation for EHR/EMR datasets",
            rules=rules,
            metadata={
                "domain": "healthcare",
                "compliance": ["HIPAA", "HITECH"],
                "data_types": ["demographics", "diagnoses", "procedures", "medications"]
            }
        )
    
    @staticmethod
    def medical_imaging() -> ValidationProfile:
        """Profile for medical imaging metadata validation."""
        from .validators import (
            SchemaValidator,
            PHIDetector,
            DataQualityChecker,
            RangeValidator,
            DateValidator,
        )
        
        rules = [
            SchemaValidator(
                required_columns=["image_id", "patient_id", "study_date"],
                column_types={"image_id": "string", "patient_id": "string"}
            ),
            PHIDetector(),
            DataQualityChecker(),
            DateValidator(
                date_columns=["study_date", "acquisition_date"],
                min_date="1990-01-01"
            ),
            RangeValidator(ranges={
                "pixel_spacing": {"min": 0.1, "max": 10.0},
                "slice_thickness": {"min": 0.1, "max": 50.0},
            })
        ]
        
        return ValidationProfile(
            name="Medical Imaging",
            description="Validation for medical imaging metadata",
            rules=rules,
            metadata={
                "domain": "radiology",
                "compliance": ["DICOM", "HIPAA"],
                "data_types": ["imaging_metadata", "patient_info"]
            }
        )
    
    @staticmethod
    def laboratory_data() -> ValidationProfile:
        """Profile for laboratory test data validation."""
        from .validators import (
            SchemaValidator,
            PHIDetector,
            DataQualityChecker,
            MedicalCodeValidator,
            RangeValidator,
            DateValidator,
        )
        
        rules = [
            SchemaValidator(
                required_columns=["patient_id", "test_date", "test_code"],
                column_types={"patient_id": "string", "test_date": "datetime"}
            ),
            PHIDetector(),
            DataQualityChecker(),
            MedicalCodeValidator(code_columns={
                "test_code": "loinc",
                "diagnosis_code": "icd10"
            }),
            RangeValidator(ranges={
                "test_value": {"min": -1000, "max": 10000},  # Generic range
            }),
            DateValidator(
                date_columns=["test_date", "collection_date"],
                min_date="2000-01-01"
            )
        ]
        
        return ValidationProfile(
            name="Laboratory Data",
            description="Validation for laboratory test results",
            rules=rules,
            metadata={
                "domain": "laboratory",
                "compliance": ["CLIA", "CAP"],
                "data_types": ["lab_results", "test_metadata"]
            }
        )


class ValidationRegistry:
    """
    Registry for managing custom validators and profiles.
    
    This allows users to register and reuse custom validation logic
    across different projects.
    """
    
    def __init__(self):
        self._validators: Dict[str, ValidationRule] = {}
        self._profiles: Dict[str, ValidationProfile] = {}
    
    def register_validator(self, name: str, validator: ValidationRule) -> None:
        """Register a custom validator."""
        self._validators[name] = validator
    
    def register_profile(self, name: str, profile: ValidationProfile) -> None:
        """Register a validation profile."""
        self._profiles[name] = profile
    
    def get_validator(self, name: str) -> Optional[ValidationRule]:
        """Get a registered validator by name."""
        return self._validators.get(name)
    
    def get_profile(self, name: str) -> Optional[ValidationProfile]:
        """Get a registered profile by name."""
        return self._profiles.get(name)
    
    def list_validators(self) -> List[str]:
        """List all registered validator names."""
        return list(self._validators.keys())
    
    def list_profiles(self) -> List[str]:
        """List all registered profile names."""
        return list(self._profiles.keys())
    
    def create_validator_from_profile(self, profile_name: str) -> Optional["MedicalDataValidator"]:
        """Create a validator from a registered profile."""
        profile = self.get_profile(profile_name)
        if profile:
            return profile.create_validator()
        return None


# Global registry instance
registry = ValidationRegistry()

# Register built-in profiles
registry.register_profile("clinical_trials", MedicalProfiles.clinical_trials())
registry.register_profile("ehr", MedicalProfiles.electronic_health_records())
registry.register_profile("imaging", MedicalProfiles.medical_imaging())
registry.register_profile("lab", MedicalProfiles.laboratory_data())


def create_custom_validator(
    func: Callable[[pd.DataFrame], List[ValidationIssue]],
    name: str = "CustomValidator",
    description: str = "Custom validation rule",
    severity: str = "error",
) -> CustomValidator:
    """
    Convenience function to create a custom validator.
    
    Args:
        func: Function that takes a DataFrame and returns ValidationIssues
        name: Name of the validator
        description: Description of what the validator does
        severity: Default severity for issues (error, warning, info)
    
    Returns:
        CustomValidator instance
    """
    return CustomValidator(func, name, description, severity)


def get_profile(name: str) -> Optional[ValidationProfile]:
    """
    Get a validation profile by name.
    
    Args:
        name: Name of the profile (clinical_trials, ehr, imaging, lab)
    
    Returns:
        ValidationProfile or None if not found
    """
    return registry.get_profile(name)


def list_available_profiles() -> List[str]:
    """
    List all available validation profiles.
    
    Returns:
        List of profile names
    """
    return registry.list_profiles() 