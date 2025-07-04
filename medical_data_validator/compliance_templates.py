"""
Compliance Templates for Medical Data Validator v1.2
Pre-built compliance profiles for different use cases.
"""

from typing import Dict, List, Any
from .compliance import ComplianceEngine, CustomComplianceRule

class ComplianceTemplate:
    """Represents a compliance template with pre-configured rules."""
    
    def __init__(self, name: str, description: str):
        self.name = name
        self.description = description
        self.rules = []
    
    def add_rule(self, rule: CustomComplianceRule) -> None:
        """Add a rule to the template."""
        self.rules.append(rule)
    
    def apply_to_engine(self, engine: ComplianceEngine) -> None:
        """Apply all template rules to a compliance engine."""
        for rule in self.rules:
            engine.add_custom_rule(rule)

class ComplianceTemplateManager:
    """Manages compliance templates."""
    
    def __init__(self):
        self.templates = {}
        self._create_default_templates()
    
    def _create_default_templates(self):
        """Create default compliance templates."""
        
        # Clinical Trials Template
        clinical_trials = ComplianceTemplate(
            name="clinical_trials",
            description="Compliance template for clinical trial data"
        )
        clinical_trials.add_rule(CustomComplianceRule(
            name="subject_id_format",
            description="Subject ID must follow clinical trial format",
            pattern=r'^[A-Z]{2}\d{6}$',
            severity="high",
            field_pattern=r'subject|participant|patient',
            recommendation="Use standard subject ID format: 2 letters + 6 digits"
        ))
        clinical_trials.add_rule(CustomComplianceRule(
            name="visit_date_format",
            description="Visit dates must be in ISO format",
            pattern=r'^\d{4}-\d{2}-\d{2}$',
            severity="medium",
            field_pattern=r'visit|date|time',
            recommendation="Use ISO date format: YYYY-MM-DD"
        ))
        clinical_trials.add_rule(CustomComplianceRule(
            name="adverse_event_coding",
            description="Adverse events must use MedDRA coding",
            pattern=r'^\d{8}$',
            severity="high",
            field_pattern=r'adverse|event|ae',
            recommendation="Use MedDRA preferred terms (8-digit codes)"
        ))
        self.templates["clinical_trials"] = clinical_trials
        
        # EHR Template
        ehr = ComplianceTemplate(
            name="ehr",
            description="Compliance template for Electronic Health Records"
        )
        ehr.add_rule(CustomComplianceRule(
            name="patient_id_format",
            description="Patient ID must follow EHR format",
            pattern=r'^P\d{8}$',
            severity="critical",
            field_pattern=r'patient|id|mrn',
            recommendation="Use standard patient ID format: P + 8 digits"
        ))
        ehr.add_rule(CustomComplianceRule(
            name="vital_signs_range",
            description="Vital signs must be within normal ranges",
            pattern=r'^(0|[1-9]\d{0,2})$',
            severity="medium",
            field_pattern=r'bp|heart_rate|temperature|weight',
            recommendation="Verify vital signs are within expected ranges"
        ))
        ehr.add_rule(CustomComplianceRule(
            name="medication_dosage",
            description="Medication dosages must include units",
            pattern=r'^\d+(\.\d+)?\s*(mg|mcg|g|ml|units?)$',
            severity="high",
            field_pattern=r'dosage|dose|amount',
            recommendation="Include units with all medication dosages"
        ))
        self.templates["ehr"] = ehr
        
        # Laboratory Data Template
        lab = ComplianceTemplate(
            name="laboratory",
            description="Compliance template for laboratory data"
        )
        lab.add_rule(CustomComplianceRule(
            name="lab_result_format",
            description="Lab results must include reference ranges",
            pattern=r'^\d+(\.\d+)?\s*[<>]?\s*\([0-9.-]+\s*-\s*[0-9.-]+\s*[a-zA-Z%]+\)$',
            severity="high",
            field_pattern=r'result|value|level',
            recommendation="Include reference ranges with lab results"
        ))
        lab.add_rule(CustomComplianceRule(
            name="specimen_id_format",
            description="Specimen IDs must follow lab format",
            pattern=r'^SP\d{6}-\d{3}$',
            severity="medium",
            field_pattern=r'specimen|sample|collection',
            recommendation="Use standard specimen ID format: SP + 6 digits + dash + 3 digits"
        ))
        lab.add_rule(CustomComplianceRule(
            name="test_status",
            description="Test status must be valid",
            pattern=r'^(completed|pending|cancelled|failed)$',
            severity="medium",
            field_pattern=r'status|state',
            recommendation="Use valid test status values"
        ))
        self.templates["laboratory"] = lab
        
        # Imaging Data Template
        imaging = ComplianceTemplate(
            name="imaging",
            description="Compliance template for medical imaging data"
        )
        imaging.add_rule(CustomComplianceRule(
            name="dicom_uid_format",
            description="DICOM UIDs must follow standard format",
            pattern=r'^\d+\.\d+\.\d+\.\d+\.\d+\.\d+$',
            severity="high",
            field_pattern=r'dicom|uid|study|series|instance',
            recommendation="Use standard DICOM UID format"
        ))
        imaging.add_rule(CustomComplianceRule(
            name="modality_codes",
            description="Imaging modality must use standard codes",
            pattern=r'^(CT|MR|US|XR|NM|PT|CR|DX|MG|XA|RF|XA)$',
            severity="medium",
            field_pattern=r'modality|type',
            recommendation="Use standard DICOM modality codes"
        ))
        imaging.add_rule(CustomComplianceRule(
            name="image_quality_score",
            description="Image quality scores must be numeric",
            pattern=r'^[1-5]$',
            severity="medium",
            field_pattern=r'quality|score|rating',
            recommendation="Use 1-5 scale for image quality assessment"
        ))
        self.templates["imaging"] = imaging
        
        # Research Data Template
        research = ComplianceTemplate(
            name="research",
            description="Compliance template for research data"
        )
        research.add_rule(CustomComplianceRule(
            name="deidentified_id",
            description="Research IDs must be de-identified",
            pattern=r'^R\d{6}$',
            severity="critical",
            field_pattern=r'id|identifier|subject',
            recommendation="Use de-identified research IDs only"
        ))
        research.add_rule(CustomComplianceRule(
            name="consent_status",
            description="Consent status must be documented",
            pattern=r'^(consented|declined|withdrawn|pending)$',
            severity="critical",
            field_pattern=r'consent|permission',
            recommendation="Document consent status for all participants"
        ))
        research.add_rule(CustomComplianceRule(
            name="data_anonymization",
            description="Check for potential re-identification risks",
            pattern=r'\b(19|20)\d{2}\b',  # Years that could be birth years
            severity="high",
            field_pattern=r'date|birth|age',
            recommendation="Ensure dates don't reveal birth years"
        ))
        self.templates["research"] = research
    
    def get_template(self, name: str) -> ComplianceTemplate | None:
        """Get a template by name."""
        return self.templates.get(name)
    
    def list_templates(self) -> Dict[str, str]:
        """List all available templates."""
        return {name: template.description for name, template in self.templates.items()}
    
    def apply_template(self, template_name: str, engine: ComplianceEngine) -> bool:
        """Apply a template to a compliance engine."""
        template = self.get_template(template_name)
        if template:
            template.apply_to_engine(engine)
            return True
        return False
    
    def create_custom_template(self, name: str, description: str, rules: List[CustomComplianceRule]) -> ComplianceTemplate:
        """Create a custom template."""
        template = ComplianceTemplate(name, description)
        for rule in rules:
            template.add_rule(rule)
        self.templates[name] = template
        return template

# Global template manager instance
template_manager = ComplianceTemplateManager() 