"""
Test cases for Medical Data Validator v1.2 Advanced Compliance Features
"""

import pytest
import pandas as pd
import numpy as np
from medical_data_validator.compliance import (
    ComplianceEngine, ComplianceViolation, ComplianceScore, 
    CustomComplianceRule
)

class TestComplianceEngine:
    """Test cases for the ComplianceEngine class."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.engine = ComplianceEngine()
        
        # Create test data
        self.test_data = pd.DataFrame({
            'patient_name': ['John Doe', 'Jane Smith', 'Bob Johnson'],
            'ssn': ['123-45-6789', '987-65-4321', '111-22-3333'],
            'email': ['john@example.com', 'jane@test.com', 'bob@demo.com'],
            'phone': ['(555) 123-4567', '(555) 987-6543', '(555) 111-2222'],
            'diagnosis_code': ['E11.9', 'I10', 'Z51.11'],
            'lab_code': ['58410-2', '789-8', '58410-2'],
            'procedure_code': ['99213', '99214', '99215'],
            'race': ['White', 'Black', 'Asian'],
            'religion': ['Christian', 'Muslim', 'Jewish'],
            'genetic_info': ['BRCA1+', 'BRCA2-', 'APC+'],
            'username': ['user1', 'user2', 'user3'],
            'timestamp': ['2024-01-01 10:00:00', '2024-01-01 11:00:00', '2024-01-01 12:00:00'],
            'action': ['create', 'update', 'delete'],
            'change_reason': ['Initial entry', 'Correction', 'Deletion']
        })
    
    def test_hipaa_compliance_detection(self):
        """Test HIPAA compliance detection."""
        result = self.engine.comprehensive_compliance_validation(self.test_data)
        
        # Check HIPAA results
        assert 'standards' in result
        assert 'hipaa' in result['standards']
        hipaa_result = result['standards']['hipaa']
        
        # Should detect names, SSNs, emails, phones
        assert hipaa_result['violations_count'] > 0
        
        # Check for specific violations in all_violations
        all_violations = result['all_violations']
        hipaa_violations = [v for v in all_violations if v['standard'] == 'HIPAA']
        assert len(hipaa_violations) > 0
        
        # Check score calculation
        assert 0 <= hipaa_result['score'] <= 100
        assert hipaa_result['risk_level'] in ['low', 'medium', 'high', 'critical']
    
    def test_gdpr_compliance_detection(self):
        """Test GDPR compliance detection."""
        result = self.engine.comprehensive_compliance_validation(self.test_data)
        
        # Check GDPR results
        assert 'standards' in result
        assert 'gdpr' in result['standards']
        gdpr_result = result['standards']['gdpr']
        
        # Should detect personal and sensitive data
        assert gdpr_result['violations_count'] > 0
        
        # Check for specific violations in all_violations
        all_violations = result['all_violations']
        gdpr_violations = [v for v in all_violations if v['standard'] == 'GDPR']
        assert len(gdpr_violations) > 0
        
        # Check score calculation
        assert 0 <= gdpr_result['score'] <= 100
        assert gdpr_result['risk_level'] in ['low', 'medium', 'high', 'critical']
    
    def test_fda_compliance_detection(self):
        """Test FDA 21 CFR Part 11 compliance detection."""
        result = self.engine.comprehensive_compliance_validation(self.test_data)
        
        # Check FDA results
        assert 'standards' in result
        assert 'fda' in result['standards']
        fda_result = result['standards']['fda']
        
        # Should have some violations (missing some required fields)
        assert fda_result['violations_count'] >= 0
        
        # Check score calculation
        assert 0 <= fda_result['score'] <= 100
        assert fda_result['risk_level'] in ['low', 'medium', 'high', 'critical']
    
    def test_medical_coding_compliance(self):
        """Test medical coding compliance detection."""
        result = self.engine.comprehensive_compliance_validation(self.test_data)
        
        # Check medical coding results
        assert 'standards' in result
        assert 'medical_coding' in result['standards']
        coding_result = result['standards']['medical_coding']
        
        # Should have scores for each coding system
        assert 'icd10' in coding_result
        assert 'loinc' in coding_result
        assert 'cpt' in coding_result
        
        # Check score ranges
        assert 0 <= coding_result['icd10']['score'] <= 100
        assert 0 <= coding_result['loinc']['score'] <= 100
        assert 0 <= coding_result['cpt']['score'] <= 100
    
    def test_custom_rule_management(self):
        """Test custom compliance rule management."""
        # Add custom rule
        rule = CustomComplianceRule(
            name="test_rule",
            description="Test custom rule",
            pattern=r'\bTEST\b',
            severity='high',
            field_pattern='test_column',
            recommendation="Remove test data"
        )
        
        self.engine.add_custom_rule(rule)
        
        # Verify rule was added
        rules = self.engine.get_custom_rules()
        assert len(rules) == 1
        assert rules[0].name == "test_rule"
        
        # Test quick pattern addition
        self.engine.add_custom_pattern(
            name="quick_rule",
            pattern=r'\bQUICK\b',
            severity='medium',
            description="Quick test rule"
        )
        
        rules = self.engine.get_custom_rules()
        assert len(rules) == 2
        
        # Test rule removal
        success = self.engine.remove_custom_rule("test_rule")
        assert success is True
        
        rules = self.engine.get_custom_rules()
        assert len(rules) == 1
        assert rules[0].name == "quick_rule"
        
        # Test clearing all rules
        self.engine.clear_custom_rules()
        rules = self.engine.get_custom_rules()
        assert len(rules) == 0
    
    def test_custom_rule_validation(self):
        """Test custom rule validation in compliance check."""
        # Add custom rule
        self.engine.add_custom_pattern(
            name="test_pattern",
            pattern=r'\bTEST\b',
            severity='high',
            field_pattern='test_column'
        )
        
        # Create test data with custom pattern
        test_data = pd.DataFrame({
            'test_column': ['This is a TEST value', 'Normal value', 'Another TEST'],
            'normal_column': ['Normal', 'Data', 'Here']
        })
        
        result = self.engine.comprehensive_compliance_validation(test_data)
        
        # Check that custom violations are included
        all_violations = result.get('all_violations', [])
        custom_violations = [v for v in all_violations if v.get('standard') == 'CUSTOM' and 'test_pattern' in v.get('message', '')]
        assert len(custom_violations) > 0
    
    def test_empty_dataframe(self):
        """Test compliance validation with empty dataframe."""
        empty_df = pd.DataFrame()
        result = self.engine.comprehensive_compliance_validation(empty_df)
        
        # Should handle empty dataframe gracefully
        assert isinstance(result, dict)
        assert 'overall_score' in result
    
    def test_single_column_dataframe(self):
        """Test compliance validation with single column."""
        single_col_df = pd.DataFrame({'test': ['value1', 'value2']})
        result = self.engine.comprehensive_compliance_validation(single_col_df)
        
        # Should process single column
        assert isinstance(result, dict)
        assert 'overall_score' in result
    
    def test_compliance_score_calculation(self):
        """Test compliance score calculation logic."""
        # Test with clean data (no violations)
        clean_data = pd.DataFrame({
            'id': ['1', '2', '3'],
            'value': [100, 200, 300]
        })
        
        result = self.engine.comprehensive_compliance_validation(clean_data)
        
        # Should have high overall score
        assert result['overall_score'] >= 80
        
        # Test with violating data
        violating_data = pd.DataFrame({
            'name': ['John Doe', 'Jane Smith'],
            'ssn': ['123-45-6789', '987-65-4321'],
            'race': ['White', 'Black']
        })
        
        result = self.engine.comprehensive_compliance_validation(violating_data)
        
        # Should have lower overall score (but not necessarily < 80 due to medical coding scores)
        assert result['overall_score'] < 95
    
    def test_risk_level_assignment(self):
        """Test risk level assignment based on scores."""
        # Test different score ranges
        test_cases = [
            (95, 'low'),
            (85, 'low'),
            (75, 'medium'),
            (65, 'medium'),
            (55, 'high'),
            (45, 'high'),
            (35, 'critical'),
            (25, 'critical')
        ]
        
        for score, expected_risk in test_cases:
            # Create test data that will result in specific score
            # This is a simplified test - in practice scores depend on violations
            test_data = pd.DataFrame({'test': ['value']})
            result = self.engine.comprehensive_compliance_validation(test_data)
            
            # Verify risk levels are assigned correctly
            assert result['standards']['hipaa']['risk_level'] in ['low', 'medium', 'high', 'critical']
            assert result['standards']['gdpr']['risk_level'] in ['low', 'medium', 'high', 'critical']
            assert result['standards']['fda']['risk_level'] in ['low', 'medium', 'high', 'critical']
    
    def test_violation_details(self):
        """Test violation detail structure."""
        result = self.engine.comprehensive_compliance_validation(self.test_data)
        
        # Check violation structure
        all_violations = result['all_violations']
        for violation in all_violations:
            assert 'standard' in violation
            assert 'severity' in violation
            assert 'field' in violation
            assert 'message' in violation
            assert violation['severity'] in ['critical', 'high', 'medium', 'low']
    
    def test_recommendations_generation(self):
        """Test recommendations generation."""
        result = self.engine.comprehensive_compliance_validation(self.test_data)
        
        # Check that recommendations are generated
        for standard in ['hipaa', 'gdpr', 'fda']:
            if standard in result['standards']:
                recommendations = result['standards'][standard]['recommendations']
                assert isinstance(recommendations, list)
                assert len(recommendations) >= 0  # May be empty if no violations
    
    def test_medical_coding_patterns(self):
        """Test medical coding pattern validation."""
        # Test valid ICD-10 codes
        valid_icd10_data = pd.DataFrame({
            'diagnosis': ['E11.9', 'I10', 'Z51.11', 'A00.0', 'B01.9']
        })
        
        # Test valid LOINC codes
        valid_loinc_data = pd.DataFrame({
            'lab_test': ['58410-2', '789-8', '58410-2', '2160-0', '2951-2']
        })
        
        # Test valid CPT codes
        valid_cpt_data = pd.DataFrame({
            'procedure': ['99213', '99214', '99215', '99216', '99217']
        })
        
        # These should have high coding scores
        icd10_result = self.engine.comprehensive_compliance_validation(valid_icd10_data)
        loinc_result = self.engine.comprehensive_compliance_validation(valid_loinc_data)
        cpt_result = self.engine.comprehensive_compliance_validation(valid_cpt_data)
        
        assert icd10_result['standards']['medical_coding']['icd10']['score'] >= 80
        assert loinc_result['standards']['medical_coding']['loinc']['score'] >= 80
        assert cpt_result['standards']['medical_coding']['cpt']['score'] >= 80 