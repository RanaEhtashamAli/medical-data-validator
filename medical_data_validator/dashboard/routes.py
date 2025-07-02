"""
Flask routes for the Medical Data Validator Dashboard and REST API.

This module provides both UI routes (HTML pages) and API routes (JSON endpoints)
for the unified Flask application.
"""

import os
import tempfile
import traceback
from pathlib import Path
from flask import render_template, request, jsonify, Blueprint, current_app
import pandas as pd
import numpy as np
import json
from typing import Dict, List, Optional, Any

import sys
import os

# Add the project root to Python path for direct execution
if __name__ == "__main__":
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    sys.path.insert(0, project_root)

try:
    from medical_data_validator.core import MedicalDataValidator, ValidationResult
    from medical_data_validator.validators import PHIDetector, DataQualityChecker, MedicalCodeValidator
    from medical_data_validator.extensions import get_profile
    from medical_data_validator.dashboard.utils import load_data, generate_charts
except ImportError:
    # Fallback for relative imports when used as package
    from ..core import MedicalDataValidator, ValidationResult
    from ..validators import PHIDetector, DataQualityChecker, MedicalCodeValidator
    from ..extensions import get_profile
    from .utils import load_data, generate_charts

def convert_numpy_types(obj):
    """Convert numpy types to native Python types for JSON serialization."""
    try:
        print(f"convert_numpy_types called with: {type(obj)} - {obj}")
        
        if isinstance(obj, np.ndarray):
            result = obj.tolist()
            print(f"Converted numpy array to list: {result}")
            return result
        elif isinstance(obj, np.integer):
            result = int(obj)
            print(f"Converted numpy integer: {result}")
            return result
        elif isinstance(obj, np.floating):
            result = float(obj)
            print(f"Converted numpy float: {result}")
            return result
        elif isinstance(obj, np.bool_):
            result = bool(obj)
            print(f"Converted numpy bool: {result}")
            return result
        elif isinstance(obj, dict):
            print(f"Converting dict with {len(obj)} items")
            result = {key: convert_numpy_types(value) for key, value in obj.items()}
            print(f"Converted dict: {result}")
            return result
        elif isinstance(obj, list):
            print(f"Converting list with {len(obj)} items")
            result = [convert_numpy_types(item) for item in obj]
            print(f"Converted list: {result}")
            return result
        elif obj is None:
            print("Converting None")
            return None
        elif isinstance(obj, (bool, int, float, str)):
            print(f"Returning native type: {obj}")
            return obj
        else:
            result = str(obj)
            print(f"Converting to string: {result}")
            return result
    except Exception as e:
        print(f"ERROR in convert_numpy_types: {e}")
        print(f"ERROR traceback: {traceback.format_exc()}")
        # Fallback: convert to string if conversion fails
        return str(obj)

def generate_compliance_report(data: pd.DataFrame, result: ValidationResult, standards: List[str]) -> Dict[str, Any]:
    """Generate compliance report for medical standards."""
    compliance_report = {}
    
    for standard in standards:
        if standard == "hipaa":
            # Check for PHI/PII in the data itself
            phi_detected = False
            phi_issues = []
            
            # Check for SSN patterns
            for col in data.columns:
                if any(data[col].astype(str).str.contains(r'\d{3}-\d{2}-\d{4}', na=False)):
                    phi_detected = True
                    phi_issues.append(f"SSN detected in column: {col}")
            
            # Check for email patterns
            for col in data.columns:
                if any(data[col].astype(str).str.contains(r'@.*\.', na=False)):
                    phi_detected = True
                    phi_issues.append(f"Email detected in column: {col}")
            
            # Also check validation issues for PHI mentions
            for issue in result.issues:
                if hasattr(issue, 'message') and ("phi" in issue.message.lower() or "pii" in issue.message.lower()):
                    phi_detected = True
                    phi_issues.append(issue.message)
            
            compliance_report["hipaa"] = {
                "compliant": not phi_detected,
                "issues": phi_issues,
                "score": 100 if not phi_detected else 50
            }
        elif standard == "icd10":
            # Check ICD-10 code compliance
            icd10_issues = [
                issue for issue in result.issues 
                if hasattr(issue, 'message') and 
                ("icd10" in issue.message.lower() or "diagnosis" in issue.message.lower())
            ]
            compliance_report["icd10"] = {
                "compliant": len(icd10_issues) == 0,
                "issues": [issue.message for issue in icd10_issues if hasattr(issue, 'message')],
                "score": max(0, 100 - len(icd10_issues) * 10)
            }
        elif standard == "loinc":
            # Check LOINC code compliance
            loinc_issues = [
                issue for issue in result.issues 
                if hasattr(issue, 'message') and 
                ("loinc" in issue.message.lower() or "lab" in issue.message.lower())
            ]
            compliance_report["loinc"] = {
                "compliant": len(loinc_issues) == 0,
                "issues": [issue.message for issue in loinc_issues if hasattr(issue, 'message')],
                "score": max(0, 100 - len(loinc_issues) * 10)
            }
        elif standard == "cpt":
            # Check CPT code compliance
            cpt_issues = [
                issue for issue in result.issues 
                if hasattr(issue, 'message') and 
                ("cpt" in issue.message.lower() or "procedure" in issue.message.lower())
            ]
            compliance_report["cpt"] = {
                "compliant": len(cpt_issues) == 0,
                "issues": [issue.message for issue in cpt_issues if hasattr(issue, 'message')],
                "score": max(0, 100 - len(cpt_issues) * 10)
            }
        elif standard == "fhir":
            # Check FHIR compliance
            fhir_issues = [
                issue for issue in result.issues 
                if hasattr(issue, 'message') and "fhir" in issue.message.lower()
            ]
            compliance_report["fhir"] = {
                "compliant": len(fhir_issues) == 0,
                "issues": [issue.message for issue in fhir_issues if hasattr(issue, 'message')],
                "score": max(0, 100 - len(fhir_issues) * 10)
            }
        elif standard == "omop":
            # Check OMOP compliance
            omop_issues = [
                issue for issue in result.issues 
                if hasattr(issue, 'message') and "omop" in issue.message.lower()
            ]
            compliance_report["omop"] = {
                "compliant": len(omop_issues) == 0,
                "issues": [issue.message for issue in omop_issues if hasattr(issue, 'message')],
                "score": max(0, 100 - len(omop_issues) * 10)
            }
    
    return compliance_report

def convert_validation_issue_to_dict(issue) -> Dict[str, Any]:
    """Convert ValidationIssue to dictionary."""
    try:
        print(f"convert_validation_issue_to_dict called with: {type(issue)}")
        print(f"Issue attributes: {dir(issue)}")
        
        result = {
            "severity": getattr(issue, 'severity', 'unknown'),
            "description": getattr(issue, 'message', str(issue)),
            "column": getattr(issue, 'column', None),
            "row": getattr(issue, 'row', None),
            "value": getattr(issue, 'value', None),
            "rule_name": getattr(issue, 'rule_name', None)
        }
        
        print(f"Converted issue to dict: {result}")
        return result
    except Exception as e:
        print(f"ERROR in convert_validation_issue_to_dict: {e}")
        print(f"ERROR traceback: {traceback.format_exc()}")
        return {
            "severity": "error",
            "description": f"Failed to convert issue: {str(e)}",
            "column": None,
            "row": None,
            "value": None,
            "rule_name": None
        }

def create_api_blueprint():
    """Create and configure the API Blueprint."""
    api_bp = Blueprint('api', __name__, url_prefix='/api')
    
    @api_bp.route('/', methods=['GET'])
    def api_root():
        """Root API endpoint with information."""
        return jsonify({
            "message": "Medical Data Validator API",
            "version": "0.1.0",
            "developer": "Rana Ehtasham Ali",
            "documentation": "/docs",
            "health": "/api/health"
        })

    @api_bp.route('/health', methods=['GET'])
    def api_health():
        """Health check endpoint for monitoring."""
        return jsonify({
            'status': 'healthy',
            'version': '0.1.0',
            'timestamp': pd.Timestamp.now().isoformat(),
            'standards_supported': ["icd10", "loinc", "cpt", "icd9", "ndc", "fhir", "omop"]
        })

    @api_bp.route('/validate/data', methods=['POST'])
    def api_validate_data():
        """Validate JSON data via API."""
        try:
            print("=== API VALIDATE DATA START ===")
            
            data = request.get_json()
            print(f"Received data: {type(data)} - {data}")
            
            if data is None:
                print("Data is None - returning 400")
                return jsonify({"success": False, "error": "Invalid JSON data"}), 400
            
            # Handle empty data gracefully
            if not data:
                print("Data is empty - returning success response")
                return jsonify({
                    "success": True,
                    "is_valid": True,
                    "total_issues": 0,
                    "error_count": 0,
                    "warning_count": 0,
                    "info_count": 0,
                    "compliance_report": {},
                    "issues": [],
                    "summary": {
                        "total_rows": 0,
                        "total_columns": 0,
                        "is_valid": True,
                        "total_issues": 0
                    }
                })
            
            # Get parameters
            detect_phi = request.args.get('detect_phi', 'true').lower() == 'true'
            quality_checks = request.args.get('quality_checks', 'true').lower() == 'true'
            profile = request.args.get('profile', '')
            standards = request.args.getlist('standards') or ["icd10", "loinc", "cpt"]
            
            print(f"Parameters: detect_phi={detect_phi}, quality_checks={quality_checks}, profile='{profile}'")
            
            # Convert data to DataFrame
            print("Converting data to DataFrame...")
            try:
                # Handle arrays of different lengths by padding with None
                if isinstance(data, dict):
                    # Find the maximum length
                    max_length = max(len(value) if isinstance(value, list) else 1 for value in data.values())
                    print(f"Maximum array length: {max_length}")
                    
                    # Pad shorter arrays with None
                    padded_data = {}
                    for key, value in data.items():
                        if isinstance(value, list):
                            if len(value) < max_length:
                                padded_data[key] = value + [None] * (max_length - len(value))
                                print(f"Padded {key} from {len(value)} to {max_length} items")
                            else:
                                padded_data[key] = value
                        else:
                            # Convert single values to lists
                            padded_data[key] = [value] * max_length
                            print(f"Converted {key} single value to list of {max_length} items")
                    
                    df = pd.DataFrame(padded_data)
                else:
                    df = pd.DataFrame(data)
                
                print(f"DataFrame created: {df.shape} - columns: {list(df.columns)}")
                print(f"DataFrame dtypes: {df.dtypes.to_dict()}")
                print(f"DataFrame head: {df.head().to_dict()}")
            except Exception as e:
                print(f"ERROR creating DataFrame: {e}")
                print(f"ERROR traceback: {traceback.format_exc()}")
                return jsonify({
                    "success": False, 
                    "error": f"Failed to create DataFrame: {str(e)}",
                    "traceback": traceback.format_exc()
                }), 500
            
            # Create validator
            print("Creating validator...")
            try:
                validator = create_validator(detect_phi, quality_checks, profile)
                print(f"Validator created with {len(validator.rules)} rules")
            except Exception as e:
                print(f"ERROR creating validator: {e}")
                print(f"ERROR traceback: {traceback.format_exc()}")
                return jsonify({
                    "success": False, 
                    "error": f"Failed to create validator: {str(e)}",
                    "traceback": traceback.format_exc()
                }), 500
            
            # Validate data
            print("Validating data...")
            try:
                result = validator.validate(df)
                print(f"Validation completed: {len(result.issues)} issues found")
            except Exception as e:
                print(f"ERROR during validation: {e}")
                print(f"ERROR traceback: {traceback.format_exc()}")
                return jsonify({
                    "success": False, 
                    "error": f"Validation failed: {str(e)}",
                    "traceback": traceback.format_exc()
                }), 500
            
            # Generate compliance report
            print("Generating compliance report...")
            try:
                compliance_report = generate_compliance_report(df, result, standards)
                print("Compliance report generated")
            except Exception as e:
                print(f"ERROR generating compliance report: {e}")
                print(f"ERROR traceback: {traceback.format_exc()}")
                return jsonify({
                    "success": False, 
                    "error": f"Failed to generate compliance report: {str(e)}",
                    "traceback": traceback.format_exc()
                }), 500
            
            # Convert result to dict
            print("Converting result to dict...")
            try:
                result_dict = convert_numpy_types(result.to_dict())
                print("Result converted to dict")
            except Exception as e:
                print(f"ERROR converting result to dict: {e}")
                print(f"ERROR traceback: {traceback.format_exc()}")
                return jsonify({
                    "success": False, 
                    "error": f"Failed to convert result: {str(e)}",
                    "traceback": traceback.format_exc()
                }), 500
            
            # Convert issues to dict
            print("Converting issues to dict...")
            try:
                issues_dict = [convert_validation_issue_to_dict(issue) for issue in result.issues]
                print(f"Converted {len(issues_dict)} issues")
            except Exception as e:
                print(f"ERROR converting issues to dict: {e}")
                print(f"ERROR traceback: {traceback.format_exc()}")
                return jsonify({
                    "success": False, 
                    "error": f"Failed to convert issues: {str(e)}",
                    "traceback": traceback.format_exc()
                }), 500
            
            print("Creating final response...")
            response_data = {
                "success": True,
                "is_valid": result.is_valid,
                "total_issues": len(result.issues),
                "error_count": len([i for i in result.issues if i.severity == 'error']),
                "warning_count": len([i for i in result.issues if i.severity == 'warning']),
                "info_count": len([i for i in result.issues if i.severity == 'info']),
                "compliance_report": compliance_report,
                "issues": issues_dict,
                "summary": {
                    "total_rows": len(df),
                    "total_columns": len(df.columns),
                    "is_valid": result.is_valid,
                    "total_issues": len(result.issues)
                }
            }
            
            print("=== API VALIDATE DATA SUCCESS ===")
            return jsonify(response_data)
            
        except Exception as e:
            print(f"=== API VALIDATE DATA ERROR ===")
            print(f"Unexpected error: {e}")
            print(f"Error type: {type(e)}")
            print(f"Full traceback: {traceback.format_exc()}")
            return jsonify({
                "success": False,
                "error": f"Unexpected error: {str(e)}",
                "error_type": str(type(e)),
                "traceback": traceback.format_exc()
            }), 500

    @api_bp.route('/validate/file', methods=['POST'])
    def api_validate_file():
        """Validate uploaded file via API."""
        try:
            if 'file' not in request.files:
                return jsonify({"success": False, "error": "No file provided"}), 400
            
            file = request.files['file']
            if file.filename == '':
                return jsonify({"success": False, "error": "No file selected"}), 400
            
            # Security: File validation
            allowed_extensions = {'csv', 'xlsx', 'xls', 'json', 'parquet'}
            file_extension = file.filename.split('.')[-1].lower()
            
            if file_extension not in allowed_extensions:
                return jsonify({
                    "success": False,
                    "error": f"File type not allowed. Supported: {', '.join(allowed_extensions)}"
                }), 400
            
            # Security: File size validation (16MB limit)
            file.seek(0, 2)  # Seek to end
            file_size = file.tell()
            file.seek(0)  # Reset to beginning
            
            if file_size > 16 * 1024 * 1024:  # 16MB
                return jsonify({
                    "success": False,
                    "error": "File too large. Maximum size is 16MB"
                }), 400
            
            # Get parameters
            detect_phi = request.form.get('detect_phi', 'true').lower() == 'true'
            quality_checks = request.form.get('quality_checks', 'true').lower() == 'true'
            profile = request.form.get('profile', '')
            standards = request.form.getlist('standards') or ["icd10", "loinc", "cpt"]
            
            # Process file
            with tempfile.NamedTemporaryFile(delete=False, suffix=f".{file_extension}") as tmp_file:
                file.save(tmp_file.name)
                tmp_path = tmp_file.name
            
            try:
                # Load data
                data = load_data(tmp_path)
                
                # Create validator
                validator = create_validator(detect_phi, quality_checks, profile)
                
                # Validate data
                result = validator.validate(data)
                
                # Generate compliance report
                compliance_report = generate_compliance_report(data, result, standards)
                
                # Convert result to dict
                result_dict = convert_numpy_types(result.to_dict())
                
                return jsonify({
                    "success": True,
                    "is_valid": result.is_valid,
                    "total_issues": len(result.issues),
                    "error_count": len([i for i in result.issues if i.severity == 'error']),
                    "warning_count": len([i for i in result.issues if i.severity == 'warning']),
                    "info_count": len([i for i in result.issues if i.severity == 'info']),
                    "compliance_report": compliance_report,
                    "issues": [convert_validation_issue_to_dict(issue) for issue in result.issues],
                    "summary": {
                        "total_rows": len(data),
                        "total_columns": len(data.columns),
                        "is_valid": result.is_valid,
                        "total_issues": len(result.issues)
                    }
                })
                
            finally:
                # Clean up
                os.unlink(tmp_path)
                
        except Exception as e:
            return jsonify({
                "success": False,
                "error": str(e),
                "traceback": traceback.format_exc() if current_app.debug else None
            }), 500

    @api_bp.route('/compliance/check', methods=['POST'])
    def api_compliance_check():
        """Check compliance with medical standards."""
        try:
            data = request.get_json()
            if not data:
                return jsonify({"success": False, "error": "No data provided"}), 400
            
            standards = request.args.getlist('standards') or ["hipaa", "icd10", "loinc", "cpt"]
            
            # Convert data to DataFrame
            df = pd.DataFrame(data)
            
            # Create validator for compliance check
            validator = create_validator(detect_phi=True, quality_checks=True, profile='')
            result = validator.validate(df)
            
            # Generate compliance report
            compliance_report = generate_compliance_report(df, result, standards)
            
            return jsonify({
                "hipaa_compliant": compliance_report.get("hipaa", {}).get("compliant", False),
                "icd10_compliant": compliance_report.get("icd10", {}).get("compliant", False),
                "loinc_compliant": compliance_report.get("loinc", {}).get("compliant", False),
                "cpt_compliant": compliance_report.get("cpt", {}).get("compliant", False),
                "fhir_compliant": compliance_report.get("fhir", {}).get("compliant", False),
                "omop_compliant": compliance_report.get("omop", {}).get("compliant", False),
                "details": compliance_report
            })
            
        except Exception as e:
            return jsonify({
                "success": False,
                "error": str(e),
                "traceback": traceback.format_exc() if current_app.debug else None
            }), 500

    @api_bp.route('/profiles', methods=['GET'])
    def api_profiles():
        """Get available validation profiles."""
        profiles = {
            'clinical_trials': 'Clinical trial data validation',
            'ehr': 'Electronic health records validation',
            'imaging': 'Medical imaging metadata validation',
            'lab': 'Laboratory data validation'
        }
        return jsonify(profiles)

    @api_bp.route('/standards', methods=['GET'])
    def api_standards():
        """Get supported medical standards information."""
        standards = {
            "icd10": {
                "name": "International Classification of Diseases, 10th Revision",
                "version": "2024",
                "authority": "WHO",
                "description": "Standard classification system for diseases and health conditions"
            },
            "loinc": {
                "name": "Logical Observation Identifiers Names and Codes",
                "version": "2.76",
                "authority": "Regenstrief Institute",
                "description": "Standard for identifying medical laboratory observations"
            },
            "cpt": {
                "name": "Current Procedural Terminology",
                "version": "2024",
                "authority": "AMA",
                "description": "Standard for medical procedures and services"
            },
            "icd9": {
                "name": "International Classification of Diseases, 9th Revision",
                "version": "2012",
                "authority": "WHO",
                "description": "Legacy classification system for diseases"
            },
            "ndc": {
                "name": "National Drug Code",
                "version": "2024",
                "authority": "FDA",
                "description": "Standard for identifying drugs and biologics"
            },
            "fhir": {
                "name": "Fast Healthcare Interoperability Resources",
                "version": "R5",
                "authority": "HL7",
                "description": "Standard for healthcare data exchange"
            },
            "omop": {
                "name": "Observational Medical Outcomes Partnership",
                "version": "6.0",
                "authority": "OHDSI",
                "description": "Standard for observational healthcare data"
            }
        }
        return jsonify(standards)

    return api_bp

def create_validator(detect_phi: bool, quality_checks: bool, profile: str) -> MedicalDataValidator:
    """Create a validator with the specified configuration."""
    # Handle profile-based validation
    if profile and profile.strip():  # Check if profile is not empty
        profile_validator = get_profile(profile)
        if profile_validator:
            return profile_validator.create_validator()
    
    # Create basic validator
    validator = MedicalDataValidator()
    if detect_phi:
        validator.add_rule(PHIDetector())
    if quality_checks:
        validator.add_rule(DataQualityChecker())
    return validator

def register_routes(app):
    """Register all routes (UI and API) with the Flask app."""
    # Create and register API Blueprint
    api_bp = create_api_blueprint()
    app.register_blueprint(api_bp)
    
    # UI Routes
    @app.route('/home')
    def index():
        return render_template('index.html')

    @app.route('/about')
    def about():
        return render_template('about.html')

    # Legacy health endpoint (for backward compatibility)
    @app.route('/health')
    def health_check():
        """Health check endpoint for monitoring."""
        return jsonify({
            'status': 'healthy',
            'timestamp': pd.Timestamp.now().isoformat(),
            'version': '0.1.0'
        })

    # Legacy upload endpoint (for backward compatibility)
    @app.route('/upload', methods=['POST'])
    def upload_file():
        try:
            if 'file' not in request.files:
                return jsonify({'error': 'No file provided'}), 400
            file = request.files['file']
            if file.filename == '':
                return jsonify({'error': 'No file selected'}), 400
            # Security: File type validation
            allowed_extensions = {'csv', 'xlsx', 'xls', 'json', 'parquet'}
            if '.' not in file.filename or file.filename.rsplit('.', 1)[1].lower() not in allowed_extensions:
                return jsonify({'error': 'File type not allowed. Supported formats: CSV, Excel, JSON, Parquet'}), 400
            
            # Security: File size validation (16MB limit)
            file.seek(0, 2)  # Seek to end
            file_size = file.tell()
            file.seek(0)  # Reset to beginning
            if file_size > 16 * 1024 * 1024:  # 16MB
                return jsonify({'error': 'File too large. Maximum size is 16MB'}), 400
            
            # Security: Filename sanitization
            import re
            safe_filename = re.sub(r'[^a-zA-Z0-9._-]', '_', file.filename)
            if safe_filename != file.filename:
                return jsonify({'error': 'Invalid filename characters'}), 400
            detect_phi = request.form.get('detect_phi', 'false').lower() == 'true'
            quality_checks = request.form.get('quality_checks', 'false').lower() == 'true'
            profile = request.form.get('profile', '')
            with tempfile.NamedTemporaryFile(delete=False, suffix=f".{file.filename.rsplit('.', 1)[1]}") as tmp_file:
                file.save(tmp_file.name)
                tmp_path = tmp_file.name
            data = load_data(tmp_path)
            validator = create_validator(detect_phi, quality_checks, profile)
            result = validator.validate(data)
            charts = generate_charts(data, result)
            os.unlink(tmp_path)
            # Convert result to dict and handle numpy types
            result_dict = convert_numpy_types(result.to_dict())
            charts_dict = convert_numpy_types(charts)
            
            return jsonify({
                'success': True,
                'result': result_dict,
                'charts': charts_dict,
                'summary': {
                    'total_rows': len(data),
                    'total_columns': len(data.columns),
                    'is_valid': result.is_valid,
                    'total_issues': len(result.issues),
                    'error_count': len([i for i in result.issues if i.severity == 'error']),
                    'warning_count': len([i for i in result.issues if i.severity == 'warning']),
                    'info_count': len([i for i in result.issues if i.severity == 'info'])
                }
            })
        except Exception as e:
            return jsonify({
                'error': f'Validation failed: {str(e)}',
                'traceback': traceback.format_exc() if current_app.debug else None
            }), 500

    @app.route('/profiles')
    def get_profiles():
        profiles = {
            'clinical_trials': 'Clinical trial data validation',
            'ehr': 'Electronic health records validation',
            'imaging': 'Medical imaging metadata validation',
            'lab': 'Laboratory data validation'
        }
        return jsonify(profiles) 