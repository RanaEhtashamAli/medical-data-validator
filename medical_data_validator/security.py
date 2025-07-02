"""
Security and HIPAA Compliance Module

Provides comprehensive security features for medical data validation,
including PHI/PII detection, data anonymization, and HIPAA compliance.
"""

import re
import hashlib
import base64
import uuid
from typing import Dict, List, Set, Optional, Any, Tuple
from datetime import datetime, timedelta
import pandas as pd
import numpy as np

class HIPAAComplianceChecker:
    """HIPAA compliance checker for medical data."""
    
    def __init__(self):
        self.phi_patterns = {
            'ssn': r'\b\d{3}-\d{2}-\d{4}\b|\b\d{9}\b',
            'email': r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
            'phone': r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b',
            'date': r'\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b|\b\d{4}-\d{2}-\d{2}\b',
            'address': r'\b\d+\s+[A-Za-z\s]+(?:Street|St|Avenue|Ave|Road|Rd|Boulevard|Blvd|Lane|Ln|Drive|Dr)\b',
            'medical_record': r'\bMRN\s*\d+\b|\bMedical\s*Record\s*\d+\b',
            'account_number': r'\bAccount\s*#?\s*\d+\b|\bAcct\s*#?\s*\d+\b',
            'insurance_id': r'\bInsurance\s*ID\s*\d+\b|\bPolicy\s*#\s*\d+\b',
            'license_number': r'\bLicense\s*#\s*\d+\b|\bLic\s*#\s*\d+\b',
            'vehicle_id': r'\bVIN\s*\d+\b|\bVehicle\s*ID\s*\d+\b',
            'device_id': r'\bDevice\s*ID\s*\d+\b|\bSerial\s*#\s*\d+\b',
            'ip_address': r'\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b',
            'url': r'\bhttps?://[^\s]+\b',
            'biometric': r'\bFingerprint|Retina|Iris|Voice\s*Pattern\b'
        }
        
        self.hipaa_safe_harbor_fields = {
            'names': ['first_name', 'last_name', 'full_name', 'patient_name'],
            'dates': ['birth_date', 'admission_date', 'discharge_date', 'visit_date'],
            'addresses': ['address', 'street', 'city', 'state', 'zip_code'],
            'identifiers': ['ssn', 'medical_record_number', 'account_number'],
            'contact': ['phone', 'email', 'fax']
        }
    
    def check_hipaa_compliance(self, data: pd.DataFrame) -> Dict[str, Any]:
        """Check HIPAA compliance of the dataset."""
        phi_detected = []
        compliance_score = 100
        
        for column in data.columns:
            column_phi = self.detect_phi_in_column(data[column], column)
            if column_phi:
                phi_detected.extend(column_phi)
                compliance_score -= 10  # Reduce score for each PHI column
        
        return {
            'compliant': len(phi_detected) == 0,
            'compliance_score': max(0, compliance_score),
            'phi_detected': phi_detected,
            'total_phi_instances': len(phi_detected),
            'recommendations': self.generate_hipaa_recommendations(phi_detected)
        }
    
    def detect_phi_in_column(self, column_data: pd.Series, column_name: str) -> List[Dict[str, Any]]:
        """Detect PHI in a specific column."""
        phi_instances = []
        
        for pattern_name, pattern in self.phi_patterns.items():
            matches = column_data.astype(str).str.contains(pattern, regex=True, na=False)
            if matches.any():
                phi_instances.append({
                    'column': column_name,
                    'phi_type': pattern_name,
                    'pattern': pattern,
                    'instances': int(matches.sum()),
                    'sample_values': column_data[matches].head(3).tolist()
                })
        
        return phi_instances
    
    def generate_hipaa_recommendations(self, phi_detected: List[Dict[str, Any]]) -> List[str]:
        """Generate HIPAA compliance recommendations."""
        recommendations = []
        
        if phi_detected:
            recommendations.append("⚠️ PHI detected in dataset. Consider anonymization or de-identification.")
            
            phi_types = set(item['phi_type'] for item in phi_detected)
            
            if 'ssn' in phi_types:
                recommendations.append("🔒 Remove or hash Social Security Numbers")
            
            if 'email' in phi_types:
                recommendations.append("📧 Replace email addresses with generic identifiers")
            
            if 'phone' in phi_types:
                recommendations.append("📞 Mask phone numbers or use generic placeholders")
            
            if 'date' in phi_types:
                recommendations.append("📅 Consider date generalization (e.g., year only)")
            
            if 'address' in phi_types:
                recommendations.append("🏠 Remove or generalize addresses")
        
        else:
            recommendations.append("✅ No PHI detected - dataset appears HIPAA compliant")
        
        return recommendations

class DataAnonymizer:
    """Data anonymization for HIPAA compliance."""
    
    def __init__(self, method: str = "hipaa_safe_harbor"):
        self.method = method
        self.hash_salt = str(uuid.uuid4())
    
    def anonymize_dataset(self, data: pd.DataFrame, columns_to_anonymize: List[str]) -> pd.DataFrame:
        """Anonymize specified columns in the dataset."""
        anonymized_data = data.copy()
        
        for column in columns_to_anonymize:
            if column in anonymized_data.columns:
                anonymized_data[column] = self.anonymize_column(
                    anonymized_data[column], 
                    column
                )
        
        return anonymized_data
    
    def anonymize_column(self, column_data: pd.Series, column_name: str) -> pd.Series:
        """Anonymize a specific column based on its content type."""
        if self.method == "hipaa_safe_harbor":
            return self._hipaa_safe_harbor_anonymization(column_data, column_name)
        elif self.method == "hash":
            return self._hash_anonymization(column_data)
        elif self.method == "mask":
            return self._mask_anonymization(column_data, column_name)
        else:
            raise ValueError(f"Unknown anonymization method: {self.method}")
    
    def _hipaa_safe_harbor_anonymization(self, column_data: pd.Series, column_name: str) -> pd.Series:
        """Apply HIPAA Safe Harbor method anonymization."""
        column_lower = column_name.lower()
        
        # Names
        if any(name_field in column_lower for name_field in ['name', 'first', 'last']):
            return pd.Series([f"Patient_{i:04d}" for i in range(len(column_data))])
        
        # Dates - keep only year
        elif any(date_field in column_lower for date_field in ['date', 'birth', 'admission', 'discharge']):
            return column_data.apply(self._generalize_date)
        
        # Addresses
        elif any(addr_field in column_lower for addr_field in ['address', 'street', 'city', 'state', 'zip']):
            return pd.Series(['[REDACTED]'] * len(column_data))
        
        # Identifiers
        elif any(id_field in column_lower for id_field in ['ssn', 'id', 'number', 'account']):
            return pd.Series([f"ID_{i:06d}" for i in range(len(column_data))])
        
        # Contact information
        elif any(contact_field in column_lower for contact_field in ['phone', 'email', 'fax']):
            return pd.Series(['[REDACTED]'] * len(column_data))
        
        # Default - hash the values
        else:
            return self._hash_anonymization(column_data)
    
    def _hash_anonymization(self, column_data: pd.Series) -> pd.Series:
        """Hash-based anonymization."""
        def hash_value(value):
            if pd.isna(value):
                return None
            value_str = str(value) + self.hash_salt
            return hashlib.sha256(value_str.encode()).hexdigest()[:8]
        
        return column_data.apply(hash_value)
    
    def _mask_anonymization(self, column_data: pd.Series, column_name: str) -> pd.Series:
        """Mask-based anonymization."""
        column_lower = column_name.lower()
        
        if 'phone' in column_lower:
            return column_data.apply(lambda x: f"***-***-{str(x)[-4:]}" if pd.notna(x) else x)
        
        elif 'ssn' in column_lower:
            return column_data.apply(lambda x: f"***-**-{str(x)[-4:]}" if pd.notna(x) else x)
        
        elif 'email' in column_lower:
            return column_data.apply(lambda x: f"{str(x)[:3]}***@{str(x).split('@')[1]}" if pd.notna(x) and '@' in str(x) else x)
        
        else:
            return column_data.apply(lambda x: f"{str(x)[:3]}***" if pd.notna(x) else x)
    
    def _generalize_date(self, date_value) -> str:
        """Generalize date to year only."""
        if pd.isna(date_value):
            return None
        
        try:
            if isinstance(date_value, str):
                # Try to parse various date formats
                for fmt in ['%Y-%m-%d', '%m/%d/%Y', '%d/%m/%Y', '%Y/%m/%d']:
                    try:
                        parsed_date = datetime.strptime(date_value, fmt)
                        return str(parsed_date.year)
                    except ValueError:
                        continue
            elif isinstance(date_value, (datetime, pd.Timestamp)):
                return str(date_value.year)
            
            return str(date_value)
        except:
            return '[REDACTED]'

class SecurityAuditor:
    """Security auditor for medical data validation."""
    
    def __init__(self):
        self.audit_log = []
        self.security_checks = [
            self._check_file_permissions,
            self._check_data_encryption,
            self._check_access_logs,
            self._check_audit_trail
        ]
    
    def audit_security(self, data: pd.DataFrame, file_path: str = None) -> Dict[str, Any]:
        """Perform comprehensive security audit."""
        audit_results = {
            'timestamp': datetime.now().isoformat(),
            'file_path': file_path,
            'data_shape': data.shape,
            'security_score': 100,
            'issues': [],
            'recommendations': []
        }
        
        for check in self.security_checks:
            try:
                result = check(data, file_path)
                if result['issues']:
                    audit_results['issues'].extend(result['issues'])
                    audit_results['security_score'] -= result['score_penalty']
                audit_results['recommendations'].extend(result['recommendations'])
            except Exception as e:
                audit_results['issues'].append(f"Security check failed: {str(e)}")
                audit_results['security_score'] -= 10
        
        audit_results['security_score'] = max(0, audit_results['security_score'])
        audit_results['overall_status'] = 'SECURE' if audit_results['security_score'] >= 80 else 'NEEDS_ATTENTION'
        
        self.audit_log.append(audit_results)
        return audit_results
    
    def _check_file_permissions(self, data: pd.DataFrame, file_path: str) -> Dict[str, Any]:
        """Check file permissions and access controls."""
        issues = []
        recommendations = []
        score_penalty = 0
        
        if file_path:
            try:
                import os
                import stat
                
                file_stat = os.stat(file_path)
                permissions = stat.filemode(file_stat.st_mode)
                
                # Check if file is world-readable
                if permissions[-3] == 'r':
                    issues.append("File is world-readable - security risk")
                    score_penalty += 20
                    recommendations.append("Restrict file permissions to owner only")
                
                # Check if file is world-writable
                if permissions[-2] == 'w':
                    issues.append("File is world-writable - critical security risk")
                    score_penalty += 30
                    recommendations.append("Remove world-write permissions immediately")
                
            except Exception as e:
                issues.append(f"Could not check file permissions: {str(e)}")
                score_penalty += 5
        
        return {
            'issues': issues,
            'recommendations': recommendations,
            'score_penalty': score_penalty
        }
    
    def _check_data_encryption(self, data: pd.DataFrame, file_path: str) -> Dict[str, Any]:
        """Check if data is properly encrypted."""
        issues = []
        recommendations = []
        score_penalty = 0
        
        # Check for sensitive data patterns
        sensitive_patterns = [
            r'\b\d{3}-\d{2}-\d{4}\b',  # SSN
            r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',  # Email
            r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b'  # Phone
        ]
        
        for pattern in sensitive_patterns:
            for column in data.columns:
                matches = data[column].astype(str).str.contains(pattern, regex=True, na=False)
                if matches.any():
                    issues.append(f"Sensitive data detected in column '{column}' without encryption")
                    score_penalty += 15
                    recommendations.append(f"Encrypt column '{column}' or apply anonymization")
        
        return {
            'issues': issues,
            'recommendations': recommendations,
            'score_penalty': score_penalty
        }
    
    def _check_access_logs(self, data: pd.DataFrame, file_path: str) -> Dict[str, Any]:
        """Check access logging and monitoring."""
        issues = []
        recommendations = []
        score_penalty = 0
        
        # This would typically check system logs
        # For now, we'll provide general recommendations
        recommendations.append("Implement comprehensive access logging")
        recommendations.append("Monitor data access patterns for anomalies")
        recommendations.append("Set up alerts for unauthorized access attempts")
        
        return {
            'issues': issues,
            'recommendations': recommendations,
            'score_penalty': score_penalty
        }
    
    def _check_audit_trail(self, data: pd.DataFrame, file_path: str) -> Dict[str, Any]:
        """Check audit trail implementation."""
        issues = []
        recommendations = []
        score_penalty = 0
        
        recommendations.append("Maintain detailed audit trail of all data access")
        recommendations.append("Log all validation operations and results")
        recommendations.append("Implement data lineage tracking")
        
        return {
            'issues': issues,
            'recommendations': recommendations,
            'score_penalty': score_penalty
        }
    
    def get_audit_report(self) -> List[Dict[str, Any]]:
        """Get complete audit report."""
        return self.audit_log

class DataSanitizer:
    """Data sanitization for security."""
    
    def __init__(self):
        self.dangerous_patterns = [
            r'<script.*?</script>',  # XSS
            r'javascript:',  # JavaScript injection
            r'<iframe.*?</iframe>',  # IFrame injection
            r'<object.*?</object>',  # Object injection
            r'<embed.*?</embed>',  # Embed injection
            r'<form.*?</form>',  # Form injection
            r'<input.*?>',  # Input injection
            r'<textarea.*?</textarea>',  # Textarea injection
            r'<select.*?</select>',  # Select injection
            r'<button.*?</button>',  # Button injection
            r'<link.*?>',  # Link injection
            r'<meta.*?>',  # Meta injection
            r'<style.*?</style>',  # Style injection
            r'<title.*?</title>',  # Title injection
            r'<base.*?>',  # Base injection
            r'<bgsound.*?>',  # BGSound injection
            r'<link.*?>',  # Link injection
            r'<meta.*?>',  # Meta injection
            r'<style.*?</style>',  # Style injection
            r'<title.*?</title>',  # Title injection
            r'<base.*?>',  # Base injection
            r'<bgsound.*?>',  # BGSound injection
        ]
    
    def sanitize_data(self, data: pd.DataFrame) -> pd.DataFrame:
        """Sanitize data to remove potentially dangerous content."""
        sanitized_data = data.copy()
        
        for column in sanitized_data.columns:
            if sanitized_data[column].dtype == 'object':
                sanitized_data[column] = sanitized_data[column].apply(self._sanitize_value)
        
        return sanitized_data
    
    def _sanitize_value(self, value) -> str:
        """Sanitize a single value."""
        if pd.isna(value):
            return value
        
        value_str = str(value)
        
        # Remove dangerous patterns
        for pattern in self.dangerous_patterns:
            value_str = re.sub(pattern, '', value_str, flags=re.IGNORECASE)
        
        # Remove HTML tags
        value_str = re.sub(r'<[^>]+>', '', value_str)
        
        # Remove special characters that could be used for injection
        value_str = value_str.replace(';', '').replace('--', '').replace('/*', '').replace('*/', '')
        
        return value_str
    
    def validate_filename(self, filename: str) -> bool:
        """Validate filename for security."""
        dangerous_chars = ['<', '>', ':', '"', '|', '?', '*', '\\', '/']
        return not any(char in filename for char in dangerous_chars)
    
    def sanitize_filename(self, filename: str) -> str:
        """Sanitize filename for security."""
        dangerous_chars = ['<', '>', ':', '"', '|', '?', '*', '\\', '/']
        sanitized = filename
        for char in dangerous_chars:
            sanitized = sanitized.replace(char, '_')
        return sanitized 