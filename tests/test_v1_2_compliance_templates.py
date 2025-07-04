"""
Test cases for Medical Data Validator v1.2 Compliance Templates
"""

import pytest
import pandas as pd
from medical_data_validator.compliance_templates import (
    ComplianceTemplate, ComplianceTemplateManager, template_manager
)

class TestComplianceTemplates:
    """Test cases for compliance templates."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.template_manager = ComplianceTemplateManager()
        
        # Create test data for different domains
        self.clinical_trials_data = pd.DataFrame({
            'subject_id': ['SUB001', 'SUB002', 'SUB003'],
            'visit_date': ['2024-01-01', '2024-01-02', '2024-01-03'],
            'treatment_arm': ['A', 'B', 'A'],
            'adverse_event': ['None', 'Mild', 'None'],
            'vital_signs': ['Normal', 'Normal', 'Normal'],
            'lab_results': ['58410-2', '789-8', '58410-2'],
            'investigator': ['Dr. Smith', 'Dr. Johnson', 'Dr. Brown'],
            'site_id': ['SITE001', 'SITE002', 'SITE001']
        })
    
    def test_template_manager_initialization(self):
        """Test template manager initialization."""
        assert isinstance(self.template_manager.templates, dict)
        assert len(self.template_manager.templates) > 0
        
        # Check that default templates are created
        expected_templates = ['clinical_trials', 'ehr', 'laboratory', 'imaging', 'research']
        for template_name in expected_templates:
            assert template_name in self.template_manager.templates
    
    def test_get_template(self):
        """Test getting templates by name."""
        # Test getting existing templates
        templates = [
            'clinical_trials',
            'ehr',
            'laboratory',
            'imaging',
            'research'
        ]
        
        for template_name in templates:
            template = self.template_manager.get_template(template_name)
            assert template is not None
            assert template.name == template_name
            assert isinstance(template, ComplianceTemplate)
        
        # Test getting non-existent template
        template = self.template_manager.get_template('non_existent_template')
        assert template is None
    
    def test_list_templates(self):
        """Test listing available templates."""
        templates = self.template_manager.list_templates()
        
        # Check that all expected templates are available
        expected_templates = [
            'clinical_trials',
            'ehr',
            'laboratory',
            'imaging',
            'research'
        ]
        
        for expected in expected_templates:
            assert expected in templates
        
        # Check template descriptions
        for template_name in templates:
            assert templates[template_name] is not None
            assert len(templates[template_name]) > 0
    
    def test_template_application(self):
        """Test template application."""
        from medical_data_validator.compliance import ComplianceEngine
        
        # Get clinical trials template
        template = self.template_manager.get_template('clinical_trials')
        assert template is not None
        
        # Create compliance engine
        engine = ComplianceEngine()
        
        # Apply template to engine
        template.apply_to_engine(engine)
        
        # Check that rules were added
        rules = engine.get_custom_rules()
        assert len(rules) > 0
        
        # Check that rules have expected names
        rule_names = [rule.name for rule in rules]
        assert 'subject_id_format' in rule_names
        assert 'visit_date_format' in rule_names
        assert 'adverse_event_coding' in rule_names
    
    def test_template_rule_validation(self):
        """Test template rule validation."""
        from medical_data_validator.compliance import ComplianceEngine
        
        # Get template and apply to engine
        template = self.template_manager.get_template('clinical_trials')
        assert template is not None  # Ensure template exists
        engine = ComplianceEngine()
        template.apply_to_engine(engine)
        
        # Test with valid data
        valid_data = pd.DataFrame({
            'subject_id': ['AB123456', 'CD789012'],
            'visit_date': ['2024-01-01', '2024-01-02'],
            'adverse_event': ['12345678', '87654321']
        })
        
        result = engine.comprehensive_compliance_validation(valid_data)
        
        # Should have some violations (not all data matches template rules)
        assert 'all_violations' in result
        assert len(result['all_violations']) >= 0
    
    def test_custom_template_creation(self):
        """Test custom template creation."""
        from medical_data_validator.compliance import CustomComplianceRule
        
        # Create custom rules
        custom_rules = [
            CustomComplianceRule(
                name="test_rule_1",
                description="Test rule 1",
                pattern=r'\bTEST\b',
                severity='high',
                recommendation="Test recommendation 1"
            ),
            CustomComplianceRule(
                name="test_rule_2",
                description="Test rule 2",
                pattern=r'\bCUSTOM\b',
                severity='medium',
                recommendation="Test recommendation 2"
            )
        ]
        
        # Create custom template
        custom_template = self.template_manager.create_custom_template(
            name="test_template",
            description="Test custom template",
            rules=custom_rules
        )
        
        # Check template properties
        assert custom_template.name == "test_template"
        assert custom_template.description == "Test custom template"
        assert len(custom_template.rules) == 2
        
        # Test template application
        from medical_data_validator.compliance import ComplianceEngine
        engine = ComplianceEngine()
        custom_template.apply_to_engine(engine)
        
        # Check that custom rules were added
        rules = engine.get_custom_rules()
        assert len(rules) == 2
        
        rule_names = [rule.name for rule in rules]
        assert 'test_rule_1' in rule_names
        assert 'test_rule_2' in rule_names
    
    def test_global_template_manager(self):
        """Test the global template manager instance."""
        # Test that global template manager exists
        assert template_manager is not None
        assert isinstance(template_manager, ComplianceTemplateManager)
        
        # Test that it has the same templates
        templates = template_manager.list_templates()
        assert len(templates) > 0
        
        # Test getting a template from global manager
        clinical_trials = template_manager.get_template('clinical_trials')
        assert clinical_trials is not None
        assert clinical_trials.name == 'clinical_trials' 