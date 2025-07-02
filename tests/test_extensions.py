"""
Tests for the extensions module.

This module tests custom validators, validation profiles, and the registry system.
"""

import pytest
import pandas as pd
from typing import List

from medical_data_validator.extensions import (
    CustomValidator,
    ValidationProfile,
    ValidationRegistry,
    MedicalProfiles,
    create_custom_validator,
    get_profile,
    list_available_profiles,
    registry,
)
from medical_data_validator.core import ValidationIssue, MedicalDataValidator, ValidationRule
from medical_data_validator.validators import SchemaValidator, PHIDetector


class TestCustomValidator:
    """Test CustomValidator class."""
    
    def test_custom_validator_creation(self):
        """Test creating a custom validator."""
        def custom_func(df):
            return [ValidationIssue(severity="error", message="Custom error")]
        
        validator = CustomValidator(
            validator_func=custom_func,
            name="TestValidator",
            description="Test custom validator",
            severity="error"
        )
        
        assert validator.name == "TestValidator"
        assert validator.description == "Test custom validator"
        assert validator.severity == "error"
    
    def test_custom_validator_validation(self):
        """Test custom validator validation."""
        def custom_func(df):
            issues = []
            if len(df) > 0:
                issues.append(ValidationIssue(
                    severity="warning",
                    message=f"Found {len(df)} rows",
                    rule_name="CustomValidator"
                ))
            return issues
        
        validator = CustomValidator(custom_func)
        df = pd.DataFrame({"col1": [1, 2, 3]})
        
        issues = validator.validate(df)
        
        assert len(issues) == 1
        assert issues[0].severity == "warning"
        assert "Found 3 rows" in issues[0].message
    
    def test_custom_validator_empty_result(self):
        """Test custom validator returning empty result."""
        def custom_func(df):
            return []
        
        validator = CustomValidator(custom_func)
        df = pd.DataFrame({"col1": [1, 2, 3]})
        
        issues = validator.validate(df)
        
        assert len(issues) == 0


class TestValidationProfile:
    """Test ValidationProfile class."""
    
    def test_profile_creation(self):
        """Test creating a validation profile."""
        rules: List[ValidationRule] = [SchemaValidator(), PHIDetector()]
        profile = ValidationProfile(
            name="TestProfile",
            description="Test profile",
            rules=rules,
            metadata={"domain": "test"}
        )
        
        assert profile.name == "TestProfile"
        assert profile.description == "Test profile"
        assert len(profile.rules) == 2
        assert profile.metadata["domain"] == "test"
    
    def test_profile_create_validator(self):
        """Test creating validator from profile."""
        from medical_data_validator.core import ValidationRule
        rules: List[ValidationRule] = [SchemaValidator()]
        profile = ValidationProfile("Test", "Test profile", rules)
        
        validator = profile.create_validator()
        
        assert isinstance(validator, MedicalDataValidator)
        assert len(validator.rules) == 1
        assert isinstance(validator.rules[0], SchemaValidator)
    
    def test_profile_to_dict(self):
        """Test converting profile to dictionary."""
        rules = [SchemaValidator(name="Schema"), PHIDetector(name="PHI")]
        profile = ValidationProfile(
            name="TestProfile",
            description="Test profile",
            rules=rules,
            metadata={"domain": "test"}
        )
        
        profile_dict = profile.to_dict()
        
        assert profile_dict["name"] == "TestProfile"
        assert profile_dict["description"] == "Test profile"
        assert profile_dict["rule_count"] == 2
        assert "Schema" in profile_dict["rules"]
        assert "PHI" in profile_dict["rules"]
        assert profile_dict["metadata"]["domain"] == "test"


class TestMedicalProfiles:
    """Test MedicalProfiles class."""
    
    def test_clinical_trials_profile(self):
        """Test clinical trials profile."""
        profile = MedicalProfiles.clinical_trials()
        
        assert profile.name == "Clinical Trials"
        assert "clinical trial" in profile.description.lower()
        assert len(profile.rules) > 0
        assert profile.metadata["domain"] == "clinical_research"
        assert "ICH-GCP" in profile.metadata["compliance"]
    
    def test_ehr_profile(self):
        """Test electronic health records profile."""
        profile = MedicalProfiles.electronic_health_records()
        
        assert profile.name == "Electronic Health Records"
        assert "EHR" in profile.description
        assert len(profile.rules) > 0
        assert profile.metadata["domain"] == "healthcare"
        assert "HIPAA" in profile.metadata["compliance"]
    
    def test_imaging_profile(self):
        """Test medical imaging profile."""
        profile = MedicalProfiles.medical_imaging()
        
        assert profile.name == "Medical Imaging"
        assert "imaging" in profile.description.lower()
        assert len(profile.rules) > 0
        assert profile.metadata["domain"] == "radiology"
        assert "DICOM" in profile.metadata["compliance"]
    
    def test_lab_profile(self):
        """Test laboratory data profile."""
        profile = MedicalProfiles.laboratory_data()
        
        assert profile.name == "Laboratory Data"
        assert "laboratory" in profile.description.lower()
        assert len(profile.rules) > 0
        assert profile.metadata["domain"] == "laboratory"
        assert "CLIA" in profile.metadata["compliance"]
    
    def test_profile_validation(self):
        """Test that profiles create working validators."""
        profile = MedicalProfiles.clinical_trials()
        validator = profile.create_validator()
        
        # Test with valid data - use proper date format and convert to datetime
        df = pd.DataFrame({
            "subject_id": ["001", "002", "003"],
            "visit_date": ["2020-01-01", "2020-01-02", "2020-01-03"],
            "treatment_group": ["A", "B", "A"],
            "age": [25, 30, 35],
            "bmi": [22.5, 24.0, 23.1]
        })
        
        # Convert visit_date to datetime
        df["visit_date"] = pd.to_datetime(df["visit_date"])
        
        result = validator.validate(df)
        
        # The data should be valid, but there might be warnings about PHI detection
        # Check that there are no errors (only warnings/info are acceptable)
        error_issues = [issue for issue in result.issues if issue.severity == "error"]
        assert len(error_issues) == 0, f"Found errors: {error_issues}"
    
    def test_profile_validation_with_issues(self):
        """Test profile validation with problematic data."""
        profile = MedicalProfiles.clinical_trials()
        validator = profile.create_validator()
        
        # Test with missing required columns
        df = pd.DataFrame({
            "subject_id": ["001", "002"],  # Missing visit_date and treatment_group
            "age": [25, 30]
        })
        
        result = validator.validate(df)
        
        # Should have issues due to missing required columns
        assert len(result.issues) > 0
        # Should have errors for missing required columns
        error_issues = [issue for issue in result.issues if issue.severity == "error"]
        assert len(error_issues) > 0


class TestValidationRegistry:
    """Test ValidationRegistry class."""
    
    def test_registry_creation(self):
        """Test creating a validation registry."""
        reg = ValidationRegistry()
        
        assert len(reg._validators) == 0
        assert len(reg._profiles) == 0
    
    def test_register_and_get_validator(self):
        """Test registering and retrieving validators."""
        reg = ValidationRegistry()
        validator = SchemaValidator()
        
        reg.register_validator("schema", validator)
        
        retrieved = reg.get_validator("schema")
        assert retrieved == validator
        
        # Test non-existent validator
        assert reg.get_validator("nonexistent") is None
    
    def test_register_and_get_profile(self):
        """Test registering and retrieving profiles."""
        reg = ValidationRegistry()
        profile = ValidationProfile("Test", "Test profile", [])
        
        reg.register_profile("test", profile)
        
        retrieved = reg.get_profile("test")
        assert retrieved == profile
        
        # Test non-existent profile
        assert reg.get_profile("nonexistent") is None
    
    def test_list_validators(self):
        """Test listing registered validators."""
        reg = ValidationRegistry()
        validator1 = SchemaValidator()
        validator2 = PHIDetector()
        
        reg.register_validator("schema", validator1)
        reg.register_validator("phi", validator2)
        
        validators = reg.list_validators()
        
        assert len(validators) == 2
        assert "schema" in validators
        assert "phi" in validators
    
    def test_list_profiles(self):
        """Test listing registered profiles."""
        reg = ValidationRegistry()
        profile1 = ValidationProfile("Test1", "Test profile 1", [])
        profile2 = ValidationProfile("Test2", "Test profile 2", [])
        
        reg.register_profile("test1", profile1)
        reg.register_profile("test2", profile2)
        
        profiles = reg.list_profiles()
        
        assert len(profiles) == 2
        assert "test1" in profiles
        assert "test2" in profiles
    
    def test_create_validator_from_profile(self):
        """Test creating validator from registered profile."""
        reg = ValidationRegistry()
        from medical_data_validator.core import ValidationRule
        rules: List[ValidationRule] = [SchemaValidator()]
        profile = ValidationProfile("Test", "Test profile", rules)
        
        reg.register_profile("test", profile)
        
        validator = reg.create_validator_from_profile("test")
        
        assert validator is not None
        assert isinstance(validator, MedicalDataValidator)
        assert len(validator.rules) == 1
    
    def test_create_validator_from_nonexistent_profile(self):
        """Test creating validator from non-existent profile."""
        reg = ValidationRegistry()
        
        validator = reg.create_validator_from_profile("nonexistent")
        
        assert validator is None


class TestGlobalRegistry:
    """Test the global registry instance."""
    
    def test_global_registry_has_profiles(self):
        """Test that global registry has built-in profiles."""
        profiles = registry.list_profiles()
        
        assert len(profiles) >= 4
        assert "clinical_trials" in profiles
        assert "ehr" in profiles
        assert "imaging" in profiles
        assert "lab" in profiles
    
    def test_get_built_in_profiles(self):
        """Test getting built-in profiles from global registry."""
        clinical_profile = registry.get_profile("clinical_trials")
        ehr_profile = registry.get_profile("ehr")
        
        assert clinical_profile is not None
        assert ehr_profile is not None
        assert clinical_profile.name == "Clinical Trials"
        assert ehr_profile.name == "Electronic Health Records"


class TestUtilityFunctions:
    """Test utility functions."""
    
    def test_create_custom_validator(self):
        """Test create_custom_validator function."""
        def custom_func(df):
            return [ValidationIssue(severity="error", message="Test")]
        
        validator = create_custom_validator(
            custom_func,
            name="TestValidator",
            description="Test description",
            severity="warning"
        )
        
        assert isinstance(validator, CustomValidator)
        assert validator.name == "TestValidator"
        assert validator.description == "Test description"
        assert validator.severity == "warning"
    
    def test_get_profile(self):
        """Test get_profile function."""
        profile = get_profile("clinical_trials")
        
        assert profile is not None
        assert profile.name == "Clinical Trials"
        
        # Test non-existent profile
        assert get_profile("nonexistent") is None
    
    def test_list_available_profiles(self):
        """Test list_available_profiles function."""
        profiles = list_available_profiles()
        
        assert len(profiles) >= 4
        assert "clinical_trials" in profiles
        assert "ehr" in profiles
        assert "imaging" in profiles
        assert "lab" in profiles


class TestIntegration:
    """Test integration scenarios."""
    
    def test_custom_validator_in_profile(self):
        """Test using custom validator in a profile."""
        def custom_func(df):
            return [ValidationIssue(severity="info", message="Custom check")]
        
        custom_validator = create_custom_validator(custom_func, "CustomCheck")
        from medical_data_validator.core import ValidationRule
        rules: List[ValidationRule] = [SchemaValidator(), custom_validator]
        
        profile = ValidationProfile("CustomProfile", "Profile with custom validator", rules)
        validator = profile.create_validator()
        
        df = pd.DataFrame({"col1": [1, 2, 3]})
        result = validator.validate(df)
        
        # Should have custom validator issue
        custom_issues = [issue for issue in result.issues if "Custom check" in issue.message]
        assert len(custom_issues) == 1
    
    def test_registry_with_custom_validators(self):
        """Test registry with custom validators."""
        reg = ValidationRegistry()
        
        def custom_func(df):
            return [ValidationIssue(severity="warning", message="Custom warning")]
        
        custom_validator = create_custom_validator(custom_func, "CustomWarning")
        reg.register_validator("custom_warning", custom_validator)
        
        retrieved = reg.get_validator("custom_warning")
        assert retrieved is not None
        
        df = pd.DataFrame({"col1": [1, 2, 3]})
        issues = retrieved.validate(df)
        
        assert len(issues) == 1
        assert "Custom warning" in issues[0].message


if __name__ == "__main__":
    pytest.main([__file__]) 