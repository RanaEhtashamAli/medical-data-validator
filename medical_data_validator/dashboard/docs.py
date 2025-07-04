"""
Documentation routes for the Medical Data Validator API v1.2.
Provides both simple documentation and Swagger/OpenAPI integration.
"""

import os
from pathlib import Path
from typing import Dict, Any

from flask import Blueprint, render_template, jsonify, current_app, request
from flask_restx import Api, Resource, fields, Namespace
import markdown

# Create documentation blueprint
docs_bp = Blueprint('docs', __name__, url_prefix='/docs')

# Create API documentation namespace for v1.2
api_docs_v1_2 = Namespace('v1.2', description='Medical Data Validator API v1.2 Documentation')

# Create legacy API documentation namespace
api_docs_legacy = Namespace('api', description='Medical Data Validator API v1.0 Documentation (Legacy)')

# Define API models for v1.2 Swagger documentation
validation_request_model_v1_2 = api_docs_v1_2.model('ValidationRequestV1_2', {
    'patient_id': fields.List(fields.String, description='Patient identifiers', example=['P001', 'P002']),
    'age': fields.List(fields.Integer, description='Patient ages', example=[30, 45]),
    'diagnosis': fields.List(fields.String, description='Diagnosis codes (ICD-10)', example=['E11.9', 'I10']),
    'procedure': fields.List(fields.String, description='Procedure codes (CPT)', example=['99213', '93010']),
    'lab_code': fields.List(fields.String, description='Laboratory codes (LOINC)', example=['58410-2', '789-8']),
    'ssn': fields.List(fields.String, description='Social Security Numbers (for PHI testing)', example=['123-45-6789'])
})

risk_assessment_model = api_docs_v1_2.model('RiskAssessment', {
    'overall_risk': fields.String(description='Overall risk level (low, medium, high)', example='medium'),
    'risk_score': fields.Integer(description='Risk score (0-100)', example=65),
    'risk_factors': fields.List(fields.String, description='List of risk factors', example=['phi_detected', 'missing_audit_trail']),
    'recommendations': fields.List(fields.String, description='Risk mitigation recommendations', 
                                 example=['Remove or encrypt SSN data', 'Implement data anonymization'])
})

analytics_model = api_docs_v1_2.model('Analytics', {
    'data_quality_score': fields.Float(description='Overall data quality score', example=85.0),
    'completeness': fields.Float(description='Data completeness percentage', example=95.0),
    'accuracy': fields.Float(description='Data accuracy percentage', example=90.0),
    'consistency': fields.Float(description='Data consistency percentage', example=80.0),
    'timeliness': fields.Float(description='Data timeliness percentage', example=100.0),
    'validity': fields.Float(description='Data validity percentage', example=88.0)
})

compliance_standard_model = api_docs_v1_2.model('ComplianceStandard', {
    'compliant': fields.Boolean(description='Compliance status'),
    'issues': fields.List(fields.String, description='Compliance issues'),
    'score': fields.Integer(description='Compliance score (0-100)'),
    'risk_level': fields.String(description='Risk level (low, medium, high)')
})

validation_response_model_v1_2 = api_docs_v1_2.model('ValidationResponseV1_2', {
    'success': fields.Boolean(description='Request success status'),
    'is_valid': fields.Boolean(description='Data validation result'),
    'total_issues': fields.Integer(description='Total number of validation issues'),
    'error_count': fields.Integer(description='Number of error-level issues'),
    'warning_count': fields.Integer(description='Number of warning-level issues'),
    'info_count': fields.Integer(description='Number of info-level issues'),
    'compliance_report': fields.Raw(description='Compliance report by standard'),
    'risk_assessment': fields.Nested(risk_assessment_model, description='Risk assessment results'),
    'analytics': fields.Nested(analytics_model, description='Data quality analytics'),
    'issues': fields.List(fields.Raw, description='Detailed validation issues'),
    'summary': fields.Raw(description='Validation summary statistics')
})

compliance_request_model_v1_2 = api_docs_v1_2.model('ComplianceRequestV1_2', {
    'patient_id': fields.List(fields.String, description='Patient identifiers'),
    'diagnosis': fields.List(fields.String, description='Diagnosis codes'),
    'procedure': fields.List(fields.String, description='Procedure codes'),
    'lab_code': fields.List(fields.String, description='Laboratory codes')
})

compliance_response_model_v1_2 = api_docs_v1_2.model('ComplianceResponseV1_2', {
    'hipaa_compliant': fields.Boolean(description='HIPAA compliance status'),
    'gdpr_compliant': fields.Boolean(description='GDPR compliance status'),
    'fda_21_cfr_part_11_compliant': fields.Boolean(description='FDA 21 CFR Part 11 compliance status'),
    'icd10_compliant': fields.Boolean(description='ICD-10 compliance status'),
    'loinc_compliant': fields.Boolean(description='LOINC compliance status'),
    'cpt_compliant': fields.Boolean(description='CPT compliance status'),
    'fhir_compliant': fields.Boolean(description='FHIR compliance status'),
    'omop_compliant': fields.Boolean(description='OMOP compliance status'),
    'overall_compliance_score': fields.Integer(description='Overall compliance score (0-100)'),
    'risk_assessment': fields.Nested(risk_assessment_model, description='Risk assessment results'),
    'details': fields.Raw(description='Detailed compliance information by standard')
})

compliance_template_model = api_docs_v1_2.model('ComplianceTemplate', {
    'name': fields.String(description='Template name'),
    'description': fields.String(description='Template description'),
    'standards': fields.List(fields.String, description='Applicable standards'),
    'required_checks': fields.List(fields.String, description='Required validation checks')
})

compliance_templates_response_model = api_docs_v1_2.model('ComplianceTemplatesResponse', {
    'clinical_trials': fields.Nested(compliance_template_model, description='Clinical trials template'),
    'ehr': fields.Nested(compliance_template_model, description='Electronic health records template'),
    'imaging': fields.Nested(compliance_template_model, description='Medical imaging template'),
    'lab': fields.Nested(compliance_template_model, description='Laboratory data template')
})

analytics_response_model = api_docs_v1_2.model('AnalyticsResponse', {
    'data_quality_score': fields.Float(description='Overall data quality score'),
    'metrics': fields.Nested(analytics_model, description='Data quality metrics'),
    'trends': fields.Raw(description='Historical trends'),
    'anomalies': fields.List(fields.Raw, description='Detected anomalies'),
    'recommendations': fields.List(fields.String, description='Improvement recommendations')
})

monitoring_performance_model = api_docs_v1_2.model('MonitoringPerformance', {
    'response_time_avg': fields.Integer(description='Average response time in ms'),
    'throughput': fields.Integer(description='Requests per second'),
    'error_rate': fields.Float(description='Error rate percentage'),
    'cpu_usage': fields.Float(description='CPU usage percentage'),
    'memory_usage': fields.Float(description='Memory usage percentage')
})

monitoring_compliance_model = api_docs_v1_2.model('MonitoringCompliance', {
    'active_validations': fields.Integer(description='Number of active validations'),
    'compliance_score_avg': fields.Float(description='Average compliance score'),
    'risk_alerts': fields.Integer(description='Number of risk alerts'),
    'last_alert': fields.String(description='Timestamp of last alert')
})

monitoring_alert_model = api_docs_v1_2.model('MonitoringAlert', {
    'type': fields.String(description='Alert type'),
    'message': fields.String(description='Alert message'),
    'severity': fields.String(description='Alert severity'),
    'timestamp': fields.String(description='Alert timestamp')
})

monitoring_response_model = api_docs_v1_2.model('MonitoringResponse', {
    'system_status': fields.String(description='System health status'),
    'uptime': fields.String(description='System uptime'),
    'performance': fields.Nested(monitoring_performance_model, description='Performance metrics'),
    'compliance_monitoring': fields.Nested(monitoring_compliance_model, description='Compliance monitoring'),
    'alerts': fields.List(fields.Nested(monitoring_alert_model), description='Active alerts')
})

health_response_model_v1_2 = api_docs_v1_2.model('HealthResponseV1_2', {
    'status': fields.String(description='API health status'),
    'version': fields.String(description='API version'),
    'timestamp': fields.String(description='Current timestamp'),
    'standards_supported': fields.List(fields.String, description='Supported medical standards'),
    'compliance_templates': fields.List(fields.String, description='Available compliance templates'),
    'features': fields.List(fields.String, description='Available v1.2 features')
})

# Legacy models (v1.0)
validation_request_model = api_docs_legacy.model('ValidationRequest', {
    'patient_id': fields.List(fields.String, description='Patient identifiers', example=['P001', 'P002']),
    'age': fields.List(fields.Integer, description='Patient ages', example=[30, 45]),
    'diagnosis': fields.List(fields.String, description='Diagnosis codes (ICD-10)', example=['E11.9', 'I10']),
    'procedure': fields.List(fields.String, description='Procedure codes (CPT)', example=['99213', '93010']),
    'lab_code': fields.List(fields.String, description='Laboratory codes (LOINC)', example=['58410-2', '789-8'])
})

validation_response_model = api_docs_legacy.model('ValidationResponse', {
    'success': fields.Boolean(description='Request success status'),
    'is_valid': fields.Boolean(description='Data validation result'),
    'total_issues': fields.Integer(description='Total number of validation issues'),
    'error_count': fields.Integer(description='Number of error-level issues'),
    'warning_count': fields.Integer(description='Number of warning-level issues'),
    'info_count': fields.Integer(description='Number of info-level issues'),
    'compliance_report': fields.Raw(description='Compliance report by standard'),
    'issues': fields.List(fields.Raw, description='Detailed validation issues'),
    'summary': fields.Raw(description='Validation summary statistics')
})

compliance_request_model = api_docs_legacy.model('ComplianceRequest', {
    'patient_id': fields.List(fields.String, description='Patient identifiers'),
    'diagnosis': fields.List(fields.String, description='Diagnosis codes'),
    'procedure': fields.List(fields.String, description='Procedure codes')
})

compliance_response_model = api_docs_legacy.model('ComplianceResponse', {
    'hipaa_compliant': fields.Boolean(description='HIPAA compliance status'),
    'icd10_compliant': fields.Boolean(description='ICD-10 compliance status'),
    'loinc_compliant': fields.Boolean(description='LOINC compliance status'),
    'cpt_compliant': fields.Boolean(description='CPT compliance status'),
    'fhir_compliant': fields.Boolean(description='FHIR compliance status'),
    'omop_compliant': fields.Boolean(description='OMOP compliance status'),
    'details': fields.Raw(description='Detailed compliance information')
})

health_response_model = api_docs_legacy.model('HealthResponse', {
    'status': fields.String(description='API health status'),
    'version': fields.String(description='API version'),
    'timestamp': fields.String(description='Current timestamp'),
    'standards_supported': fields.List(fields.String, description='Supported medical standards')
})

profiles_response_model = api_docs_legacy.model('ProfilesResponse', {
    'clinical_trials': fields.String(description='Clinical trial data validation'),
    'ehr': fields.String(description='Electronic health records validation'),
    'imaging': fields.String(description='Medical imaging metadata validation'),
    'lab': fields.String(description='Laboratory data validation')
})

standards_response_model = api_docs_legacy.model('StandardsResponse', {
    'icd10': fields.Raw(description='ICD-10 standard information'),
    'loinc': fields.Raw(description='LOINC standard information'),
    'cpt': fields.Raw(description='CPT standard information'),
    'icd9': fields.Raw(description='ICD-9 standard information'),
    'ndc': fields.Raw(description='NDC standard information'),
    'fhir': fields.Raw(description='FHIR standard information'),
    'omop': fields.Raw(description='OMOP standard information')
})

# Define parameter models for v1.2
validation_params_v1_2 = api_docs_v1_2.parser()
validation_params_v1_2.add_argument('detect_phi', type=bool, default=True, 
                                   help='Enable PHI/PII detection')
validation_params_v1_2.add_argument('quality_checks', type=bool, default=True, 
                                   help='Enable data quality checks')
validation_params_v1_2.add_argument('profile', type=str, 
                                   help='Validation profile (clinical_trials, ehr, imaging, lab)')
validation_params_v1_2.add_argument('standards', type=str, action='append', 
                                   help='Medical standards to check (icd10, loinc, cpt, hipaa, gdpr, fda)')
validation_params_v1_2.add_argument('compliance_template', type=str,
                                   help='Use predefined compliance template')
validation_params_v1_2.add_argument('risk_assessment', type=bool, default=True,
                                   help='Enable risk assessment')

file_upload_params_v1_2 = api_docs_v1_2.parser()
file_upload_params_v1_2.add_argument('file', type='FileStorage', location='files', required=True,
                                    help='Medical data file (CSV, Excel, JSON, Parquet)')
file_upload_params_v1_2.add_argument('detect_phi', type=bool, default=True,
                                    help='Enable PHI/PII detection')
file_upload_params_v1_2.add_argument('quality_checks', type=bool, default=True,
                                    help='Enable data quality checks')
file_upload_params_v1_2.add_argument('profile', type=str,
                                    help='Validation profile')
file_upload_params_v1_2.add_argument('standards', type=str, action='append',
                                    help='Medical standards to check')
file_upload_params_v1_2.add_argument('compliance_template', type=str,
                                    help='Use predefined compliance template')
file_upload_params_v1_2.add_argument('risk_assessment', type=bool, default=True,
                                    help='Enable risk assessment')

analytics_params = api_docs_v1_2.parser()
analytics_params.add_argument('dataset_id', type=str, help='Dataset identifier for historical analysis')
analytics_params.add_argument('time_range', type=str, help='Time range for analytics (1d, 7d, 30d, 90d)')

# Legacy parameter models
validation_params = api_docs_legacy.parser()
validation_params.add_argument('detect_phi', type=bool, default=True, 
                              help='Enable PHI/PII detection')
validation_params.add_argument('quality_checks', type=bool, default=True, 
                              help='Enable data quality checks')
validation_params.add_argument('profile', type=str, 
                              help='Validation profile (clinical_trials, ehr, imaging, lab)')
validation_params.add_argument('standards', type=str, action='append', 
                              help='Medical standards to check (icd10, loinc, cpt, hipaa)')

file_upload_params = api_docs_legacy.parser()
file_upload_params.add_argument('file', type='FileStorage', location='files', required=True,
                               help='Medical data file (CSV, Excel, JSON, Parquet)')
file_upload_params.add_argument('detect_phi', type=bool, default=True,
                               help='Enable PHI/PII detection')
file_upload_params.add_argument('quality_checks', type=bool, default=True,
                               help='Enable data quality checks')
file_upload_params.add_argument('profile', type=str,
                               help='Validation profile')
file_upload_params.add_argument('standards', type=str, action='append',
                               help='Medical standards to check')

@docs_bp.route('/')
def documentation_index():
    """Main documentation page."""
    return render_template('docs/index.html')

@docs_bp.route('/api')
def api_documentation():
    """API documentation page."""
    return render_template('docs/api.html')

@docs_bp.route('/markdown/<filename>')
def serve_markdown(filename: str):
    """Serve markdown documentation files."""
    allowed_files = ['API_DOCUMENTATION.md', 'API_CURL_EXAMPLES.md']
    
    if filename not in allowed_files:
        return jsonify({'error': 'File not found'}), 404
    
    try:
        # Get the project root directory
        project_root = Path(__file__).parent.parent.parent
        file_path = project_root / filename
        
        if not file_path.exists():
            return jsonify({'error': 'File not found'}), 404
        
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Convert markdown to HTML
        html_content = markdown.markdown(
            content,
            extensions=['tables', 'fenced_code', 'codehilite', 'toc']
        )
        
        return render_template('docs/markdown.html', content=html_content, title=filename)
        
    except Exception as e:
        return jsonify({'error': f'Error reading file: {str(e)}'}), 500

@docs_bp.route('/swagger.json')
def swagger_json():
    """Serve Swagger JSON specification."""
    try:
        from medical_data_validator.dashboard.routes import create_api_blueprint
        from flask import Flask
        
        # Create a temporary app to generate the spec
        temp_app = Flask(__name__)
        api_bp = create_api_blueprint()
        temp_app.register_blueprint(api_bp)
        
        # Create API documentation
        api = Api(
            temp_app,
            version='1.2.0',
            title='Medical Data Validator API v1.2',
            description='Enterprise-grade validation for healthcare datasets v1.2 with advanced compliance and analytics',
            doc='/docs/swagger',
            authorizations={
                'apikey': {
                    'type': 'apiKey',
                    'in': 'header',
                    'name': 'X-API-Key'
                }
            },
            security='apikey'
        )
        
        # Add namespaces
        api.add_namespace(api_docs_v1_2)
        api.add_namespace(api_docs_legacy)
        
        # Generate spec
        spec = api.__schema__
        return jsonify(spec)
        
    except Exception as e:
        return jsonify({'error': f'Error generating Swagger spec: {str(e)}'}), 500

def create_swagger_api(app):
    """Create and configure Swagger API documentation for v1.2."""
    api = Api(
        app,
        version='1.2.0',
        title='Medical Data Validator API v1.2',
        description='''
        Enterprise-grade validation for healthcare datasets v1.2, ensuring compliance with HIPAA, GDPR, FDA 21 CFR Part 11, 
        medical coding standards, and data quality requirements.
        
        ## v1.2 Features
        - **Advanced Compliance Validation**: Multi-standard compliance (HIPAA, GDPR, FDA 21 CFR Part 11)
        - **Risk Assessment**: Automated risk scoring and recommendations
        - **Enhanced Analytics**: Data quality metrics and anomaly detection
        - **Real-time Monitoring**: System health and compliance tracking
        - **Compliance Templates**: Pre-configured templates for common use cases
        - **API Versioning**: Backward compatible with v1.0 endpoints
        
        ## Authentication
        Currently, the API operates without authentication for development. 
        For production deployment, implement appropriate authentication mechanisms.
        
        ## Rate Limiting
        - Standard endpoints: 100 requests per minute
        - File upload endpoints: 10 requests per minute
        - Analytics endpoints: 50 requests per minute
        
        ## API Versions
        - **v1.2 endpoints**: `/api/v1.2/*` (recommended)
        - **Legacy v1.0 endpoints**: `/api/*` (backward compatible)
        ''',
        doc='/docs/swagger',
        authorizations={
            'apikey': {
                'type': 'apiKey',
                'in': 'header',
                'name': 'X-API-Key'
            }
        },
        security='apikey',
        contact='Rana Ehtasham Ali',
        contact_email='ranaehtashamali1@gmail.com',
        contact_url='https://github.com/RanaEhtashamAli/medical-data-validator',
        license='MIT',
        license_url='https://opensource.org/licenses/MIT'
    )
    
    # Add the API documentation namespaces
    api.add_namespace(api_docs_v1_2)
    api.add_namespace(api_docs_legacy)
    
    return api

# Swagger API Resources for v1.2
@api_docs_v1_2.route('/health')
class HealthCheckV1_2(Resource):
    @api_docs_v1_2.doc('health_check_v1_2')
    @api_docs_v1_2.marshal_with(health_response_model_v1_2)
    def get(self):
        """Health check endpoint for monitoring with v1.2 features."""
        from medical_data_validator.dashboard.routes import api_health
        resp = api_health()
        if isinstance(resp, tuple):
            resp = resp[0]
        return resp.get_json()

@api_docs_v1_2.route('/validate/data')
class ValidateDataV1_2(Resource):
    @api_docs_v1_2.doc('validate_data_v1_2')
    @api_docs_v1_2.expect(validation_request_model_v1_2, validation_params_v1_2)
    @api_docs_v1_2.marshal_with(validation_response_model_v1_2)
    def post(self):
        """Validate structured JSON data for medical compliance with v1.2 features."""
        from medical_data_validator.dashboard.routes import api_validate_data
        resp = api_validate_data()
        if isinstance(resp, tuple):
            resp = resp[0]
        return resp.get_json()

@api_docs_v1_2.route('/validate/file')
class ValidateFileV1_2(Resource):
    @api_docs_v1_2.doc('validate_file_v1_2')
    @api_docs_v1_2.expect(file_upload_params_v1_2)
    @api_docs_v1_2.marshal_with(validation_response_model_v1_2)
    def post(self):
        """Upload and validate medical data files with v1.2 compliance features."""
        from medical_data_validator.dashboard.routes import api_validate_file
        resp = api_validate_file()
        if isinstance(resp, tuple):
            resp = resp[0]
        return resp.get_json()

@api_docs_v1_2.route('/compliance/check')
class ComplianceCheckV1_2(Resource):
    @api_docs_v1_2.doc('compliance_check_v1_2')
    @api_docs_v1_2.expect(compliance_request_model_v1_2)
    @api_docs_v1_2.marshal_with(compliance_response_model_v1_2)
    def post(self):
        """Advanced compliance assessment for medical standards with risk assessment."""
        from medical_data_validator.dashboard.routes import api_compliance_check
        resp = api_compliance_check()
        if isinstance(resp, tuple):
            resp = resp[0]
        return resp.get_json()

@api_docs_v1_2.route('/compliance/templates')
class ComplianceTemplatesV1_2(Resource):
    @api_docs_v1_2.doc('get_compliance_templates_v1_2')
    @api_docs_v1_2.marshal_with(compliance_templates_response_model)
    def get(self):
        """Get available compliance templates for v1.2."""
        from medical_data_validator.dashboard.routes import api_templates
        resp = api_templates()
        if isinstance(resp, tuple):
            resp = resp[0]
        return resp.get_json()

@api_docs_v1_2.route('/analytics/quality')
class AnalyticsQualityV1_2(Resource):
    @api_docs_v1_2.doc('get_analytics_quality_v1_2')
    @api_docs_v1_2.expect(analytics_params)
    @api_docs_v1_2.marshal_with(analytics_response_model)
    def get(self):
        """Get detailed data quality analytics and metrics."""
        from medical_data_validator.dashboard.routes import api_analytics
        resp = api_analytics()
        if isinstance(resp, tuple):
            resp = resp[0]
        return resp.get_json()

@api_docs_v1_2.route('/monitoring/status')
class MonitoringStatusV1_2(Resource):
    @api_docs_v1_2.doc('get_monitoring_status_v1_2')
    @api_docs_v1_2.marshal_with(monitoring_response_model)
    def get(self):
        """Get real-time system monitoring and performance metrics."""
        from medical_data_validator.dashboard.routes import api_monitoring_stats
        resp = api_monitoring_stats()
        if isinstance(resp, tuple):
            resp = resp[0]
        return resp.get_json()

@api_docs_v1_2.route('/profiles')
class ProfilesV1_2(Resource):
    @api_docs_v1_2.doc('get_profiles_v1_2')
    @api_docs_v1_2.marshal_with(compliance_templates_response_model)
    def get(self):
        """Get available validation profiles with v1.2 compliance templates."""
        from medical_data_validator.dashboard.routes import api_profiles
        resp = api_profiles()
        if isinstance(resp, tuple):
            resp = resp[0]
        return resp.get_json()

@api_docs_v1_2.route('/standards')
class StandardsV1_2(Resource):
    @api_docs_v1_2.doc('get_standards_v1_2')
    @api_docs_v1_2.marshal_with(standards_response_model)
    def get(self):
        """Get supported medical standards information including v1.2 standards."""
        from medical_data_validator.dashboard.routes import api_standards
        resp = api_standards()
        if isinstance(resp, tuple):
            resp = resp[0]
        return resp.get_json() 

@api_docs_legacy.route('/health')
class HealthCheckLegacy(Resource):
    @api_docs_legacy.doc('health_check_legacy')
    @api_docs_legacy.marshal_with(health_response_model)
    def get(self):
        """Health check endpoint for monitoring."""
        from medical_data_validator.dashboard.routes import api_health
        resp = api_health()
        if isinstance(resp, tuple):
            resp = resp[0]
        return resp.get_json()

@api_docs_legacy.route('/validate/data')
class ValidateDataLegacy(Resource):
    @api_docs_legacy.doc('validate_data_legacy')
    @api_docs_legacy.expect(validation_request_model, validation_params)
    @api_docs_legacy.marshal_with(validation_response_model)
    def post(self):
        """Validate structured JSON data for medical compliance."""
        from medical_data_validator.dashboard.routes import api_validate_data
        resp = api_validate_data()
        if isinstance(resp, tuple):
            resp = resp[0]
        return resp.get_json()

@api_docs_legacy.route('/validate/file')
class ValidateFileLegacy(Resource):
    @api_docs_legacy.doc('validate_file_legacy')
    @api_docs_legacy.expect(file_upload_params)
    @api_docs_legacy.marshal_with(validation_response_model)
    def post(self):
        """Upload and validate medical data files."""
        from medical_data_validator.dashboard.routes import api_validate_file
        resp = api_validate_file()
        if isinstance(resp, tuple):
            resp = resp[0]
        return resp.get_json()

@api_docs_legacy.route('/compliance/check')
class ComplianceCheckLegacy(Resource):
    @api_docs_legacy.doc('compliance_check_legacy')
    @api_docs_legacy.expect(compliance_request_model)
    @api_docs_legacy.marshal_with(compliance_response_model)
    def post(self):
        """Quick compliance assessment for medical standards."""
        from medical_data_validator.dashboard.routes import api_compliance_check
        resp = api_compliance_check()
        if isinstance(resp, tuple):
            resp = resp[0]
        return resp.get_json()

@api_docs_legacy.route('/profiles')
class ProfilesLegacy(Resource):
    @api_docs_legacy.doc('get_profiles_legacy')
    @api_docs_legacy.marshal_with(profiles_response_model)
    def get(self):
        """Get available validation profiles."""
        from medical_data_validator.dashboard.routes import api_profiles
        resp = api_profiles()
        if isinstance(resp, tuple):
            resp = resp[0]
        return resp.get_json()

@api_docs_legacy.route('/standards')
class StandardsLegacy(Resource):
    @api_docs_legacy.doc('get_standards_legacy')
    @api_docs_legacy.marshal_with(standards_response_model)
    def get(self):
        """Get supported medical standards information."""
        from medical_data_validator.dashboard.routes import api_standards
        resp = api_standards()
        if isinstance(resp, tuple):
            resp = resp[0]
        return resp.get_json() 