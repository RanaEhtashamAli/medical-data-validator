"""
Tests for the core medical data validator functionality.
"""

import pytest
import pandas as pd
from datetime import datetime

from medical_data_validator.core import (
    MedicalDataValidator,
    ValidationResult,
    ValidationIssue,
    ValidationRule,
)
from medical_data_validator.validators import (
    SchemaValidator,
    PHIDetector,
    DataQualityChecker,
    MedicalCodeValidator,
    RangeValidator,
    DateValidator,
)


class TestValidationIssue:
    """Test ValidationIssue dataclass."""
    
    def test_validation_issue_creation(self):
        """Test creating a ValidationIssue."""
        issue = ValidationIssue(
            severity="error",
            message="Test issue",
            column="test_column",
            row=1,
            value="test_value",
            rule_name="test_rule"
        )
        
        assert issue.severity == "error"
        assert issue.message == "Test issue"
        assert issue.column == "test_column"
        assert issue.row == 1
        assert issue.value == "test_value"
        assert issue.rule_name == "test_rule"
        assert isinstance(issue.timestamp, datetime)
    
    def test_validation_issue_with_none_values(self):
        """Test creating a ValidationIssue with None values."""
        issue = ValidationIssue(
            severity="warning",
            message="Test warning",
            column=None,
            row=None,
            value=None,
            rule_name=None
        )
        
        assert issue.severity == "warning"
        assert issue.message == "Test warning"
        assert issue.column is None
        assert issue.row is None
        assert issue.value is None
        assert issue.rule_name is None


class TestValidationResult:
    """Test ValidationResult class."""
    
    def test_validation_result_creation(self):
        """Test creating a ValidationResult."""
        result = ValidationResult(is_valid=True)
        
        assert result.is_valid is True
        assert len(result.issues) == 0
        assert isinstance(result.summary, dict)
        assert isinstance(result.timestamp, datetime)
    
    def test_add_issue(self):
        """Test adding issues to ValidationResult."""
        result = ValidationResult(is_valid=True)
        issue = ValidationIssue(severity="error", message="Test error")
        
        result.add_issue(issue)
        
        assert len(result.issues) == 1
        assert result.issues[0] == issue
        assert result.is_valid is False  # Error should make it invalid
    
    def test_add_warning_issue(self):
        """Test adding warning issues doesn't make result invalid."""
        result = ValidationResult(is_valid=True)
        issue = ValidationIssue(severity="warning", message="Test warning")
        
        result.add_issue(issue)
        
        assert len(result.issues) == 1
        assert result.is_valid is True  # Warning shouldn't make it invalid
    
    def test_add_info_issue(self):
        """Test adding info issues doesn't make result invalid."""
        result = ValidationResult(is_valid=True)
        issue = ValidationIssue(severity="info", message="Test info")
        
        result.add_issue(issue)
        
        assert len(result.issues) == 1
        assert result.is_valid is True  # Info shouldn't make it invalid
    
    def test_get_issues_by_severity(self):
        """Test filtering issues by severity."""
        result = ValidationResult(is_valid=True)
        
        error_issue = ValidationIssue(severity="error", message="Error")
        warning_issue = ValidationIssue(severity="warning", message="Warning")
        info_issue = ValidationIssue(severity="info", message="Info")
        
        result.add_issue(error_issue)
        result.add_issue(warning_issue)
        result.add_issue(info_issue)
        
        errors = result.get_issues_by_severity("error")
        warnings = result.get_issues_by_severity("warning")
        info = result.get_issues_by_severity("info")
        
        assert len(errors) == 1
        assert len(warnings) == 1
        assert len(info) == 1
        assert errors[0].message == "Error"
        assert warnings[0].message == "Warning"
        assert info[0].message == "Info"
    
    def test_get_issues_by_column(self):
        """Test filtering issues by column."""
        result = ValidationResult(is_valid=True)
        
        issue1 = ValidationIssue(severity="error", message="Error 1", column="col1")
        issue2 = ValidationIssue(severity="error", message="Error 2", column="col2")
        issue3 = ValidationIssue(severity="error", message="Error 3", column="col1")
        
        result.add_issue(issue1)
        result.add_issue(issue2)
        result.add_issue(issue3)
        
        col1_issues = result.get_issues_by_column("col1")
        col2_issues = result.get_issues_by_column("col2")
        
        assert len(col1_issues) == 2
        assert len(col2_issues) == 1
        assert col1_issues[0].message == "Error 1"
        assert col1_issues[1].message == "Error 3"
        assert col2_issues[0].message == "Error 2"
    
    def test_to_dict(self):
        """Test converting ValidationResult to dictionary."""
        result = ValidationResult(is_valid=True)
        issue = ValidationIssue(
            severity="error",
            message="Test issue",
            column="test_col",
            row=1,
            value="test_value",
            rule_name="test_rule"
        )
        result.add_issue(issue)
        
        result_dict = result.to_dict()
        
        assert result_dict["is_valid"] is False
        assert result_dict["total_issues"] == 1
        assert result_dict["error_count"] == 1
        assert result_dict["warning_count"] == 0
        assert result_dict["info_count"] == 0
        assert len(result_dict["issues"]) == 1
        assert result_dict["issues"][0]["severity"] == "error"
        assert result_dict["issues"][0]["message"] == "Test issue"
        assert result_dict["issues"][0]["column"] == "test_col"
        assert result_dict["issues"][0]["row"] == 1
        assert result_dict["issues"][0]["value"] == "test_value"
        assert result_dict["issues"][0]["rule_name"] == "test_rule"
    
    def test_to_dict_with_none_values(self):
        """Test to_dict with None values in issues."""
        result = ValidationResult(is_valid=True)
        issue = ValidationIssue(
            severity="warning",
            message="Test warning",
            column=None,
            row=None,
            value=None,
            rule_name=None
        )
        result.add_issue(issue)
        
        result_dict = result.to_dict()
        
        assert result_dict["is_valid"] is True
        assert result_dict["total_issues"] == 1
        assert result_dict["issues"][0]["column"] is None
        assert result_dict["issues"][0]["row"] is None
        assert result_dict["issues"][0]["value"] is None
        assert result_dict["issues"][0]["rule_name"] is None


class TestMedicalDataValidator:
    """Test MedicalDataValidator class."""
    
    def test_validator_creation(self):
        """Test creating a MedicalDataValidator."""
        validator = MedicalDataValidator()
        
        assert len(validator.rules) == 0
        assert len(validator._validators) == 0
    
    def test_validator_with_rules(self):
        """Test creating validator with initial rules."""
        rule1 = SchemaValidator()
        rule2 = PHIDetector()
        validator = MedicalDataValidator([rule1, rule2])
        
        assert len(validator.rules) == 2
        assert validator.rules[0] == rule1
        assert validator.rules[1] == rule2
    
    def test_add_rule(self):
        """Test adding rules to validator."""
        validator = MedicalDataValidator()
        rule = SchemaValidator()
        
        validator.add_rule(rule)
        
        assert len(validator.rules) == 1
        assert validator.rules[0] == rule
    
    def test_add_validator(self):
        """Test adding custom validators."""
        validator = MedicalDataValidator()
        
        def custom_validator(df):
            return []
        
        validator.add_validator("custom", custom_validator)
        
        assert len(validator._validators) == 1
        assert "custom" in validator._validators
    
    def test_validate_dataframe(self):
        """Test validating pandas DataFrame."""
        validator = MedicalDataValidator()
        df = pd.DataFrame({
            "col1": [1, 2, 3],
            "col2": ["a", "b", "c"]
        })
        
        result = validator.validate(df)
        
        assert isinstance(result, ValidationResult)
        assert result.is_valid is True
    
    def test_validate_dict(self):
        """Test validating dictionary data."""
        validator = MedicalDataValidator()
        data = {
            "col1": [1, 2, 3],
            "col2": ["a", "b", "c"]
        }
        
        result = validator.validate(data)
        
        assert isinstance(result, ValidationResult)
        assert result.is_valid is True
    
    def test_validate_list(self):
        """Test validating list of dictionaries."""
        validator = MedicalDataValidator()
        data = [
            {"col1": 1, "col2": "a"},
            {"col1": 2, "col2": "b"},
            {"col1": 3, "col2": "c"}
        ]
        
        result = validator.validate(data)
        
        assert isinstance(result, ValidationResult)
        assert result.is_valid is True
    
    def test_validate_invalid_input(self):
        """Test validating invalid input raises error."""
        validator = MedicalDataValidator()
        
        with pytest.raises(ValueError, match="Data must be"):
            validator.validate("invalid")  # type: ignore
    
    def test_rule_failure_handling(self):
        """Test handling of rule failures."""
        class FailingRule(ValidationRule):
            def __init__(self):
                super().__init__(name="FailingRule", description="A rule that always fails")
            
            def validate(self, data):
                raise Exception("Rule failed")
        
        validator = MedicalDataValidator([FailingRule()])
        df = pd.DataFrame({"col1": [1, 2, 3]})
        
        result = validator.validate(df)
        
        assert not result.is_valid
        assert len(result.issues) == 1
        assert "Rule 'FailingRule' failed" in result.issues[0].message
    
    def test_custom_validator_failure_handling(self):
        """Test handling of custom validator failures."""
        validator = MedicalDataValidator()
        
        def failing_validator(df):
            raise Exception("Validator failed")
        
        validator.add_validator("failing", failing_validator)
        df = pd.DataFrame({"col1": [1, 2, 3]})
        
        result = validator.validate(df)
        
        assert not result.is_valid
        assert len(result.issues) == 1
        assert "Custom validator 'failing' failed" in result.issues[0].message
    
    def test_custom_validator_returning_issue(self):
        """Test custom validator returning ValidationIssue."""
        validator = MedicalDataValidator()
        
        def issue_validator(df):
            return ValidationIssue(severity="error", message="Custom issue")
        
        validator.add_validator("issue", issue_validator)
        df = pd.DataFrame({"col1": [1, 2, 3]})
        
        result = validator.validate(df)
        
        assert not result.is_valid
        assert len(result.issues) == 1
        assert result.issues[0].message == "Custom issue"
    
    def test_custom_validator_returning_list(self):
        """Test custom validator returning list of issues."""
        validator = MedicalDataValidator()
        
        def list_validator(df):
            return [
                ValidationIssue(severity="warning", message="Warning 1"),
                ValidationIssue(severity="error", message="Error 1")
            ]
        
        validator.add_validator("list", list_validator)
        df = pd.DataFrame({"col1": [1, 2, 3]})
        
        result = validator.validate(df)
        
        assert not result.is_valid
        assert len(result.issues) == 2
        assert result.issues[0].message == "Warning 1"
        assert result.issues[1].message == "Error 1"
    
    def test_generate_summary(self):
        """Test summary generation."""
        validator = MedicalDataValidator()
        df = pd.DataFrame({
            "col1": [1, 2, None, 4],
            "col2": ["a", "b", "c", "d"]
        })
        result = ValidationResult(is_valid=True)
        
        summary = validator._generate_summary(df, result)
        
        assert summary["total_rows"] == 4
        assert summary["total_columns"] == 2
        assert summary["missing_values"]["col1"] == 1
        assert summary["missing_values"]["col2"] == 0
        assert summary["duplicate_rows"] == 0
        assert "col1" in summary["data_types"]
        assert "col2" in summary["data_types"]
        assert summary["validation_rules_applied"] == 0
        assert summary["custom_validators_applied"] == 0
    
    def test_get_report(self):
        """Test report generation."""
        validator = MedicalDataValidator()
        result = ValidationResult(is_valid=False)
        
        issue1 = ValidationIssue(severity="error", message="Error 1", column="col1")
        issue2 = ValidationIssue(severity="warning", message="Warning 1", column="col2")
        
        result.add_issue(issue1)
        result.add_issue(issue2)
        
        report = validator.get_report(result)
        
        assert "Medical Data Validation Report" in report
        assert "❌ INVALID" in report
        assert "Error 1" in report
        assert "Warning 1" in report
        assert "col1" in report
        assert "col2" in report
    
    def test_get_report_with_value_and_row(self):
        """Test report generation with value and row information."""
        validator = MedicalDataValidator()
        result = ValidationResult(is_valid=False)
        
        issue = ValidationIssue(
            severity="error", 
            message="Invalid value", 
            column="col1",
            row=5,
            value="bad_value"
        )
        result.add_issue(issue)
        
        report = validator.get_report(result)
        
        assert "Invalid value" in report
        assert "Location: Column: col1, Row: 5" in report
        assert "Value: bad_value" in report


class TestSchemaValidator:
    """Test SchemaValidator class."""
    
    def test_required_columns_missing(self):
        """Test validation when required columns are missing."""
        validator = SchemaValidator(required_columns=["patient_id", "age"])
        df = pd.DataFrame({"patient_id": [1, 2, 3]})  # Missing 'age'
        
        issues = validator.validate(df)
        
        assert len(issues) == 1
        assert issues[0].severity == "error"
        assert "Required column 'age' is missing" in issues[0].message
    
    def test_column_type_mismatch(self):
        """Test validation when column types don't match."""
        validator = SchemaValidator(column_types={"age": "int"})
        df = pd.DataFrame({"age": ["30", "40", "50"]})  # String instead of int
        
        issues = validator.validate(df)
        
        assert len(issues) == 1
        assert issues[0].severity == "error"
        assert "has type 'object' but expected 'int'" in issues[0].message
    
    def test_valid_schema(self):
        """Test validation with valid schema."""
        validator = SchemaValidator(
            required_columns=["patient_id", "age"],
            column_types={"age": "int"}
        )
        df = pd.DataFrame({
            "patient_id": [1, 2, 3],
            "age": [30, 40, 50]
        })
        
        issues = validator.validate(df)
        
        assert len(issues) == 0
    
    def test_column_not_in_data(self):
        """Test validation when column specified in types is not in data."""
        validator = SchemaValidator(column_types={"missing_col": "int"})
        df = pd.DataFrame({"existing_col": [1, 2, 3]})
        
        issues = validator.validate(df)
        
        assert len(issues) == 0  # Should skip missing column
    
    def test_type_compatibility(self):
        """Test type compatibility checking."""
        validator = SchemaValidator()
        
        # Test int64 compatibility
        assert validator._is_type_compatible("int64", "int")
        assert validator._is_type_compatible("int64", "integer")
        assert validator._is_type_compatible("int64", "int64")
        
        # Test float64 compatibility
        assert validator._is_type_compatible("float64", "float")
        assert validator._is_type_compatible("float64", "number")
        
        # Test object compatibility
        assert validator._is_type_compatible("object", "string")
        assert validator._is_type_compatible("object", "str")
        assert validator._is_type_compatible("object", "text")
        
        # Test datetime compatibility
        assert validator._is_type_compatible("datetime64[ns]", "datetime")
        assert validator._is_type_compatible("datetime64[ns]", "date")
        
        # Test bool compatibility
        assert validator._is_type_compatible("bool", "boolean")
        assert validator._is_type_compatible("bool", "bool")
        
        # Test incompatible types
        assert not validator._is_type_compatible("int64", "float")
        assert not validator._is_type_compatible("object", "int")


class TestPHIDetector:
    """Test PHIDetector class."""
    
    def test_phi_keyword_detection(self):
        """Test detection of PHI keywords in column names."""
        validator = PHIDetector()
        df = pd.DataFrame({
            "patient_name": ["John", "Jane"],
            "ssn": ["123-45-6789", "987-65-4321"],
            "age": [30, 40]
        })
        
        issues = validator.validate(df)
        
        # Should detect 'patient_name' and 'ssn' as potential PHI
        phi_columns = [issue.column for issue in issues if issue.column]
        assert "patient_name" in phi_columns
        assert "ssn" in phi_columns
        assert "age" not in phi_columns
    
    def test_ssn_pattern_detection(self):
        """Test detection of SSN patterns in data."""
        validator = PHIDetector()
        df = pd.DataFrame({
            "id": ["123-45-6789", "987-65-4321", "555-12-3456"],
            "name": ["John", "Jane", "Bob"]
        })
        
        issues = validator.validate(df)
        
        # Should detect SSN patterns in 'id' column
        ssn_issues = [issue for issue in issues if "SSN" in issue.message]
        assert len(ssn_issues) > 0
        assert any(issue.column is not None and "id" in issue.column for issue in ssn_issues)
    
    def test_email_pattern_detection(self):
        """Test detection of email patterns in data."""
        validator = PHIDetector()
        df = pd.DataFrame({
            "contact": ["john@example.com", "jane@test.org", "bob@company.com"],
            "name": ["John", "Jane", "Bob"]
        })
        
        issues = validator.validate(df)
        
        email_issues = [issue for issue in issues if "EMAIL" in issue.message]
        assert len(email_issues) > 0
    
    def test_phone_pattern_detection(self):
        """Test detection of phone patterns in data."""
        validator = PHIDetector()
        df = pd.DataFrame({
            "phone": ["555-123-4567", "555-987-6543"],
            "name": ["John", "Jane"]
        })
        
        issues = validator.validate(df)
        
        phone_issues = [issue for issue in issues if "PHONE" in issue.message]
        assert len(phone_issues) > 0
    
    def test_non_object_column_skipped(self):
        """Test that non-object columns are skipped for pattern checking."""
        validator = PHIDetector()
        df = pd.DataFrame({
            "age": [30, 40, 50],  # int column
            "name": ["John", "Jane", "Bob"]  # object column
        })
        
        issues = validator.validate(df)
        
        # Should only check 'name' column for patterns
        assert len(issues) > 0  # Should have some issues from name column


class TestDataQualityChecker:
    """Test DataQualityChecker class."""
    
    def test_missing_values_detection(self):
        """Test detection of missing values."""
        validator = DataQualityChecker()
        df = pd.DataFrame({
            "col1": [1, None, 3, None],
            "col2": ["a", "b", None, "d"]
        })
        
        issues = validator.validate(df)
        
        # Should detect missing values in both columns
        missing_issues = [issue for issue in issues if "missing values" in issue.message]
        assert len(missing_issues) == 2
    
    def test_missing_values_high_percentage(self):
        """Test detection of high percentage missing values."""
        validator = DataQualityChecker()
        df = pd.DataFrame({
            "col1": [1, None, None, None],  # 75% missing
            "col2": ["a", "b", "c", "d"]
        })
        
        issues = validator.validate(df)
        
        # Should have error for high percentage missing
        error_issues = [issue for issue in issues if issue.severity == "error"]
        assert len(error_issues) > 0
    
    def test_duplicate_rows_detection(self):
        """Test detection of duplicate rows."""
        validator = DataQualityChecker()
        df = pd.DataFrame({
            "col1": [1, 2, 1, 3],
            "col2": ["a", "b", "a", "c"]
        })
        
        issues = validator.validate(df)
        
        # Should detect duplicate rows
        duplicate_issues = [issue for issue in issues if "duplicate rows" in issue.message]
        assert len(duplicate_issues) == 1
    
    def test_empty_columns_detection(self):
        """Test detection of empty columns."""
        validator = DataQualityChecker()
        df = pd.DataFrame({
            "col1": [1, 2, 3],
            "col2": [None, None, None],
            "col3": ["a", "b", "c"]
        })
        
        issues = validator.validate(df)
        
        # Should detect empty column
        empty_issues = [issue for issue in issues if "completely empty" in issue.message]
        assert len(empty_issues) == 1
        assert any(issue.column is not None and "col2" in issue.column for issue in empty_issues)


class TestMedicalCodeValidator:
    """Test MedicalCodeValidator class."""
    
    def test_icd10_validation(self):
        """Test ICD-10 code validation."""
        validator = MedicalCodeValidator(code_columns={"diagnosis": "icd10"})
        df = pd.DataFrame({
            "diagnosis": ["A01.1", "B02.2", "C03", "INVALID", "D04.5"]
        })
        
        issues = validator.validate(df)
        
        assert len(issues) == 1
        assert "INVALID" in issues[0].message
        assert "ICD10" in issues[0].message
    
    def test_icd9_validation(self):
        """Test ICD-9 code validation."""
        validator = MedicalCodeValidator(code_columns={"diagnosis": "icd9"})
        df = pd.DataFrame({
            "diagnosis": ["001", "002.1", "003", "INVALID", "004.5"]
        })
        
        issues = validator.validate(df)
        
        assert len(issues) == 1
        assert "INVALID" in issues[0].message
        assert "ICD9" in issues[0].message
    
    def test_loinc_validation(self):
        """Test LOINC code validation."""
        validator = MedicalCodeValidator(code_columns={"test": "loinc"})
        df = pd.DataFrame({
            "test": ["1234-5", "5678-9", "INVALID", "9999-1"]
        })
        
        issues = validator.validate(df)
        
        assert len(issues) == 1
        assert "INVALID" in issues[0].message
        assert "LOINC" in issues[0].message
    
    def test_cpt_validation(self):
        """Test CPT code validation."""
        validator = MedicalCodeValidator(code_columns={"procedure": "cpt"})
        df = pd.DataFrame({
            "procedure": ["1234", "5678A", "INVALID", "9999"]
        })
        
        issues = validator.validate(df)
        
        assert len(issues) == 1
        assert "INVALID" in issues[0].message
        assert "CPT" in issues[0].message
    
    def test_ndc_validation(self):
        """Test NDC code validation."""
        validator = MedicalCodeValidator(code_columns={"medication": "ndc"})
        df = pd.DataFrame({
            "medication": ["1234-5678-90", "9876-5432-10", "INVALID", "1111-2222-33"]
        })
        
        issues = validator.validate(df)
        
        assert len(issues) == 1
        assert "INVALID" in issues[0].message
        assert "NDC" in issues[0].message
    
    def test_column_not_in_data(self):
        """Test validation when column is not in data."""
        validator = MedicalCodeValidator(code_columns={"missing": "icd10"})
        df = pd.DataFrame({"existing": ["A01.1", "B02.2"]})
        
        issues = validator.validate(df)
        
        assert len(issues) == 0  # Should skip missing column
    
    def test_unknown_code_type(self):
        """Test validation with unknown code type."""
        validator = MedicalCodeValidator(code_columns={"test": "unknown"})
        df = pd.DataFrame({"test": ["value1", "value2"]})
        
        issues = validator.validate(df)
        
        assert len(issues) == 0  # Should skip unknown code type
    
    def test_null_values_handled(self):
        """Test that null values are handled properly."""
        validator = MedicalCodeValidator(code_columns={"diagnosis": "icd10"})
        df = pd.DataFrame({
            "diagnosis": ["A01.1", None, "B02.2", pd.NA]
        })
        
        issues = validator.validate(df)
        
        # Should not have issues for null values
        assert len(issues) == 0


class TestRangeValidator:
    """Test RangeValidator class."""
    
    def test_min_value_validation(self):
        """Test minimum value validation."""
        validator = RangeValidator(ranges={"age": {"min": 0}})
        df = pd.DataFrame({
            "age": [25, 30, -5, 40, 50]
        })
        
        issues = validator.validate(df)
        
        assert len(issues) == 1
        assert "below minimum" in issues[0].message
        assert "age" in issues[0].message
    
    def test_max_value_validation(self):
        """Test maximum value validation."""
        validator = RangeValidator(ranges={"age": {"max": 120}})
        df = pd.DataFrame({
            "age": [25, 30, 150, 40, 50]
        })
        
        issues = validator.validate(df)
        
        assert len(issues) == 1
        assert "above maximum" in issues[0].message
        assert "age" in issues[0].message
    
    def test_both_min_max_validation(self):
        """Test both minimum and maximum value validation."""
        validator = RangeValidator(ranges={"age": {"min": 0, "max": 120}})
        df = pd.DataFrame({
            "age": [25, 30, -5, 150, 50]
        })
        
        issues = validator.validate(df)
        
        assert len(issues) == 2
        min_issues = [issue for issue in issues if "below minimum" in issue.message]
        max_issues = [issue for issue in issues if "above maximum" in issue.message]
        assert len(min_issues) == 1
        assert len(max_issues) == 1
    
    def test_column_not_in_data(self):
        """Test validation when column is not in data."""
        validator = RangeValidator(ranges={"missing": {"min": 0}})
        df = pd.DataFrame({"existing": [1, 2, 3]})
        
        issues = validator.validate(df)
        
        assert len(issues) == 0  # Should skip missing column
    
    def test_non_numeric_column_skipped(self):
        """Test that non-numeric columns are skipped."""
        validator = RangeValidator(ranges={"text": {"min": 0}})
        df = pd.DataFrame({
            "text": ["a", "b", "c"]
        })
        
        issues = validator.validate(df)
        
        assert len(issues) == 0  # Should skip non-numeric column
    
    def test_no_range_specified(self):
        """Test validation when no range is specified."""
        validator = RangeValidator(ranges={"age": {}})
        df = pd.DataFrame({
            "age": [25, 30, 40, 50]
        })
        
        issues = validator.validate(df)
        
        assert len(issues) == 0  # Should not validate anything


class TestDateValidator:
    """Test DateValidator class."""
    
    def test_invalid_date_detection(self):
        """Test detection of invalid dates."""
        validator = DateValidator(date_columns=["birth_date"])
        df = pd.DataFrame({
            "birth_date": ["2020-01-01", "invalid-date", "2020-02-02", "not-a-date"]
        })
        
        issues = validator.validate(df)
        
        assert len(issues) == 1
        assert "invalid date values" in issues[0].message
    
    def test_min_date_validation(self):
        """Test minimum date validation."""
        validator = DateValidator(
            date_columns=["birth_date"],
            min_date="1900-01-01"
        )
        df = pd.DataFrame({
            "birth_date": ["1950-01-01", "1800-01-01", "2000-01-01"]
        })
        
        issues = validator.validate(df)
        
        assert len(issues) == 1
        assert "before" in issues[0].message
        assert "1900-01-01" in issues[0].message
    
    def test_max_date_validation(self):
        """Test maximum date validation."""
        validator = DateValidator(
            date_columns=["birth_date"],
            max_date="2020-01-01"
        )
        df = pd.DataFrame({
            "birth_date": ["2010-01-01", "2025-01-01", "2000-01-01"]
        })
        
        issues = validator.validate(df)
        
        assert len(issues) == 1
        assert "after" in issues[0].message
        assert "2020-01-01" in issues[0].message
    
    def test_both_min_max_date_validation(self):
        """Test both minimum and maximum date validation."""
        validator = DateValidator(
            date_columns=["birth_date"],
            min_date="1900-01-01",
            max_date="2020-01-01"
        )
        df = pd.DataFrame({
            "birth_date": ["1950-01-01", "1800-01-01", "2025-01-01"]
        })
        
        issues = validator.validate(df)
        
        assert len(issues) == 2
        before_issues = [issue for issue in issues if "before" in issue.message]
        after_issues = [issue for issue in issues if "after" in issue.message]
        assert len(before_issues) == 1
        assert len(after_issues) == 1
    
    def test_column_not_in_data(self):
        """Test validation when column is not in data."""
        validator = DateValidator(date_columns=["missing"])
        df = pd.DataFrame({"existing": ["2020-01-01", "2020-02-02"]})
        
        issues = validator.validate(df)
        
        assert len(issues) == 0  # Should skip missing column


if __name__ == "__main__":
    pytest.main([__file__]) 