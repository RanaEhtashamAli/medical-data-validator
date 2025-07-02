"""
Documentation routes for the Medical Data Validator API.
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

# Create API documentation namespace
api_docs = Namespace('api', description='Medical Data Validator API Documentation')

# Define API models for Swagger documentation
validation_request_model = api_docs.model('ValidationRequest', {
    'patient_id': fields.List(fields.String, description='Patient identifiers', example=['P001', 'P002']),
    'age': fields.List(fields.Integer, description='Patient ages', example=[30, 45]),
    'diagnosis': fields.List(fields.String, description='Diagnosis codes (ICD-10)', example=['E11.9', 'I10']),
    'procedure': fields.List(fields.String, description='Procedure codes (CPT)', example=['99213', '93010']),
    'lab_code': fields.List(fields.String, description='Laboratory codes (LOINC)', example=['58410-2', '789-8'])
})

validation_response_model = api_docs.model('ValidationResponse', {
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

compliance_request_model = api_docs.model('ComplianceRequest', {
    'patient_id': fields.List(fields.String, description='Patient identifiers'),
    'diagnosis': fields.List(fields.String, description='Diagnosis codes'),
    'procedure': fields.List(fields.String, description='Procedure codes')
})

compliance_response_model = api_docs.model('ComplianceResponse', {
    'hipaa_compliant': fields.Boolean(description='HIPAA compliance status'),
    'icd10_compliant': fields.Boolean(description='ICD-10 compliance status'),
    'loinc_compliant': fields.Boolean(description='LOINC compliance status'),
    'cpt_compliant': fields.Boolean(description='CPT compliance status'),
    'fhir_compliant': fields.Boolean(description='FHIR compliance status'),
    'omop_compliant': fields.Boolean(description='OMOP compliance status'),
    'details': fields.Raw(description='Detailed compliance information')
})

health_response_model = api_docs.model('HealthResponse', {
    'status': fields.String(description='API health status'),
    'version': fields.String(description='API version'),
    'timestamp': fields.String(description='Current timestamp'),
    'standards_supported': fields.List(fields.String, description='Supported medical standards')
})

profiles_response_model = api_docs.model('ProfilesResponse', {
    'clinical_trials': fields.String(description='Clinical trial data validation'),
    'ehr': fields.String(description='Electronic health records validation'),
    'imaging': fields.String(description='Medical imaging metadata validation'),
    'lab': fields.String(description='Laboratory data validation')
})

standards_response_model = api_docs.model('StandardsResponse', {
    'icd10': fields.Raw(description='ICD-10 standard information'),
    'loinc': fields.Raw(description='LOINC standard information'),
    'cpt': fields.Raw(description='CPT standard information'),
    'icd9': fields.Raw(description='ICD-9 standard information'),
    'ndc': fields.Raw(description='NDC standard information'),
    'fhir': fields.Raw(description='FHIR standard information'),
    'omop': fields.Raw(description='OMOP standard information')
})

# Define parameter models
validation_params = api_docs.parser()
validation_params.add_argument('detect_phi', type=bool, default=True, 
                              help='Enable PHI/PII detection')
validation_params.add_argument('quality_checks', type=bool, default=True, 
                              help='Enable data quality checks')
validation_params.add_argument('profile', type=str, 
                              help='Validation profile (clinical_trials, ehr, imaging, lab)')
validation_params.add_argument('standards', type=str, action='append', 
                              help='Medical standards to check (icd10, loinc, cpt, hipaa)')

file_upload_params = api_docs.parser()
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
            version='1.0',
            title='Medical Data Validator API',
            description='Enterprise-grade validation for healthcare datasets',
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
        api.add_namespace(api_docs)
        
        # Generate spec
        spec = api.__schema__
        return jsonify(spec)
        
    except Exception as e:
        return jsonify({'error': f'Error generating Swagger spec: {str(e)}'}), 500

def create_swagger_api(app):
    """Create and configure Swagger API documentation."""
    api = Api(
        app,
        version='1.0',
        title='Medical Data Validator API',
        description='''
        Enterprise-grade validation for healthcare datasets, ensuring compliance with HIPAA, 
        medical coding standards, and data quality requirements.
        
        ## Features
        - **HIPAA Compliance**: PHI/PII detection and privacy protection
        - **Medical Standards**: ICD-10, LOINC, CPT, FHIR, OMOP validation
        - **Data Quality**: Completeness, accuracy, and consistency checks
        - **File Support**: CSV, Excel, JSON, Parquet formats
        - **Real-time Validation**: Instant feedback on data quality
        
        ## Authentication
        Currently, the API operates without authentication for development. 
        For production deployment, implement appropriate authentication mechanisms.
        
        ## Rate Limiting
        - Default: 100 requests per minute per IP
        - File uploads: 10 requests per minute per IP
        - Burst: Up to 20 requests in 10 seconds
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
    
    # Add the API documentation namespace
    api.add_namespace(api_docs)
    
    return api

# Swagger API Resources
@api_docs.route('/health')
class HealthCheck(Resource):
    @api_docs.doc('health_check')
    @api_docs.marshal_with(health_response_model)
    def get(self):
        """Health check endpoint for monitoring."""
        from medical_data_validator.dashboard.routes import api_health
        resp = api_health()
        if isinstance(resp, tuple):
            resp = resp[0]
        return resp.get_json()

@api_docs.route('/validate/data')
class ValidateData(Resource):
    @api_docs.doc('validate_data')
    @api_docs.expect(validation_request_model, validation_params)
    @api_docs.marshal_with(validation_response_model)
    def post(self):
        """Validate structured JSON data for medical compliance."""
        from medical_data_validator.dashboard.routes import api_validate_data
        resp = api_validate_data()
        if isinstance(resp, tuple):
            resp = resp[0]
        return resp.get_json()

@api_docs.route('/validate/file')
class ValidateFile(Resource):
    @api_docs.doc('validate_file')
    @api_docs.expect(file_upload_params)
    @api_docs.marshal_with(validation_response_model)
    def post(self):
        """Upload and validate medical data files."""
        from medical_data_validator.dashboard.routes import api_validate_file
        resp = api_validate_file()
        if isinstance(resp, tuple):
            resp = resp[0]
        return resp.get_json()

@api_docs.route('/compliance/check')
class ComplianceCheck(Resource):
    @api_docs.doc('compliance_check')
    @api_docs.expect(compliance_request_model)
    @api_docs.marshal_with(compliance_response_model)
    def post(self):
        """Quick compliance assessment for medical standards."""
        from medical_data_validator.dashboard.routes import api_compliance_check
        resp = api_compliance_check()
        if isinstance(resp, tuple):
            resp = resp[0]
        return resp.get_json()

@api_docs.route('/profiles')
class Profiles(Resource):
    @api_docs.doc('get_profiles')
    @api_docs.marshal_with(profiles_response_model)
    def get(self):
        """Get available validation profiles."""
        from medical_data_validator.dashboard.routes import api_profiles
        resp = api_profiles()
        if isinstance(resp, tuple):
            resp = resp[0]
        return resp.get_json()

@api_docs.route('/standards')
class Standards(Resource):
    @api_docs.doc('get_standards')
    @api_docs.marshal_with(standards_response_model)
    def get(self):
        """Get supported medical standards information."""
        from medical_data_validator.dashboard.routes import api_standards
        resp = api_standards()
        if isinstance(resp, tuple):
            resp = resp[0]
        return resp.get_json() 