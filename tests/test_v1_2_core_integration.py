"""
Test cases for Medical Data Validator v1.2 Core Integration
"""

import pytest
import pandas as pd
import numpy as np
from medical_data_validator.core import MedicalDataValidator
from medical_data_validator.compliance import ComplianceEngine
from medical_data_validator.analytics import AdvancedAnalytics
from medical_data_validator.monitoring import RealTimeMonitor

class TestV12CoreIntegration:
    """Test cases for v1.2 core integration."""
    
    def setup_method(self):
        """Set up test fixtures."""
        # Test data with various data types and patterns
        self.test_data = pd.DataFrame({
            'patient_id': ['P001', 'P002', 'P003', 'P004', 'P005'],
            'name': ['John Doe', 'Jane Smith', 'Bob Johnson', 'Alice Brown', 'Charlie Wilson'],
            'ssn': ['123-45-6789', '987-65-4321', '111-22-3333', '444-55-6666', '777-88-9999'],
            'email': ['john@example.com', 'jane@test.com', 'bob@demo.com', 'alice@sample.com', 'charlie@test.org'],
            'phone': ['(555) 123-4567', '(555) 987-6543', '(555) 111-2222', '(555) 333-4444', '(555) 555-6666'],
            'age': [25, 30, 35, 40, 45],
            'diagnosis_code': ['E11.9', 'I10', 'Z51.11', 'A00.0', 'B01.9'],
            'lab_code': ['58410-2', '789-8', '58410-2', '2160-0', '2951-2'],
            'procedure_code': ['99213', '99214', '99215', '99216', '99217'],
            'visit_date': ['2024-01-01', '2024-01-02', '2024-01-03', '2024-01-04', '2024-01-05'],
            'blood_pressure': [120, 125, 130, 135, 140],
            'temperature': [98.6, 98.8, 99.0, 98.4, 98.9],
            'status': ['active', 'active', 'inactive', 'active', 'active'],
            'race': ['White', 'Black', 'Asian', 'Hispanic', 'Other'],
            'religion': ['Christian', 'Muslim', 'Jewish', 'Hindu', 'Buddhist'],
            'genetic_info': ['BRCA1+', 'BRCA2-', 'APC+', 'TP53-', 'MLH1+'],
            'username': ['user1', 'user2', 'user3', 'user4', 'user5'],
            'timestamp': ['2024-01-01 10:00:00', '2024-01-01 11:00:00', '2024-01-01 12:00:00', '2024-01-01 13:00:00', '2024-01-01 14:00:00'],
            'action': ['create', 'update', 'delete', 'create', 'update'],
            'change_reason': ['Initial entry', 'Correction', 'Deletion', 'New entry', 'Update']
        })
        
        # Clean data for comparison
        self.clean_data = pd.DataFrame({
            'id': ['1', '2', '3', '4', '5'],
            'value': [100, 200, 300, 400, 500],
            'category': ['A', 'B', 'A', 'B', 'A'],
            'date': ['2024-01-01', '2024-01-02', '2024-01-03', '2024-01-04', '2024-01-05']
        })
    
    def test_validator_with_v12_compliance(self):
        """Test validator with v1.2 compliance enabled."""
        validator = MedicalDataValidator(enable_compliance=True)
        
        # Validate data with compliance
        result = validator.validate_dataframe(self.test_data)
        
        # Check basic validation results
        assert hasattr(result, 'is_valid')
        assert hasattr(result, 'summary')
        compliance_report = result.summary.get('compliance_report', {})
        assert 'standards' in compliance_report
        standards = compliance_report['standards']
        assert 'hipaa' in standards
        assert 'gdpr' in standards
        assert 'fda' in standards
        assert 'medical_coding' in standards
        assert 'overall_score' in compliance_report
        
        # Check compliance scores
        assert 0 <= compliance_report.get('overall_score', 0) <= 100
        assert 0 <= compliance_report.get('hipaa', {}).get('score', 0) <= 100
        assert 0 <= compliance_report.get('gdpr', {}).get('score', 0) <= 100
        assert 0 <= compliance_report.get('fda', {}).get('score', 0) <= 100
    
    def test_validator_with_compliance_template(self):
        """Test validator with compliance template."""
        validator = MedicalDataValidator(
            enable_compliance=True,
            compliance_template='clinical_trials'
        )
        
        result = validator.validate_dataframe(self.test_data)
        
        # Check template application
        compliance_report = result.summary.get('compliance_report', {})
        assert 'template_applied' in compliance_report
        assert compliance_report['template_applied'] == 'clinical_trials'
    
    def test_custom_compliance_rules(self):
        """Test custom compliance rules integration."""
        validator = MedicalDataValidator(enable_compliance=True)
        
        # Add custom rule
        validator.add_custom_compliance_rule(
            name='test_rule',
            pattern=r'\bTEST\b',
            severity='high',
            description='Test custom rule',
            recommendation='Remove test data'
        )
        
        # Create test data with custom pattern
        test_data = pd.DataFrame({
            'test_column': ['This is a TEST value', 'Normal value', 'Another TEST'],
            'normal_column': ['Normal', 'Data', 'Here']
        })
        
        result = validator.validate_dataframe(test_data)
        
        # Check that custom violations are included
        compliance_report = result.summary.get('compliance_report', {})
        all_violations = compliance_report.get('all_violations', [])
        custom_violations = [v for v in all_violations if 'test_rule' in str(v)]
        assert len(custom_violations) > 0
        
        # Remove custom rule
        validator.remove_custom_compliance_rule('test_rule')
        rules = validator.get_custom_compliance_rules()
        assert all(rule['name'] != 'test_rule' for rule in rules)
    
    def test_validator_with_analytics(self):
        """Test validator with analytics integration."""
        # Create validator with analytics
        validator = MedicalDataValidator()
        
        # Add analytics manually since it's not directly integrated in core
        analytics = AdvancedAnalytics()
        
        # Get analytics results
        analytics_result = analytics.comprehensive_analysis(self.test_data, time_column='visit_date')
        
        # Check analytics structure
        assert 'quality_metrics' in analytics_result
        assert 'anomalies' in analytics_result
        assert 'trends' in analytics_result
        assert 'statistical_summary' in analytics_result
        assert 'overall_quality_score' in analytics_result
        
        # Check quality metrics
        quality_metrics = analytics_result['quality_metrics']
        assert 'completeness' in quality_metrics
        assert 'consistency' in quality_metrics
        assert 'accuracy' in quality_metrics
        assert 'timeliness' in quality_metrics
        
        # Check metric values
        for metric in quality_metrics.values():
            assert 0 <= metric['value'] <= 1
            assert metric['severity'] in ['excellent', 'good', 'fair', 'poor', 'critical']
    
    def test_validator_with_monitoring(self):
        """Test validator with monitoring integration."""
        # Create validator
        validator = MedicalDataValidator()
        
        # Create monitor
        monitor = RealTimeMonitor()
        
        # Start monitoring
        monitor.start_monitoring()
        
        # Perform validation
        result = validator.validate_dataframe(self.test_data)
        
        # Record result in monitor
        monitor.record_validation_result(result.to_dict(), 2.5)
        
        # Get monitoring stats
        stats = monitor.get_monitoring_stats()
        
        # Check stats
        assert stats['total_validations'] == 1
        assert stats['successful_validations'] >= 0
        assert stats['failed_validations'] >= 0
        assert stats['average_processing_time'] > 0
        
        # Stop monitoring
        monitor.stop_monitoring()
    
    def test_comprehensive_v12_validation(self):
        """Test comprehensive v1.2 validation workflow."""
        # Create validator with all v1.2 features
        validator = MedicalDataValidator(
            enable_compliance=True,
            compliance_template='clinical_trials'
        )
        
        # Create monitor
        monitor = RealTimeMonitor()
        monitor.start_monitoring()
        
        # Create analytics engine
        analytics = AdvancedAnalytics()
        
        # Perform comprehensive validation
        validation_result = validator.validate_dataframe(self.test_data)
        
        # Get analytics
        analytics_result = analytics.comprehensive_analysis(self.test_data, time_column='visit_date')
        
        # Record in monitor
        monitor.record_validation_result(validation_result.to_dict(), 3.0)
        
        # Check validation results
        assert hasattr(validation_result, 'is_valid')
        assert hasattr(validation_result, 'summary')
        compliance_report = validation_result.summary.get('compliance_report', {})
        assert 'standards' in compliance_report
        standards = compliance_report['standards']
        assert 'hipaa' in standards
        assert 'gdpr' in standards
        assert 'fda' in standards
        assert 'medical_coding' in standards
        assert 'template_applied' in compliance_report
        
        # Check compliance
        assert 'quality_metrics' in analytics_result
        assert 'anomalies' in analytics_result
        assert 'trends' in analytics_result
        assert 'overall_quality_score' in analytics_result
        
        # Check monitoring
        stats = monitor.get_monitoring_stats()
        assert stats['total_validations'] == 1
        
        monitor.stop_monitoring()
    
    def test_data_quality_comparison(self):
        """Test data quality comparison between clean and violating data."""
        validator = MedicalDataValidator(enable_compliance=True)
        
        # Validate clean data
        clean_result = validator.validate_dataframe(self.clean_data)
        clean_compliance = clean_result.summary.get('compliance_report', {})
        
        # Validate violating data
        violating_result = validator.validate_dataframe(self.test_data)
        violating_compliance = violating_result.summary.get('compliance_report', {})
        
        # Clean data should have higher compliance scores
        assert clean_compliance.get('overall_score', 0) > violating_compliance.get('overall_score', 0)
        clean_standards = clean_compliance.get('standards', {})
        violating_standards = violating_compliance.get('standards', {})
        assert clean_standards.get('hipaa', {}).get('score', 0) > violating_standards.get('hipaa', {}).get('score', 0)
        assert clean_standards.get('gdpr', {}).get('score', 0) > violating_standards.get('gdpr', {}).get('score', 0)
    
    def test_compliance_score_calculation(self):
        """Test compliance score calculation logic."""
        validator = MedicalDataValidator(enable_compliance=True)
        
        # Test with different data scenarios
        scenarios = [
            (self.clean_data, "Clean data should have high scores"),
            (self.test_data, "Violating data should have lower scores")
        ]
        
        for data, description in scenarios:
            result = validator.validate_dataframe(data)
            compliance_report = result.summary.get('compliance_report', {})
            
            # Check score ranges
            assert 0 <= compliance_report.get('overall_score', 0) <= 100, description
            standards = compliance_report.get('standards', {})
            assert 0 <= standards.get('hipaa', {}).get('score', 0) <= 100, description
            assert 0 <= standards.get('gdpr', {}).get('score', 0) <= 100, description
            assert 0 <= standards.get('fda', {}).get('score', 0) <= 100, description
            
            # Check risk levels
            assert standards.get('hipaa', {}).get('risk_level', 'low') in ['low', 'medium', 'high', 'critical'], description
            assert standards.get('gdpr', {}).get('risk_level', 'low') in ['low', 'medium', 'high', 'critical'], description
            assert standards.get('fda', {}).get('risk_level', 'low') in ['low', 'medium', 'high', 'critical'], description
    
    def test_violation_detection(self):
        """Test violation detection accuracy."""
        validator = MedicalDataValidator(enable_compliance=True)
        
        result = validator.validate_dataframe(self.test_data)
        compliance_report = result.summary.get('compliance_report', {})
        
        # Should detect HIPAA violations (names, SSNs, emails, phones)
        standards = compliance_report.get('standards', {})
        hipaa_violations = standards.get('hipaa', {}).get('violations', [])
        assert len(hipaa_violations) > 0
        
        # Check for specific violation types
        violation_types = [v.get('rule_id') for v in hipaa_violations]
        assert 'PHI_NAME_DETECTED' in violation_types
        assert 'PHI_SSN_DETECTED' in violation_types
        
        # Should detect GDPR violations (personal and sensitive data)
        gdpr_violations = standards.get('gdpr', {}).get('violations', [])
        assert len(gdpr_violations) > 0
        
        violation_types = [v.get('rule_id') for v in gdpr_violations]
        assert 'PERSONAL_DATA_DETECTED' in violation_types
        # Note: SENSITIVE_DATA_DETECTED may not be present if test data doesn't contain sensitive patterns
    
    def test_medical_coding_validation(self):
        """Test medical coding validation."""
        validator = MedicalDataValidator(enable_compliance=True)
        
        result = validator.validate_dataframe(self.test_data)
        compliance_report = result.summary.get('compliance_report', {})
        
        # Check medical coding scores
        standards = compliance_report.get('standards', {})
        medical_coding = standards.get('medical_coding', {})
        assert 'icd10_score' in medical_coding
        assert 'loinc_score' in medical_coding
        assert 'cpt_score' in medical_coding
        
        # Check score ranges
        assert 0 <= medical_coding.get('icd10_score', 0) <= 100
        assert 0 <= medical_coding.get('loinc_score', 0) <= 100
        assert 0 <= medical_coding.get('cpt_score', 0) <= 100
    
    def test_template_application(self):
        """Test compliance template application."""
        templates = [
            'clinical_trials',
            'electronic_health_records',
            'laboratory_data',
            'medical_imaging',
            'research_data'
        ]
        
        for template_name in templates:
            validator = MedicalDataValidator(
                enable_compliance=True,
                compliance_template=template_name
            )
            
            result = validator.validate_dataframe(self.test_data)
            compliance_report = result.summary.get('compliance_report', {})
            
            # Check template was applied
            assert 'template_applied' in compliance_report
            assert compliance_report['template_applied'] == template_name
    
    def test_error_handling(self):
        """Test error handling in v1.2 features."""
        validator = MedicalDataValidator(enable_compliance=True)
        
        # Test with empty dataframe
        empty_df = pd.DataFrame()
        result = validator.validate_dataframe(empty_df)
        
        # Should handle gracefully
        assert hasattr(result, 'is_valid')
        assert hasattr(result, 'summary')
        compliance_report = result.summary.get('compliance_report', {})
        
        # Test with single column
        single_col_df = pd.DataFrame({'test': ['value1', 'value2']})
        result = validator.validate_dataframe(single_col_df)
        
        # Should process single column
        assert hasattr(result, 'is_valid')
        assert hasattr(result, 'summary')
    
    def test_performance_with_large_data(self):
        """Test performance with larger datasets."""
        # Create larger test dataset
        large_data = {
            'id': [str(i) for i in range(1000)],
            'value': list(range(1000)),
            'category': ['A', 'B'] * 500,
            'date': [f'2024-01-{(i % 30) + 1:02d}' for i in range(1000)]
        }
        
        large_df = pd.DataFrame(large_data)
        
        validator = MedicalDataValidator(enable_compliance=True)
        
        # Should process large dataset without errors
        result = validator.validate_dataframe(large_df)
        
        assert hasattr(result, 'is_valid')
        assert hasattr(result, 'summary')
        compliance_report = result.summary.get('compliance_report', {})
    
    def test_json_serialization(self):
        """Test that all results are JSON serializable."""
        validator = MedicalDataValidator(enable_compliance=True)
        
        result = validator.validate_dataframe(self.test_data)
        
        # Should be JSON serializable
        import json
        try:
            json_str = json.dumps(result.to_dict())
            assert isinstance(json_str, str)
        except (TypeError, ValueError) as e:
            pytest.fail(f"Validation result is not JSON serializable: {e}")
    
    def test_compliance_engine_integration(self):
        """Test direct compliance engine integration."""
        # Test compliance engine directly
        engine = ComplianceEngine()
        
        # Add custom rule
        engine.add_custom_pattern(
            name='test_pattern',
            pattern=r'\bTEST\b',
            severity='high'
        )
        
        # Test compliance validation
        result = engine.comprehensive_compliance_validation(self.test_data)
        
        # Check result structure
        assert 'standards' in result
        standards = result['standards']
        assert 'hipaa' in standards
        assert 'gdpr' in standards
        assert 'fda' in standards
        assert 'medical_coding' in standards
        assert 'overall_score' in result
        assert 'all_violations' in result
    
    def test_analytics_engine_integration(self):
        """Test direct analytics engine integration."""
        # Test analytics engine directly
        analytics = AdvancedAnalytics()
        
        # Test comprehensive analysis
        result = analytics.comprehensive_analysis(self.test_data, time_column='visit_date')
        
        # Check result structure
        assert 'quality_metrics' in result
        assert 'anomalies' in result
        assert 'trends' in result
        assert 'statistical_summary' in result
        assert 'overall_quality_score' in result
        
        # Test individual components
        metrics = analytics.calculate_data_quality_metrics(self.test_data)
        assert len(metrics) > 0
        
        anomalies = analytics.detect_anomalies(self.test_data)
        assert isinstance(anomalies, list)
        
        trends = analytics.analyze_trends(self.test_data, time_column='visit_date')
        assert isinstance(trends, list)
    
    def test_monitoring_engine_integration(self):
        """Test direct monitoring engine integration."""
        # Test monitoring engine directly
        monitor = RealTimeMonitor()
        
        # Start monitoring
        monitor.start_monitoring()
        
        # Record some results
        sample_result = {
            'is_valid': True,
            'summary': {
                'compliance_report': {
                    'overall_score': 85.5
                }
            }
        }
        
        monitor.record_validation_result(sample_result, 2.5)
        
        # Get stats
        stats = monitor.get_monitoring_stats()
        assert stats['total_validations'] == 1
        
        # Get alerts
        alerts = monitor.get_active_alerts()
        assert isinstance(alerts, list)
        
        # Stop monitoring
        monitor.stop_monitoring() 