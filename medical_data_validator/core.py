"""
Core medical data validation functionality.

This module provides the main MedicalDataValidator class and supporting
data structures for validating healthcare datasets.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Union
import pandas as pd
from pydantic import BaseModel

# Import compliance engine for v1.2
try:
    from .compliance import ComplianceEngine
    from .compliance_templates import template_manager
    from .analytics import AdvancedAnalytics
    from .monitoring import monitor
except ImportError:
    ComplianceEngine = None
    template_manager = None
    AdvancedAnalytics = None
    monitor = None


@dataclass
class ValidationIssue:
    """Represents a single validation issue found in the data."""
    
    severity: str  # "error", "warning", "info"
    message: str
    column: Optional[str] = None
    row: Optional[int] = None
    value: Optional[Any] = None
    rule_name: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass
class ValidationResult:
    """Result of a validation operation."""
    
    is_valid: bool
    issues: List[ValidationIssue] = field(default_factory=list)
    summary: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.utcnow)
    
    def add_issue(self, issue: ValidationIssue) -> None:
        """Add a validation issue to the result."""
        self.issues.append(issue)
        if issue.severity == "error":
            self.is_valid = False
    
    def get_issues_by_severity(self, severity: str) -> List[ValidationIssue]:
        """Get all issues of a specific severity level."""
        return [issue for issue in self.issues if issue.severity == severity]
    
    def get_issues_by_column(self, column: str) -> List[ValidationIssue]:
        """Get all issues for a specific column."""
        return [issue for issue in self.issues if issue.column == column]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert the validation result to a dictionary."""
        return {
            "is_valid": self.is_valid,
            "total_issues": len(self.issues),
            "error_count": len(self.get_issues_by_severity("error")),
            "warning_count": len(self.get_issues_by_severity("warning")),
            "info_count": len(self.get_issues_by_severity("info")),
            "issues": [
                {
                    "severity": issue.severity,
                    "message": issue.message,
                    "column": issue.column,
                    "row": issue.row,
                    "value": str(issue.value) if issue.value is not None else None,
                    "rule_name": issue.rule_name,
                    "timestamp": issue.timestamp.isoformat(),
                }
                for issue in self.issues
            ],
            "summary": self.summary,
            "timestamp": self.timestamp.isoformat(),
        }


class ValidationRule(BaseModel):
    """Base class for validation rules."""
    
    name: str
    description: str
    severity: str = "error"  # "error", "warning", "info"
    
    model_config = {
        "extra": "allow"  # Allow extra fields in subclasses
    }
    
    def validate(self, data: pd.DataFrame) -> List[ValidationIssue]:
        """Validate the data and return a list of issues."""
        raise NotImplementedError("Subclasses must implement validate()")


class MedicalDataValidator:
    """
    Main class for validating medical datasets.
    
    This class provides a comprehensive interface for validating healthcare
    data with support for schema validation, PHI/PII detection, and
    medical-specific quality checks.
    """
    
    def __init__(self, rules: Optional[List[ValidationRule]] = None, enable_compliance: bool = True, 
                 compliance_template: Optional[str] = None, enable_analytics: bool = True, 
                 enable_monitoring: bool = True):
        """
        Initialize the validator with optional validation rules.
        
        Args:
            rules: List of validation rules to apply
            enable_compliance: Whether to enable advanced compliance validation (v1.2)
            compliance_template: Name of compliance template to apply (v1.2)
            enable_analytics: Whether to enable advanced analytics (v1.2)
            enable_monitoring: Whether to enable real-time monitoring (v1.2)
        """
        self.rules = rules or []
        self._validators = {}
        self.enable_compliance = enable_compliance
        self.compliance_template = compliance_template
        self.enable_analytics = enable_analytics
        self.enable_monitoring = enable_monitoring
        
        # Initialize compliance engine if available
        if enable_compliance and ComplianceEngine is not None:
            self.compliance_engine = ComplianceEngine()
            # Apply template if specified
            if compliance_template and template_manager is not None:
                template_manager.apply_template(compliance_template, self.compliance_engine)
                # Set template_applied attribute on compliance engine
                self.compliance_engine.template_applied = compliance_template
        else:
            self.compliance_engine = None
        
        # Initialize analytics engine if available
        if enable_analytics and AdvancedAnalytics is not None:
            self.analytics_engine = AdvancedAnalytics()
        else:
            self.analytics_engine = None
        
        # Start monitoring if enabled
        if enable_monitoring and monitor is not None:
            monitor.start_monitoring()
    
    def add_rule(self, rule: ValidationRule) -> None:
        """Add a validation rule to the validator."""
        self.rules.append(rule)
    
    def add_validator(self, name: str, validator: Any) -> None:
        """Add a custom validator function."""
        self._validators[name] = validator
    
    def add_custom_compliance_rule(self, name: str, pattern: str, severity: str = 'medium', 
                                  field_pattern: Optional[str] = None, description: str = "", 
                                  recommendation: Optional[str] = None) -> None:
        """Add a custom compliance rule (v1.2)."""
        if self.compliance_engine is not None:
            self.compliance_engine.add_custom_pattern(name, pattern, severity, field_pattern, description, recommendation)
    
    def remove_custom_compliance_rule(self, rule_name: str) -> bool:
        """Remove a custom compliance rule (v1.2)."""
        if self.compliance_engine is not None:
            return self.compliance_engine.remove_custom_rule(rule_name)
        return False
    
    def get_custom_compliance_rules(self) -> List[Dict[str, Any]]:
        """Get all custom compliance rules (v1.2)."""
        if self.compliance_engine is not None:
            rules = self.compliance_engine.get_custom_rules()
            return [
                {
                    'name': rule.name,
                    'description': rule.description,
                    'pattern': rule.pattern,
                    'severity': rule.severity,
                    'field_pattern': rule.field_pattern,
                    'recommendation': rule.recommendation
                }
                for rule in rules
            ]
        return []
    
    def get_available_compliance_templates(self) -> Dict[str, str]:
        """Get available compliance templates (v1.2)."""
        if template_manager is not None:
            return template_manager.list_templates()
        return {}
    
    def validate(self, data: Union[pd.DataFrame, Dict[str, List], List[Dict]]) -> ValidationResult:
        """
        Validate the provided data against all configured rules.
        
        Args:
            data: Data to validate. Can be a pandas DataFrame, dictionary of lists,
                  or list of dictionaries.
        
        Returns:
            ValidationResult containing validation issues and summary
        """
        import time
        start_time = time.time()
        
        # Convert data to DataFrame if needed
        if isinstance(data, dict):
            df = pd.DataFrame(data)
        elif isinstance(data, list):
            df = pd.DataFrame(data)
        elif isinstance(data, pd.DataFrame):
            df = data
        else:
            raise ValueError("Data must be a pandas DataFrame, dict, or list")
        
        # Initialize result
        result = ValidationResult(is_valid=True)
        
        # Run all validation rules
        for rule in self.rules:
            try:
                issues = rule.validate(df)
                for issue in issues:
                    result.add_issue(issue)
            except Exception as e:
                # Add error for rule failure
                error_issue = ValidationIssue(
                    severity="error",
                    message=f"Rule '{rule.name}' failed: {str(e)}",
                    rule_name=rule.name,
                )
                result.add_issue(error_issue)
        
        # Run custom validators
        for name, validator in self._validators.items():
            try:
                if callable(validator):
                    validator_result = validator(df)
                    if isinstance(validator_result, list):
                        for issue in validator_result:
                            result.add_issue(issue)
                    elif isinstance(validator_result, ValidationIssue):
                        result.add_issue(validator_result)
            except Exception as e:
                error_issue = ValidationIssue(
                    severity="error",
                    message=f"Custom validator '{name}' failed: {str(e)}",
                )
                result.add_issue(error_issue)
        
        # Generate summary
        result.summary = self._generate_summary(df, result)
        
        # Add compliance validation if enabled (v1.2)
        if self.compliance_engine is not None:
            try:
                compliance_report = self.compliance_engine.comprehensive_compliance_validation(df)
                result.summary['compliance_report'] = compliance_report
            except Exception as e:
                # Add compliance validation error
                error_issue = ValidationIssue(
                    severity="warning",
                    message=f"Compliance validation failed: {str(e)}",
                    rule_name="compliance_engine"
                )
                result.add_issue(error_issue)
        
        # Add analytics if enabled (v1.2)
        if self.analytics_engine is not None:
            try:
                analytics_report = self.analytics_engine.comprehensive_analysis(df)
                result.summary['analytics_report'] = analytics_report
            except Exception as e:
                # Add analytics error
                error_issue = ValidationIssue(
                    severity="info",
                    message=f"Analytics analysis failed: {str(e)}",
                )
                result.add_issue(error_issue)
        
        # Record monitoring data if enabled (v1.2)
        if self.enable_monitoring and monitor is not None:
            try:
                processing_time = time.time() - start_time
                monitor.record_validation_result(result.to_dict(), processing_time)
            except Exception as e:
                print(f"Monitoring recording failed: {e}")
        
        return result
    
    def validate_dataframe(self, df: pd.DataFrame) -> ValidationResult:
        """
        Validate a pandas DataFrame (alias for validate method).
        
        Args:
            df: Pandas DataFrame to validate
        
        Returns:
            ValidationResult containing validation issues and summary
        """
        return self.validate(df)
    
    def _generate_summary(self, df: pd.DataFrame, result: ValidationResult) -> Dict[str, Any]:
        """Generate a summary of the validation results."""
        return {
            "total_rows": int(len(df)),
            "total_columns": int(len(df.columns)),
            "missing_values": {col: int(count) for col, count in df.isnull().sum().to_dict().items()},
            "duplicate_rows": int(df.duplicated().sum()),
            "data_types": {col: str(dtype) for col, dtype in df.dtypes.to_dict().items()},
            "validation_rules_applied": len(self.rules),
            "custom_validators_applied": len(self._validators),
        }
    
    def get_report(self, result: ValidationResult) -> str:
        """Generate a human-readable validation report."""
        report_lines = [
            "Medical Data Validation Report",
            "=" * 40,
            f"Timestamp: {result.timestamp.strftime('%Y-%m-%d %H:%M:%S')}",
            f"Overall Status: {'✅ VALID' if result.is_valid else '❌ INVALID'}",
            "",
            f"Summary:",
            f"  - Total Issues: {len(result.issues)}",
            f"  - Errors: {len(result.get_issues_by_severity('error'))}",
            f"  - Warnings: {len(result.get_issues_by_severity('warning'))}",
            f"  - Info: {len(result.get_issues_by_severity('info'))}",
            "",
        ]
        
        if result.issues:
            report_lines.append("Issues Found:")
            report_lines.append("-" * 20)
            
            for i, issue in enumerate(result.issues, 1):
                location = f"Column: {issue.column}" if issue.column else ""
                if issue.row is not None:
                    location += f", Row: {issue.row}"
                
                report_lines.append(f"{i}. [{issue.severity.upper()}] {issue.message}")
                if location:
                    report_lines.append(f"   Location: {location}")
                if issue.value is not None:
                    report_lines.append(f"   Value: {issue.value}")
                report_lines.append("")
        
        return "\n".join(report_lines) 