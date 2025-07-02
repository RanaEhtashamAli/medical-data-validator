"""
Specific validation rules for medical data.

This module contains concrete implementations of validation rules for
healthcare datasets, including schema validation, PHI/PII detection,
and medical-specific quality checks.
"""

import re
from typing import Any, Dict, List, Optional, Set, Union
import pandas as pd
from .core import ValidationRule, ValidationIssue


class SchemaValidator(ValidationRule):
    """Validates data schema including required columns and data types."""
    
    def __init__(
        self,
        required_columns: Optional[List[str]] = None,
        column_types: Optional[Dict[str, str]] = None,
        name: str = "SchemaValidator",
        description: str = "Validates data schema and column types",
    ):
        super().__init__(name=name, description=description)
        self.required_columns = required_columns or []
        self.column_types = column_types or {}
    
    def validate(self, data: pd.DataFrame) -> List[ValidationIssue]:
        issues = []
        
        # Check required columns
        missing_columns = set(self.required_columns) - set(data.columns)
        for column in missing_columns:
            issues.append(
                ValidationIssue(
                    severity="error",
                    message=f"Required column '{column}' is missing",
                    column=column,
                    rule_name=self.name,
                )
            )
        
        # Check column types
        for column, expected_type in self.column_types.items():
            if column not in data.columns:
                continue
            
            actual_type = str(data[column].dtype)
            if not self._is_type_compatible(actual_type, expected_type):
                issues.append(
                    ValidationIssue(
                        severity="error",
                        message=f"Column '{column}' has type '{actual_type}' but expected '{expected_type}'",
                        column=column,
                        rule_name=self.name,
                    )
                )
        
        return issues
    
    def _is_type_compatible(self, actual: str, expected: str) -> bool:
        """Check if actual type is compatible with expected type."""
        type_mapping = {
            "int64": ["int", "integer", "int64"],
            "float64": ["float", "float64", "number"],
            "object": ["string", "str", "object", "text"],
            "datetime64[ns]": ["datetime", "date", "timestamp"],
            "bool": ["boolean", "bool"],
        }
        
        for pandas_type, compatible_types in type_mapping.items():
            if actual == pandas_type and expected.lower() in compatible_types:
                return True
        
        return False


class PHIDetector(ValidationRule):
    """Detects potential PHI/PII in the data."""
    
    def __init__(
        self,
        name: str = "PHIDetector",
        description: str = "Detects potential PHI/PII in the data",
    ):
        super().__init__(name=name, description=description)
        self.phi_patterns = {
            "ssn": r"\b\d{3}-\d{2}-\d{4}\b",
            "email": r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b",
            "phone": r"\b\d{3}-\d{3}-\d{4}\b",
            "date": r"\b\d{4}-\d{2}-\d{2}\b",
            "zip_code": r"\b\d{5}(?:-\d{4})?\b",
        }
        self.phi_keywords = {
            "name", "address", "phone", "email", "ssn", "social", "security",
            "birth", "date", "zip", "postal", "medical", "record", "patient",
            "id", "identifier", "account", "license", "passport", "driver",
        }
    
    def validate(self, data: pd.DataFrame) -> List[ValidationIssue]:
        issues = []
        
        for column in data.columns:
            column_lower = column.lower()
            
            # Check for PHI keywords in column names
            if any(keyword in column_lower for keyword in self.phi_keywords):
                issues.append(
                    ValidationIssue(
                        severity="warning",
                        message=f"Column '{column}' may contain PHI/PII based on name",
                        column=column,
                        rule_name=self.name,
                    )
                )
            
            # Check for PHI patterns in data
            if data[column].dtype == "object":
                column_series = data[column]
                if isinstance(column_series, pd.Series):
                    phi_found = self._check_phi_patterns(column_series, column)
                    issues.extend(phi_found)
        
        return issues
    
    def _check_phi_patterns(self, series: pd.Series, column: str) -> List[ValidationIssue]:
        """Check for PHI patterns in a data series."""
        issues = []
        
        for pattern_name, pattern in self.phi_patterns.items():
            # Use the raw regex pattern (do NOT escape)
            matches = series.astype(str).str.contains(pattern, regex=True, na=False)
            if matches.any():
                match_count = int(matches.sum())
                issues.append(
                    ValidationIssue(
                        severity="warning",
                        message=f"Found {match_count} potential {pattern_name.upper()} values in column '{column}'",
                        column=column,
                        rule_name=self.name,
                    )
                )
        
        return issues


class DataQualityChecker(ValidationRule):
    """Performs general data quality checks."""
    
    def __init__(
        self,
        name: str = "DataQualityChecker",
        description: str = "Performs general data quality checks",
    ):
        super().__init__(name=name, description=description)
    
    def validate(self, data: pd.DataFrame) -> List[ValidationIssue]:
        issues = []
        
        # Check for missing values
        missing_counts = data.isnull().sum()
        for column, count in missing_counts.items():
            if count > 0:
                percentage = (count / len(data)) * 100
                severity = "error" if percentage > 50 else "warning"
                issues.append(
                    ValidationIssue(
                        severity=severity,
                        message=f"Column '{column}' has {count} missing values ({percentage:.1f}%)",
                        column=column,
                        rule_name=self.name,
                    )
                )
        
        # Check for duplicate rows
        duplicate_mask = data.duplicated()
        duplicate_count = int(duplicate_mask.sum())
        if duplicate_count > 0:
            issues.append(
                ValidationIssue(
                    severity="warning",
                    message=f"Found {duplicate_count} duplicate rows",
                    rule_name=self.name,
                )
            )
        
        # Check for empty columns
        for column in data.columns:
            column_series = data[column]
            if isinstance(column_series, pd.Series) and column_series.isnull().all():
                issues.append(
                    ValidationIssue(
                        severity="error",
                        message=f"Column '{column}' is completely empty",
                        column=column,
                        rule_name=self.name,
                    )
                )
        
        return issues


class MedicalCodeValidator(ValidationRule):
    """Validates medical codes like ICD-10, LOINC, etc."""
    
    def __init__(
        self,
        code_columns: Optional[Dict[str, str]] = None,
        name: str = "MedicalCodeValidator",
        description: str = "Validates medical codes",
    ):
        super().__init__(name=name, description=description)
        self.code_columns = code_columns or {}
        
        # Basic patterns for common medical codes
        self.code_patterns = {
            "icd10": r"^[A-Z]\d{2}(\.\d{1,2})?$",
            "icd9": r"^\d{3}(\.\d{1,2})?$",
            "loinc": r"^\d{1,5}-\d$",
            "cpt": r"^\d{4}[A-Z]?$",
            "ndc": r"^\d{4}-\d{4}-\d{2}$",
        }
    
    def validate(self, data: pd.DataFrame) -> List[ValidationIssue]:
        issues = []
        
        for column, code_type in self.code_columns.items():
            if column not in data.columns:
                continue
            
            if code_type in self.code_patterns:
                pattern = self.code_patterns[code_type]
                column_series = data[column]
                if isinstance(column_series, pd.Series):
                    invalid_codes = self._check_code_pattern(column_series, pattern, code_type)
                    issues.extend(invalid_codes)
        
        return issues
    
    def _check_code_pattern(self, series: pd.Series, pattern: str, code_type: str) -> List[ValidationIssue]:
        """Check if codes match the expected pattern."""
        issues = []
        
        # Convert to string and check pattern
        string_series = series.astype(str)
        valid_mask = string_series.str.match(pattern, na=False)
        invalid_mask = ~valid_mask & ~series.isnull()
        
        if invalid_mask.any():
            invalid_count = int(invalid_mask.sum())
            invalid_series = series[invalid_mask]
            if isinstance(invalid_series, pd.Series):
                sample_invalid = invalid_series.head(3).tolist()
                
                issues.append(
                    ValidationIssue(
                        severity="warning",
                        message=f"Found {invalid_count} invalid {code_type.upper()} codes in column. Sample: {sample_invalid}",
                        rule_name=self.name,
                    )
                )
        
        return issues


class RangeValidator(ValidationRule):
    """Validates numeric values within expected ranges."""
    
    def __init__(
        self,
        ranges: Optional[Dict[str, Dict[str, Union[float, int]]]] = None,
        name: str = "RangeValidator",
        description: str = "Validates numeric values within expected ranges",
    ):
        super().__init__(name=name, description=description)
        self.ranges = ranges or {}
    
    def validate(self, data: pd.DataFrame) -> List[ValidationIssue]:
        issues = []
        
        for column, range_config in self.ranges.items():
            if column not in data.columns:
                continue
            
            if not pd.api.types.is_numeric_dtype(data[column]):
                continue
            
            min_val = range_config.get("min")
            max_val = range_config.get("max")
            
            if min_val is not None:
                below_min = data[column] < min_val
                if below_min.any():
                    count = int(below_min.sum())
                    issues.append(
                        ValidationIssue(
                            severity="warning",
                            message=f"Column '{column}' has {count} values below minimum {min_val}",
                            column=column,
                            rule_name=self.name,
                        )
                    )
            
            if max_val is not None:
                above_max = data[column] > max_val
                if above_max.any():
                    count = int(above_max.sum())
                    issues.append(
                        ValidationIssue(
                            severity="warning",
                            message=f"Column '{column}' has {count} values above maximum {max_val}",
                            column=column,
                            rule_name=self.name,
                        )
                    )
        
        return issues


class DateValidator(ValidationRule):
    """Validates date fields and their ranges."""
    
    def __init__(
        self,
        date_columns: Optional[List[str]] = None,
        min_date: Optional[str] = None,
        max_date: Optional[str] = None,
        name: str = "DateValidator",
        description: str = "Validates date fields and their ranges",
    ):
        super().__init__(name=name, description=description)
        self.date_columns = date_columns or []
        self.min_date = pd.to_datetime(min_date) if min_date else None
        self.max_date = pd.to_datetime(max_date) if max_date else None
    
    def validate(self, data: pd.DataFrame) -> List[ValidationIssue]:
        issues = []
        
        for column in self.date_columns:
            if column not in data.columns:
                continue
            
            # Try to convert to datetime
            try:
                date_series = pd.to_datetime(data[column], errors="coerce")
                invalid_dates = date_series.isnull() & ~data[column].isnull()
                
                if invalid_dates.any():
                    count = int(invalid_dates.sum())
                    issues.append(
                        ValidationIssue(
                            severity="error",
                            message=f"Column '{column}' has {count} invalid date values",
                            column=column,
                            rule_name=self.name,
                        )
                    )
                
                # Check date ranges
                if self.min_date is not None:
                    before_min = date_series < self.min_date
                    if before_min.any():
                        count = int(before_min.sum())
                        issues.append(
                            ValidationIssue(
                                severity="warning",
                                message=f"Column '{column}' has {count} dates before {self.min_date.date()}",
                                column=column,
                                rule_name=self.name,
                            )
                        )
                
                if self.max_date is not None:
                    after_max = date_series > self.max_date
                    if after_max.any():
                        count = int(after_max.sum())
                        issues.append(
                            ValidationIssue(
                                severity="warning",
                                message=f"Column '{column}' has {count} dates after {self.max_date.date()}",
                                column=column,
                                rule_name=self.name,
                            )
                        )
                
            except Exception as e:
                issues.append(
                    ValidationIssue(
                        severity="error",
                        message=f"Failed to validate dates in column '{column}': {str(e)}",
                        column=column,
                        rule_name=self.name,
                    )
                )
        
        return issues 