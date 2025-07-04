"""
Advanced Compliance Validation Engine for Medical Data Validator v1.2
"""

import re
import pandas as pd
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
import numpy as np

@dataclass
class ComplianceViolation:
    """Represents a compliance violation."""
    standard: str
    rule_id: str
    severity: str
    field: str
    message: str
    recommendation: Optional[str] = None

@dataclass
class ComplianceScore:
    """Represents a compliance score for a standard."""
    standard: str
    score: float
    risk_level: str
    violations: List[ComplianceViolation]
    recommendations: List[str]

@dataclass
class CustomComplianceRule:
    """Represents a custom compliance rule."""
    name: str
    description: str
    pattern: str
    severity: str  # 'critical', 'high', 'medium', 'low'
    field_pattern: Optional[str] = None  # Optional pattern to match column names
    recommendation: Optional[str] = None

class ComplianceEngine:
    """Advanced compliance validation engine for medical data."""
    
    def __init__(self):
        self.hipaa_patterns = {
            'names': r'\b[A-Z][a-z]+ [A-Z][a-z]+\b',
            'ssn': r'\d{3}-\d{2}-\d{4}',
            'email': r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}',
            'phone': r'\(\d{3}\)\s*\d{3}-\d{4}'
        }
        self.custom_rules = []
        self.template_applied = None  # Add template_applied attribute
    
    def add_custom_rule(self, rule: CustomComplianceRule) -> None:
        """Add a custom compliance rule."""
        self.custom_rules.append(rule)
    
    def add_custom_pattern(self, name: str, pattern: str, severity: str = 'medium', 
                          field_pattern: Optional[str] = None, description: str = "", 
                          recommendation: Optional[str] = None) -> None:
        """Quick method to add a custom pattern-based rule."""
        rule = CustomComplianceRule(
            name=name,
            description=description,
            pattern=pattern,
            severity=severity,
            field_pattern=field_pattern,
            recommendation=recommendation
        )
        self.add_custom_rule(rule)
    
    def remove_custom_rule(self, rule_name: str) -> bool:
        """Remove a custom compliance rule by name."""
        initial_count = len(self.custom_rules)
        self.custom_rules = [rule for rule in self.custom_rules if rule.name != rule_name]
        return len(self.custom_rules) < initial_count
    
    def get_custom_rules(self) -> List[CustomComplianceRule]:
        """Get all custom compliance rules."""
        return self.custom_rules.copy()
    
    def clear_custom_rules(self) -> None:
        """Clear all custom compliance rules."""
        self.custom_rules.clear()
    
    def comprehensive_compliance_validation(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Perform comprehensive compliance validation."""
        # HIPAA check (real)
        hipaa_violations = []
        for column in df.columns:
            column_data = df[column].astype(str)
            if column_data.str.contains(self.hipaa_patterns['names'], regex=True, na=False).any():
                hipaa_violations.append(ComplianceViolation(
                    standard='HIPAA',
                    rule_id='PHI_NAME_DETECTED',
                    severity='high',
                    field=column,
                    message=f"Potential names detected in column '{column}'",
                    recommendation="Consider de-identification"
                ))
            if column_data.str.contains(self.hipaa_patterns['ssn'], regex=True, na=False).any():
                hipaa_violations.append(ComplianceViolation(
                    standard='HIPAA',
                    rule_id='PHI_SSN_DETECTED',
                    severity='critical',
                    field=column,
                    message=f"SSN pattern detected in column '{column}'",
                    recommendation="Immediate de-identification required"
                ))
        hipaa_score = max(0, 100 - (len(hipaa_violations) * 10))
        hipaa_risk = 'low' if hipaa_score >= 90 else 'medium' if hipaa_score >= 70 else 'high' if hipaa_score >= 50 else 'critical'
        hipaa_recommendations = []
        if hipaa_violations:
            hipaa_recommendations.append("Implement data access controls")
            hipaa_recommendations.append("Provide compliance training")

        # GDPR check (real)
        gdpr_violations = []
        gdpr_patterns = {
            'personal': [self.hipaa_patterns['names'], self.hipaa_patterns['ssn'], self.hipaa_patterns['email'], self.hipaa_patterns['phone']],
            'sensitive': [r'\b(race|ethnicity|religion|health|biometric|genetic|sexuality)\b']
        }
        for column in df.columns:
            column_data = df[column].astype(str)
            # Personal data
            for pattern in gdpr_patterns['personal']:
                if column_data.str.contains(pattern, regex=True, na=False).any():
                    gdpr_violations.append(ComplianceViolation(
                        standard='GDPR',
                        rule_id='PERSONAL_DATA_DETECTED',
                        severity='high',
                        field=column,
                        message=f"Personal data detected in column '{column}'",
                        recommendation="Ensure lawful basis for processing"
                    ))
            # Sensitive data
            for pattern in gdpr_patterns['sensitive']:
                if column_data.str.contains(pattern, regex=True, na=False).any():
                    gdpr_violations.append(ComplianceViolation(
                        standard='GDPR',
                        rule_id='SENSITIVE_DATA_DETECTED',
                        severity='critical',
                        field=column,
                        message=f"Sensitive data detected in column '{column}'",
                        recommendation="Explicit consent required for processing"
                    ))
        gdpr_score = max(0, 100 - (len(gdpr_violations) * 10))
        gdpr_risk = 'low' if gdpr_score >= 90 else 'medium' if gdpr_score >= 70 else 'high' if gdpr_score >= 50 else 'critical'
        gdpr_recommendations = []
        if gdpr_violations:
            gdpr_recommendations.append("Review lawful basis for processing personal data")
            gdpr_recommendations.append("Implement data minimization and retention policies")

        # FDA 21 CFR Part 11 check (real)
        fda_violations = []
        # Check for electronic signature fields
        sig_fields = ['username', 'user', 'timestamp', 'meaning']
        missing_sig = [f for f in sig_fields if not any(f in c.lower() for c in df.columns)]
        if missing_sig:
            fda_violations.append(ComplianceViolation(
                standard='FDA',
                rule_id='MISSING_SIGNATURE_FIELDS',
                severity='high',
                field='system',
                message=f"Missing electronic signature fields: {', '.join(missing_sig)}",
                recommendation="Implement electronic signature system"
            ))
        # Check for audit trail fields
        audit_fields = ['action', 'change']
        missing_audit = [f for f in audit_fields if not any(f in c.lower() for c in df.columns)]
        if missing_audit:
            fda_violations.append(ComplianceViolation(
                standard='FDA',
                rule_id='MISSING_AUDIT_FIELDS',
                severity='medium',
                field='system',
                message=f"Missing audit trail fields: {', '.join(missing_audit)}",
                recommendation="Implement audit trail system"
            ))
        fda_score = max(0, 100 - (len(fda_violations) * 20))
        fda_risk = 'low' if fda_score >= 90 else 'medium' if fda_score >= 70 else 'high' if fda_score >= 50 else 'critical'
        fda_recommendations = []
        if fda_violations:
            fda_recommendations.append("Implement electronic signature and audit trail systems")
            fda_recommendations.append("Document system validation procedures")

        # Medical coding checks (real)
        icd10_pattern = r'^[A-Z]\d{2}(?:\.\d{1,2})?$'
        loinc_pattern = r'^\d{1,5}-\d$'
        cpt_pattern = r'^\d{5}$'
        icd10_violations = 0
        loinc_violations = 0
        cpt_violations = 0
        for column in df.columns:
            col_lower = column.lower()
            column_data = df[column].astype(str)
            if 'icd' in col_lower or 'diagnosis' in col_lower:
                icd10_violations += (~column_data.str.match(icd10_pattern, na=False)).sum()
            if 'loinc' in col_lower or 'lab' in col_lower or 'test' in col_lower:
                loinc_violations += (~column_data.str.match(loinc_pattern, na=False)).sum()
            if 'cpt' in col_lower or 'procedure' in col_lower or 'service' in col_lower:
                cpt_violations += (~column_data.str.match(cpt_pattern, na=False)).sum()
        icd10_score = max(0, 100 - icd10_violations * 10)
        loinc_score = max(0, 100 - loinc_violations * 10)
        cpt_score = max(0, 100 - cpt_violations * 10)
        icd10_risk = 'low' if icd10_score >= 90 else 'medium' if icd10_score >= 70 else 'high' if icd10_score >= 50 else 'critical'
        loinc_risk = 'low' if loinc_score >= 90 else 'medium' if loinc_score >= 70 else 'high' if loinc_score >= 50 else 'critical'
        cpt_risk = 'low' if cpt_score >= 90 else 'medium' if cpt_score >= 70 else 'high' if cpt_score >= 50 else 'critical'
        # Custom rules check
        custom_violations = []
        for column in df.columns:
            column_data = df[column].astype(str)
            for rule in self.custom_rules:
                # Check if rule applies to this column (field_pattern)
                if rule.field_pattern is None or re.search(rule.field_pattern, column, re.IGNORECASE):
                    # Check if pattern matches in column data
                    if column_data.str.contains(rule.pattern, regex=True, na=False).any():
                        custom_violations.append(ComplianceViolation(
                            standard='CUSTOM',
                            rule_id=rule.name,
                            severity=rule.severity,
                            field=column,
                            message=f"Custom rule '{rule.name}' violation: {rule.description}",
                            recommendation=rule.recommendation or "Review custom compliance rule"
                        ))
        
        # Aggregate all violations
        all_violations = [
            *hipaa_violations,
            *gdpr_violations,
            *fda_violations,
            *custom_violations
        ]
        # Summary
        summary = {
            'total_violations': len(all_violations),
            'critical_violations': len([v for v in all_violations if v.severity == 'critical']),
            'high_violations': len([v for v in all_violations if v.severity == 'high']),
            'medium_violations': len([v for v in all_violations if v.severity == 'medium']),
            'low_violations': len([v for v in all_violations if v.severity == 'low'])
        }
        # Overall score (average)
        scores = [hipaa_score, gdpr_score, fda_score, icd10_score, loinc_score, cpt_score]
        overall_score = sum(scores) / len(scores)
        overall_risk = 'low' if overall_score >= 90 else 'medium' if overall_score >= 70 else 'high' if overall_score >= 50 else 'critical'
        
        # Convert all numpy types to native Python types
        def convert_numpy_types(obj):
            if isinstance(obj, np.integer):
                return int(obj)
            elif isinstance(obj, np.floating):
                return float(obj)
            elif isinstance(obj, np.ndarray):
                return obj.tolist()
            elif isinstance(obj, dict):
                return {k: convert_numpy_types(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [convert_numpy_types(item) for item in obj]
            return obj
        
        # Convert ComplianceViolation objects to dictionaries
        def violation_to_dict(violation):
            return {
                'standard': violation.standard,
                'rule_id': violation.rule_id,
                'severity': violation.severity,
                'field': violation.field,
                'message': violation.message,
                'recommendation': violation.recommendation
            }
        
        # Convert violations to dictionaries
        hipaa_violations_dict = [violation_to_dict(v) for v in hipaa_violations]
        gdpr_violations_dict = [violation_to_dict(v) for v in gdpr_violations]
        fda_violations_dict = [violation_to_dict(v) for v in fda_violations]
        custom_violations_dict = [violation_to_dict(v) for v in custom_violations]
        
        # Collect all violations
        all_violations_dict = hipaa_violations_dict + gdpr_violations_dict + fda_violations_dict + custom_violations_dict
        
        # Structure expected by tests
        report = {
            'standards': {
                'hipaa': {
                    'score': convert_numpy_types(hipaa_score),
                    'risk_level': hipaa_risk,
                    'violations': hipaa_violations_dict,
                    'violations_count': len(hipaa_violations),
                    'recommendations': hipaa_recommendations,
                    'compliant': len(hipaa_violations) == 0
                },
                'gdpr': {
                    'score': convert_numpy_types(gdpr_score),
                    'risk_level': gdpr_risk,
                    'violations': gdpr_violations_dict,
                    'violations_count': len(gdpr_violations),
                    'recommendations': gdpr_recommendations,
                    'compliant': len(gdpr_violations) == 0
                },
                'fda': {
                    'score': convert_numpy_types(fda_score),
                    'risk_level': fda_risk,
                    'violations': fda_violations_dict,
                    'violations_count': len(fda_violations),
                    'recommendations': fda_recommendations,
                    'compliant': len(fda_violations) == 0
                },
                'medical_coding': {
                    'icd10_score': convert_numpy_types(icd10_score),
                    'loinc_score': convert_numpy_types(loinc_score),
                    'cpt_score': convert_numpy_types(cpt_score),
                    'icd10': {
                        'score': convert_numpy_types(icd10_score),
                        'risk_level': icd10_risk,
                        'violations_count': convert_numpy_types(icd10_violations),
                        'compliant': convert_numpy_types(icd10_violations) == 0
                    },
                    'loinc': {
                        'score': convert_numpy_types(loinc_score),
                        'risk_level': loinc_risk,
                        'violations_count': convert_numpy_types(loinc_violations),
                        'compliant': convert_numpy_types(loinc_violations) == 0
                    },
                    'cpt': {
                        'score': convert_numpy_types(cpt_score),
                        'risk_level': cpt_risk,
                        'violations_count': convert_numpy_types(cpt_violations),
                        'compliant': convert_numpy_types(cpt_violations) == 0
                    }
                }
            },
            'template_applied': getattr(self, 'template_applied', None),
            'all_violations': all_violations_dict,
            'overall_score': convert_numpy_types(overall_score),
            'risk_level': overall_risk
        }
        
        return report

    # Implement dummy _generate_hipaa_report, _generate_gdpr_report, etc., if not already present. 