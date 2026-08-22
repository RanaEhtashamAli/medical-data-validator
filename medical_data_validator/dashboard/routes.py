"""
Flask routes for the Medical Data Validator Dashboard and REST API.

This module provides both UI routes (HTML pages) and API routes (JSON endpoints)
for the unified Flask application.
"""

import logging
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

logger = logging.getLogger(__name__)

# Add the project root to Python path for direct execution
if __name__ == "__main__":
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    sys.path.insert(0, project_root)

try:
    from medical_data_validator.core import MedicalDataValidator, ValidationResult
    from medical_data_validator.validators import PHIDetector, DataQualityChecker, MedicalCodeValidator, SchemaValidator, RangeValidator, DateValidator
    from medical_data_validator.extensions import get_profile
    from medical_data_validator.dashboard.utils import load_data, generate_charts
    from medical_data_validator.performance import BatchValidator, ValidationCache
except ImportError:
    # Fallback for relative imports when used as package
    from ..core import MedicalDataValidator, ValidationResult
    from ..validators import PHIDetector, DataQualityChecker, MedicalCodeValidator, SchemaValidator, RangeValidator, DateValidator
    from ..extensions import get_profile
    from .utils import load_data, generate_charts
    from ..performance import BatchValidator, ValidationCache

# Module-level validation cache, shared across requests
_validation_cache = ValidationCache(max_size=int(os.environ.get('VALIDATION_CACHE_MAX_SIZE', 1000)))

def convert_numpy_types(obj):
    """Convert numpy types to native Python types for JSON serialization."""
    try:
        logger.debug("convert_numpy_types called with: %s - %s", type(obj), obj)

        if isinstance(obj, np.ndarray):
            result = obj.tolist()
            logger.debug("Converted numpy array to list: %s", result)
            return result
        elif isinstance(obj, np.integer):
            result = int(obj)
            logger.debug("Converted numpy integer: %s", result)
            return result
        elif isinstance(obj, np.floating):
            result = float(obj)
            logger.debug("Converted numpy float: %s", result)
            return result
        elif isinstance(obj, np.bool_):
            result = bool(obj)
            logger.debug("Converted numpy bool: %s", result)
            return result
        elif isinstance(obj, dict):
            logger.debug("Converting dict with %d items", len(obj))
            result = {key: convert_numpy_types(value) for key, value in obj.items()}
            logger.debug("Converted dict: %s", result)
            return result
        elif isinstance(obj, list):
            logger.debug("Converting list with %d items", len(obj))
            result = [convert_numpy_types(item) for item in obj]
            logger.debug("Converted list: %s", result)
            return result
        elif obj is None:
            logger.debug("Converting None")
            return None
        elif isinstance(obj, (bool, int, float, str)):
            logger.debug("Returning native type: %s", obj)
            return obj
        else:
            result = str(obj)
            logger.debug("Converting to string: %s", result)
            return result
    except Exception as e:
        logger.exception("Error in convert_numpy_types: %s", e)
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
    
    # Add v1.2 compliance report if available
    if 'compliance_report' in result.summary:
        v1_2_compliance = result.summary['compliance_report']
        # If v1.2 compliance has the new structure, flatten it for backward compatibility
        if 'standards' in v1_2_compliance:
            # Flatten the structure to match test expectations
            standards = v1_2_compliance['standards']
            if isinstance(standards, dict):
                # Process each standard and extract violations properly
                for standard_name, standard_data in standards.items():
                    if isinstance(standard_data, dict):
                        # Convert v1.2 structure to legacy structure
                        legacy_standard = {
                            'compliant': standard_data.get('compliant', True),
                            'score': standard_data.get('score', 100),
                            'risk_level': standard_data.get('risk_level', 'low'),
                            'issues': []
                        }
                        
                        # Extract violations from different possible locations
                        violations = standard_data.get('violations', [])
                        if violations:
                            # Convert ComplianceViolation objects to strings
                            for violation in violations:
                                if isinstance(violation, dict):
                                    if 'message' in violation:
                                        legacy_standard['issues'].append(violation['message'])
                                    elif 'description' in violation:
                                        legacy_standard['issues'].append(violation['description'])
                                    else:
                                        legacy_standard['issues'].append(str(violation))
                                elif isinstance(violation, str):
                                    legacy_standard['issues'].append(violation)
                                else:
                                    legacy_standard['issues'].append(str(violation))
                        
                        # Also check recommendations if no violations found
                        if not legacy_standard['issues']:
                            recommendations = standard_data.get('recommendations', [])
                            if recommendations:
                                legacy_standard['issues'] = recommendations
                        
                        compliance_report[standard_name] = legacy_standard
                
                # Add overall compliance data
                compliance_report.update({
                    'overall_score': v1_2_compliance.get('overall_score', 0),
                    'risk_level': v1_2_compliance.get('risk_level', 'low'),
                    'all_violations': v1_2_compliance.get('all_violations', []),
                    'template_applied': v1_2_compliance.get('template_applied')
                })
        else:
            # Otherwise, add it as v1_2_compliance
            compliance_report['v1_2_compliance'] = v1_2_compliance
    
    return compliance_report

def convert_validation_issue_to_dict(issue) -> Dict[str, Any]:
    """Convert ValidationIssue to dictionary."""
    try:
        logger.debug("convert_validation_issue_to_dict called with: %s", type(issue))

        result = {
            "severity": getattr(issue, 'severity', 'unknown'),
            "description": getattr(issue, 'message', str(issue)),
            "column": getattr(issue, 'column', None),
            "row": getattr(issue, 'row', None),
            "value": getattr(issue, 'value', None),
            "rule_name": getattr(issue, 'rule_name', None)
        }

        logger.debug("Converted issue to dict: %s", result)
        return result
    except Exception as e:
        logger.exception("Error in convert_validation_issue_to_dict: %s", e)
        return {
            "severity": "error",
            "description": f"Failed to convert issue: {str(e)}",
            "column": None,
            "row": None,
            "value": None,
            "rule_name": None
        }


# Extracted API endpoint functions for use by both Flask routes and RESTX resources
def api_root():
    """Root API endpoint with information."""
    return jsonify({
        "message": "Medical Data Validator API",
        "version": "0.1.0",
        "developer": "Rana Ehtasham Ali",
        "documentation": "/docs",
        "health": "/api/health"
    })


def api_health():
    """Health check endpoint for monitoring."""
    return jsonify({
        'status': 'healthy',
        'version': '0.1.0',
        'timestamp': pd.Timestamp.now().isoformat(),
        'standards_supported': ["icd10", "loinc", "cpt", "icd9", "ndc", "fhir", "omop"]
    })


def api_validate_data():
    """Validate JSON data via API."""
    try:
        logger.debug("=== API VALIDATE DATA START ===")

        data = request.get_json()
        logger.debug("Received data: %s - %s", type(data), data)

        if data is None:
            logger.debug("Data is None - returning 400")
            return jsonify({"success": False, "error": "Invalid JSON data"}), 400

        # Handle empty data gracefully
        if not data:
            logger.debug("Data is empty - returning success response")
            return jsonify({
                "success": True,
                "is_valid": True,
                "is_compliant": None,
                "compliance_risk_level": None,
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

        validators_config = None
        if request.args.get('validators'):
            try:
                validators_config = json.loads(request.args.get('validators'))
            except (TypeError, ValueError) as e:
                return jsonify({"success": False, "error": f"Invalid 'validators' JSON: {e}"}), 400

        batch_size = request.args.get('batch_size', type=int)
        use_cache = request.args.get('use_cache', 'false').lower() == 'true'

        logger.debug("Parameters: detect_phi=%s, quality_checks=%s, profile='%s'", detect_phi, quality_checks, profile)

        # Convert data to DataFrame
        logger.debug("Converting data to DataFrame...")
        try:
            # Handle arrays of different lengths by padding with None
            if isinstance(data, dict):
                # Find the maximum length
                max_length = max(len(value) if isinstance(value, list) else 1 for value in data.values())
                logger.debug("Maximum array length: %d", max_length)

                # Pad shorter arrays with None
                padded_data = {}
                for key, value in data.items():
                    if isinstance(value, list):
                        if len(value) < max_length:
                            padded_data[key] = value + [None] * (max_length - len(value))
                            logger.debug("Padded %s from %d to %d items", key, len(value), max_length)
                        else:
                            padded_data[key] = value
                    else:
                        # Convert single values to lists
                        padded_data[key] = [value] * max_length
                        logger.debug("Converted %s single value to list of %d items", key, max_length)

                df = pd.DataFrame(padded_data)
            else:
                df = pd.DataFrame(data)

            logger.debug("DataFrame created: %s - columns: %s", df.shape, list(df.columns))
            logger.debug("DataFrame dtypes: %s", df.dtypes.to_dict())
        except Exception as e:
            logger.exception("Error creating DataFrame: %s", e)
            return jsonify({
                "success": False,
                "error": f"Failed to create DataFrame: {str(e)}",
                "traceback": traceback.format_exc() if current_app.debug else None
            }), 500

        # Create validator
        logger.debug("Creating validator...")
        try:
            validator = create_validator(detect_phi, quality_checks, profile, validators_config=validators_config)
            logger.debug("Validator created with %d rules", len(validator.rules))
        except Exception as e:
            logger.exception("Error creating validator: %s", e)
            return jsonify({
                "success": False,
                "error": f"Failed to create validator: {str(e)}",
                "traceback": traceback.format_exc() if current_app.debug else None
            }), 500

        # Validate data
        logger.debug("Validating data...")
        try:
            if batch_size and batch_size > 0:
                cache = _validation_cache if use_cache else None
                result = BatchValidator(validator, batch_size=batch_size, cache=cache).validate_batches(df)
            else:
                result = validator.validate(df)
            logger.debug("Validation completed: %d issues found", len(result.issues))
        except Exception as e:
            logger.exception("Error during validation: %s", e)
            return jsonify({
                "success": False,
                "error": f"Validation failed: {str(e)}",
                "traceback": traceback.format_exc() if current_app.debug else None
            }), 500

        # Handle v1.2 compliance if enabled
        if validator.enable_compliance and result.summary.get('compliance_report'):
            compliance_report = result.summary['compliance_report']
        else:
            compliance_report = {}

        result_dict = result.to_dict()

        return jsonify({
            "success": True,
            "message": "Validation complete",
            "is_valid": result.is_valid,
            "is_compliant": result_dict["is_compliant"],
            "compliance_risk_level": result_dict["compliance_risk_level"],
            "total_issues": len(result.issues),
            "error_count": len([i for i in result.issues if i.severity == 'error']),
            "warning_count": len([i for i in result.issues if i.severity == 'warning']),
            "info_count": len([i for i in result.issues if i.severity == 'info']),
            "issues": result.issues,
            "summary": result.summary,
            "compliance_report": compliance_report
        })

    except Exception as e:
        logger.exception("Unexpected error in api_validate_data: %s", e)
        return jsonify({
            "success": False,
            "error": f"Unexpected error: {str(e)}",
            "traceback": traceback.format_exc() if current_app.debug else None
        }), 500


def api_validate_file():
    """Validate uploaded file via API."""
    try:
        if 'file' not in request.files:
            return jsonify({'success': False, 'error': 'No file provided'}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'success': False, 'error': 'No file selected'}), 400
        
        # Security: File type validation
        allowed_extensions = {'csv', 'xlsx', 'xls', 'json', 'parquet'}
        if '.' not in file.filename or file.filename.rsplit('.', 1)[1].lower() not in allowed_extensions:
            return jsonify({'success': False, 'error': 'File type not allowed. Supported formats: CSV, Excel, JSON, Parquet'}), 400
        
        # Security: File size validation (16MB limit)
        file.seek(0, 2)  # Seek to end
        file_size = file.tell()
        file.seek(0)  # Reset to beginning
        if file_size > 16 * 1024 * 1024:  # 16MB
            return jsonify({'success': False, 'error': 'File too large. Maximum size is 16MB'}), 400
        
        # Security: Filename sanitization
        import re
        safe_filename = re.sub(r'[^a-zA-Z0-9._-]', '_', file.filename)
        if safe_filename != file.filename:
            return jsonify({'success': False, 'error': 'Invalid filename characters'}), 400
        
        # Get parameters
        detect_phi = request.form.get('detect_phi', 'true').lower() == 'true'
        quality_checks = request.form.get('quality_checks', 'true').lower() == 'true'
        profile = request.form.get('profile', '')
        standards = request.form.getlist('standards') or ["icd10", "loinc", "cpt"]

        validators_config = None
        if request.form.get('validators'):
            try:
                validators_config = json.loads(request.form.get('validators'))
            except (TypeError, ValueError) as e:
                return jsonify({"success": False, "error": f"Invalid 'validators' JSON: {e}"}), 400

        batch_size = request.form.get('batch_size', type=int)
        use_cache = request.form.get('use_cache', 'false').lower() == 'true'

        # Save file temporarily
        with tempfile.NamedTemporaryFile(delete=False, suffix=f".{file.filename.rsplit('.', 1)[1]}") as tmp_file:
            file.save(tmp_file.name)
            tmp_path = tmp_file.name
        
        try:
            # Load data
            data = load_data(tmp_path)

            # Create validator
            validator = create_validator(detect_phi, quality_checks, profile, validators_config=validators_config)

            # Validate data
            if batch_size and batch_size > 0:
                cache = _validation_cache if use_cache else None
                result = BatchValidator(validator, batch_size=batch_size, cache=cache).validate_batches(data)
            else:
                result = validator.validate(data)
            
            # Generate compliance report
            compliance_report = generate_compliance_report(data, result, standards)
            
            # Convert result to dict
            result_dict = convert_numpy_types(result.to_dict())
            issues_dict = [convert_validation_issue_to_dict(issue) for issue in result.issues]
            
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
                    "total_rows": len(data),
                    "total_columns": len(data.columns),
                    "is_valid": result.is_valid,
                    "total_issues": len(result.issues)
                }
            }
            
            return jsonify(response_data)
            
        finally:
            # Clean up temporary file
            try:
                os.unlink(tmp_path)
            except:
                pass
                
    except Exception as e:
        return jsonify({
            "success": False,
            "error": f"File validation failed: {str(e)}",
            "traceback": traceback.format_exc() if current_app.debug else None
        }), 500


def api_compliance_check():
    try:
        # Handle both file uploads and JSON data
        if 'file' in request.files:
            # File upload
            file = request.files['file']
            if file.filename == '':
                return jsonify({"success": False, "error": "No file selected"}), 400
            
            # Read file
            try:
                if file.filename.endswith('.csv'):
                    df = pd.read_csv(file)
                elif file.filename.endswith('.xlsx'):
                    df = pd.read_excel(file)
                else:
                    return jsonify({"success": False, "error": "Unsupported file format"}), 400
            except Exception as e:
                return jsonify({"success": False, "error": f"Failed to read file: {str(e)}"}), 500
        else:
            # JSON data
            data = request.get_json()
            if data is None:
                return jsonify({"success": False, "error": "Invalid JSON data"}), 400
            df = pd.DataFrame(data)
        
        # Get parameters
        standards = request.args.getlist('standards') or ["icd10", "loinc", "cpt", "hipaa"]
        
        # Create validator for compliance check
        try:
            validator = create_validator(detect_phi=True, quality_checks=True, profile='')
        except Exception as validator_error:
            logger.exception("Failed to create validator: %s", validator_error)
            return jsonify({
                "success": False,
                "error": f"Failed to create validator: {str(validator_error)}",
                "traceback": traceback.format_exc() if current_app.debug else None,
            }), 500
        
        # Validate data
        try:
            result = validator.validate(df)
        except Exception as validation_error:
            logger.exception("Validation failed: %s", validation_error)
            return jsonify({
                "success": False,
                "error": f"Validation failed: {str(validation_error)}",
                "traceback": traceback.format_exc() if current_app.debug else None,
            }), 500
        
        # Get compliance report from result
        compliance_report = result.summary.get('compliance_report', {})
        
        # Handle v1.2 compliance structure
        if 'standards' in compliance_report:
            v1_2_standards = compliance_report['standards']
            if isinstance(v1_2_standards, dict):
                # Flatten the structure for backward compatibility
                flattened_report = {
                    'hipaa': v1_2_standards.get('hipaa', {}),
                    'gdpr': v1_2_standards.get('gdpr', {}),
                    'fda': v1_2_standards.get('fda', {}),
                    'medical_coding': v1_2_standards.get('medical_coding', {}),
                    'icd10': v1_2_standards.get('medical_coding', {}).get('icd10', {}),
                    'loinc': v1_2_standards.get('medical_coding', {}).get('loinc', {}),
                    'cpt': v1_2_standards.get('medical_coding', {}).get('cpt', {}),
                    'overall_score': compliance_report.get('overall_score', 0),
                    'risk_level': compliance_report.get('risk_level', 'low'),
                    'all_violations': compliance_report.get('all_violations', [])
                }
                compliance_report = flattened_report
        
        return jsonify({
            "hipaa_compliant": compliance_report.get("hipaa", {}).get("score", 0) >= 80 and len(compliance_report.get("hipaa", {}).get("violations", [])) == 0,
            "icd10_compliant": compliance_report.get("icd10", {}).get("score", 0) >= 80,
            "loinc_compliant": compliance_report.get("loinc", {}).get("score", 0) >= 80,
            "cpt_compliant": compliance_report.get("cpt", {}).get("score", 0) >= 80,
            "fhir_compliant": True,  # Default for backward compatibility
            "omop_compliant": True,  # Default for backward compatibility
            "details": compliance_report
        })
    except Exception as e:
        logger.exception("Unhandled error: %s", e)
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc() if current_app.debug else None,
        }), 500


def api_v1_2_compliance():
    try:
        if 'file' not in request.files:
            return jsonify({"success": False, "error": "No file provided"}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({"success": False, "error": "No file selected"}), 400
        
        # Read file
        try:
            if file.filename.endswith('.csv'):
                df = pd.read_csv(file)
            elif file.filename.endswith('.xlsx'):
                df = pd.read_excel(file)
            else:
                return jsonify({"success": False, "error": "Unsupported file format"}), 400
        except Exception as e:
            return jsonify({"success": False, "error": f"Failed to read file: {str(e)}"}), 500
        
        # Get template from request
        template = request.form.get('template')
        
        # Handle empty dataframe
        if df.empty:
            return jsonify({
                "success": True,
                "message": "v1.2 Advanced Compliance Validation Complete (Empty Dataset)",
                "compliance_report": {
                    'hipaa': {'score': 100, 'risk_level': 'low', 'violations': [], 'violations_count': 0},
                    'gdpr': {'score': 100, 'risk_level': 'low', 'violations': [], 'violations_count': 0},
                    'fda': {'score': 100, 'risk_level': 'low', 'violations': [], 'violations_count': 0},
                    'medical_coding': {'score': 100, 'risk_level': 'low', 'violations': [], 'violations_count': 0},
                    'overall_score': 100,
                    'risk_level': 'low',
                    'all_violations': [],
                    'template_applied': template
                }
            })
        
        # Create validator with v1.2 compliance enabled and optional template
        try:
            validator = create_validator(detect_phi=True, quality_checks=True, profile='', enable_compliance=True, template=template)
        except Exception as validator_error:
            logger.exception("Failed to create validator: %s", validator_error)
            return jsonify({
                "success": False,
                "error": f"Failed to create validator: {str(validator_error)}",
                "traceback": traceback.format_exc() if current_app.debug else None,
            }), 500
        
        # Apply custom rules from global storage
        if validator.compliance_engine is not None:
            for rule_data in _custom_rules_storage:
                validator.compliance_engine.add_custom_pattern(
                    name=rule_data['name'],
                    pattern=rule_data['pattern'],
                    severity=rule_data['severity'],
                    field_pattern=rule_data.get('field_pattern'),
                    description=rule_data.get('description', ''),
                    recommendation=rule_data.get('recommendation')
                )
        
        # Validate data
        try:
            result = validator.validate(df)
        except Exception as validation_error:
            logger.exception("Validation failed: %s", validation_error)
            return jsonify({
                "success": False,
                "error": f"Validation failed: {str(validation_error)}",
                "traceback": traceback.format_exc() if current_app.debug else None,
            }), 500
        
        # Get v1.2 compliance report
        compliance_report = result.summary.get('compliance_report', {})
        
        # Flatten the structure to match test expectations
        if 'standards' in compliance_report:
            standards = compliance_report['standards']
            if isinstance(standards, dict):
                flattened_report = {
                    'hipaa': standards.get('hipaa', {}),
                    'gdpr': standards.get('gdpr', {}),
                    'fda': standards.get('fda', {}),
                    'medical_coding': standards.get('medical_coding', {}),
                    'overall_score': compliance_report.get('overall_score', 0),
                    'risk_level': compliance_report.get('risk_level', 'low'),
                    'all_violations': compliance_report.get('all_violations', []),
                    'template_applied': compliance_report.get('template_applied')
                }
                compliance_report = flattened_report
        
        return jsonify({
            "success": True,
            "message": "v1.2 Advanced Compliance Validation Complete",
            "compliance_report": compliance_report
        })
    except Exception as e:
        logger.exception("Unhandled error: %s", e)
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc() if current_app.debug else None,
        }), 500


def api_templates():
    """Get available compliance templates."""
    try:
        validator = MedicalDataValidator(enable_compliance=True)
        templates = validator.get_available_compliance_templates()
        # Convert dict to list of dicts with name and description
        template_list = [
            {"name": name, "description": desc}
            for name, desc in templates.items()
        ]
        return jsonify(template_list)
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# Global storage for custom rules (in-memory for now)
_custom_rules_storage = []

def api_custom_rules():
    """Get custom compliance rules."""
    return jsonify(_custom_rules_storage)


def api_add_custom_rule():
    """Add a custom compliance rule."""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"success": False, "error": "No data provided"}), 400
        
        required_fields = ['name', 'pattern']
        for field in required_fields:
            if field not in data:
                return jsonify({"success": False, "error": f"Missing required field: {field}"}), 400
        
        # Add to global storage
        rule_data = {
            'name': data['name'],
            'pattern': data['pattern'],
            'severity': data.get('severity', 'medium'),
            'field_pattern': data.get('field_pattern'),
            'description': data.get('description', ''),
            'recommendation': data.get('recommendation')
        }
        
        # Check if rule already exists
        for i, existing_rule in enumerate(_custom_rules_storage):
            if existing_rule['name'] == data['name']:
                _custom_rules_storage[i] = rule_data
                return jsonify({
                    "success": True,
                    "message": "Custom rule updated successfully"
                })
        
        _custom_rules_storage.append(rule_data)
        
        return jsonify({
            "success": True,
            "message": "Custom rule added successfully"
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


def api_remove_custom_rule(rule_name):
    """Remove a custom compliance rule."""
    try:
        # Remove from global storage
        for i, rule in enumerate(_custom_rules_storage):
            if rule['name'] == rule_name:
                _custom_rules_storage.pop(i)
                return jsonify({
                    "success": True,
                    "message": f'Rule "{rule_name}" removed successfully'
                })
        
        return jsonify({"success": False, "error": f'Rule "{rule_name}" not found'}), 404
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


def api_anonymize():
    """Anonymize PHI/PII columns in uploaded data or JSON payload."""
    try:
        method = request.args.get('method', 'hipaa_safe_harbor')
        if method not in ('hipaa_safe_harbor', 'hash', 'mask'):
            return jsonify({'success': False, 'error': f"Unknown method '{method}'. Use hipaa_safe_harbor, hash, or mask."}), 400

        if 'file' in request.files:
            file = request.files['file']
            if not file or file.filename == '':
                return jsonify({'success': False, 'error': 'No file selected'}), 400
            if file.filename.endswith('.csv'):
                df = pd.read_csv(file)
            elif file.filename.endswith(('.xlsx', '.xls')):
                df = pd.read_excel(file)
            else:
                return jsonify({'success': False, 'error': 'Unsupported file format'}), 400
            columns_raw = request.form.get('columns')
        else:
            payload = request.get_json(silent=True)
            if payload is None:
                return jsonify({'success': False, 'error': 'No data provided'}), 400
            df = pd.DataFrame(payload.get('data', payload))
            columns_raw = payload.get('columns')

        columns = [c.strip() for c in columns_raw.split(',')] if isinstance(columns_raw, str) else columns_raw

        validator = MedicalDataValidator(enable_compliance=False, enable_analytics=False, enable_monitoring=False)
        anonymized_df = validator.anonymize(df, columns=columns, method=method)

        return jsonify({
            'success': True,
            'method': method,
            'columns_anonymized': columns or [],
            'rows': len(anonymized_df),
            'data': anonymized_df.to_dict(orient='records'),
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


def api_analytics():
    """Get advanced analytics for uploaded data."""
    try:
        if 'file' not in request.files or request.files['file'] is None:
            return jsonify({"success": False, "error": "No file provided"}), 400
        file = request.files['file']
        if not file or not hasattr(file, 'filename') or file.filename == '':
            return jsonify({"success": False, "error": "No file selected"}), 400
        # Read file
        try:
            if file.filename and file.filename.endswith('.csv'):
                df = pd.read_csv(file)
            elif file.filename and file.filename.endswith('.xlsx'):
                df = pd.read_excel(file)
            else:
                return jsonify({"success": False, "error": "Unsupported file format"}), 400
        except Exception as e:
            return jsonify({"success": False, "error": f"Failed to read file: {str(e)}"}), 500
        # Get time column from request
        time_column = request.form.get('time_column')
        # Create analytics engine
        try:
            from medical_data_validator.analytics import AdvancedAnalytics
            analytics_engine = AdvancedAnalytics()
            
            # Add timeout and error handling for large datasets
            try:
                analytics_report = analytics_engine.comprehensive_analysis(df, time_column)
            except Exception as analytics_error:
                logger.exception("Error in analytics processing: %s", analytics_error)
                return jsonify({
                    "success": False,
                    "error": f"Analytics processing failed: {str(analytics_error)}",
                    "error_type": type(analytics_error).__name__,
                    "traceback": traceback.format_exc() if current_app.debug else None,
                }), 500

            logger.debug("analytics_report: %s", analytics_report)
            serialized_report = convert_numpy_types({
                "success": True,
                "quality_metrics": analytics_report.get('quality_metrics', {}),
                "anomalies": analytics_report.get('anomalies', []),
                "trends": analytics_report.get('trends', []),
                "statistical_summary": analytics_report.get('statistical_summary', {}),
                "overall_quality_score": analytics_report.get('overall_quality_score', 0.0)
            })
            try:
                logger.debug("serialized_report: %s", serialized_report)
                return jsonify(serialized_report)
            except Exception as e:
                logger.exception("Error serializing analytics response: %s", e)
                return jsonify({
                    "success": False,
                    "error": f"Serialization error: {str(e)}",
                    "traceback": traceback.format_exc() if current_app.debug else None,
                    "serialized_report": str(serialized_report)
                }), 500
        except ImportError as import_error:
            return jsonify({
                "success": False, 
                "error": f"Analytics module not available: {str(import_error)}"
            }), 500
        except Exception as e:
            return jsonify({
                "success": False, 
                "error": f"Analytics endpoint error: {str(e)}",
                "error_type": type(e).__name__
            }), 500
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


def api_monitoring_stats():
    """Get monitoring statistics."""
    try:
        from medical_data_validator.monitoring import monitor
        stats = monitor.get_monitoring_stats()
        return jsonify(stats)
    except ImportError:
        return jsonify({"success": False, "error": "Monitoring module not available"}), 500
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


def api_monitoring_alerts():
    """Get active monitoring alerts."""
    try:
        from medical_data_validator.monitoring import monitor
        alerts = monitor.get_active_alerts()
        return jsonify(alerts)
    except ImportError:
        return jsonify({"success": False, "error": "Monitoring module not available"}), 500
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


def api_acknowledge_alert(alert_id):
    """Acknowledge a monitoring alert."""
    try:
        from medical_data_validator.monitoring import monitor
        success = monitor.acknowledge_alert(alert_id)
        
        if success:
            return jsonify({
                "success": True,
                "message": f"Alert {alert_id} acknowledged"
            })
        else:
            return jsonify({"success": False, "error": f"Alert {alert_id} not found"}), 404
    except ImportError:
        return jsonify({"success": False, "error": "Monitoring module not available"}), 500
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


def api_resolve_alert(alert_id):
    """Resolve a monitoring alert."""
    try:
        from medical_data_validator.monitoring import monitor
        success = monitor.resolve_alert(alert_id)
        
        if success:
            return jsonify({
                "success": True,
                "message": f"Alert {alert_id} acknowledged"
            })
        else:
            return jsonify({"success": False, "error": f"Alert {alert_id} not found"}), 404
    except ImportError:
        return jsonify({"success": False, "error": "Monitoring module not available"}), 500
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


def api_quality_trends(metric_name):
    """Get quality trends for a specific metric."""
    try:
        from medical_data_validator.monitoring import monitor
        hours = request.args.get('hours', 24, type=int)
        trends = monitor.get_quality_trends(metric_name, hours)
        return jsonify({
            "success": True,
            "trends": trends
        })
    except ImportError:
        return jsonify({"success": False, "error": "Monitoring module not available"}), 500
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


def api_profiles():
    """Get available validation profiles."""
    profiles = {
        'clinical_trials': 'Clinical trial data validation',
        'ehr': 'Electronic health records validation',
        'imaging': 'Medical imaging metadata validation',
        'lab': 'Laboratory data validation'
    }
    return jsonify(profiles)


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


def create_api_blueprint():
    """Create and configure the API Blueprint."""
    api_bp = Blueprint('api', __name__, url_prefix='/api')
    
    @api_bp.route('/', methods=['GET'])
    def api_root_endpoint():
        """Root API endpoint with information."""
        return api_root()

    @api_bp.route('/compliance/v1.2', methods=['POST'])
    def api_v1_2_compliance_endpoint():
        """v1.2 Advanced compliance validation."""
        return api_v1_2_compliance()

    @api_bp.route('/compliance/templates', methods=['GET'])
    def api_templates_endpoint():
        """Get available compliance templates."""
        return api_templates()

    @api_bp.route('/compliance/custom-rules', methods=['GET'])
    def api_custom_rules_endpoint():
        """Get custom compliance rules."""
        return api_custom_rules()

    @api_bp.route('/compliance/custom-rules', methods=['POST'])
    def api_add_custom_rule_endpoint():
        """Add a custom compliance rule."""
        return api_add_custom_rule()

    @api_bp.route('/compliance/custom-rules/<rule_name>', methods=['DELETE'])
    def api_remove_custom_rule_endpoint(rule_name):
        """Remove a custom compliance rule."""
        return api_remove_custom_rule(rule_name)

    @api_bp.route('/anonymize', methods=['POST'])
    def api_anonymize_endpoint():
        """Anonymize PHI/PII columns."""
        return api_anonymize()

    @api_bp.route('/analytics', methods=['POST'])
    def api_analytics_endpoint():
        """Get advanced analytics for uploaded data."""
        return api_analytics()

    @api_bp.route('/monitoring/stats', methods=['GET'])
    def api_monitoring_stats_endpoint():
        """Get monitoring statistics."""
        return api_monitoring_stats()

    @api_bp.route('/monitoring/alerts', methods=['GET'])
    def api_monitoring_alerts_endpoint():
        """Get active monitoring alerts."""
        return api_monitoring_alerts()

    @api_bp.route('/monitoring/alerts/<alert_id>/acknowledge', methods=['POST'])
    def api_acknowledge_alert_endpoint(alert_id):
        """Acknowledge a monitoring alert."""
        return api_acknowledge_alert(alert_id)

    @api_bp.route('/monitoring/alerts/<alert_id>/resolve', methods=['POST'])
    def api_resolve_alert_endpoint(alert_id):
        """Resolve a monitoring alert."""
        return api_resolve_alert(alert_id)

    @api_bp.route('/monitoring/trends/<metric_name>', methods=['GET'])
    def api_quality_trends_endpoint(metric_name):
        """Get quality trends for a specific metric."""
        return api_quality_trends(metric_name)

    return api_bp

def dataframe_from_request():
    """
    Load a DataFrame from either a multipart file upload or a raw JSON body,
    matching the same input contract api_validate_data/api_validate_file use.

    Returns (df, tmp_path). tmp_path is a real temp-file path the caller must
    os.unlink() when the request was a file upload (so file-path-aware checks
    like SecurityAuditor's have something real to inspect), or None for a
    JSON-body request. Raises ValueError with a user-facing message on bad input.
    """
    if 'file' in request.files:
        file = request.files['file']
        if file.filename == '':
            raise ValueError("No file selected")
        allowed_extensions = {'csv', 'xlsx', 'xls', 'json', 'parquet'}
        if '.' not in file.filename or file.filename.rsplit('.', 1)[1].lower() not in allowed_extensions:
            raise ValueError("File type not allowed. Supported formats: CSV, Excel, JSON, Parquet")
        with tempfile.NamedTemporaryFile(delete=False, suffix=f".{file.filename.rsplit('.', 1)[1]}") as tmp_file:
            file.save(tmp_file.name)
            tmp_path = tmp_file.name
        try:
            return load_data(tmp_path), tmp_path
        except Exception:
            os.unlink(tmp_path)
            raise

    data = request.get_json(silent=True)
    if not data:
        raise ValueError("No file or JSON data provided")
    if isinstance(data, dict):
        max_length = max(len(v) if isinstance(v, list) else 1 for v in data.values())
        padded = {}
        for key, value in data.items():
            if isinstance(value, list):
                padded[key] = value + [None] * (max_length - len(value)) if len(value) < max_length else value
            else:
                padded[key] = [value] * max_length
        df = pd.DataFrame(padded)
    else:
        df = pd.DataFrame(data)
    return df, None

def create_validator(detect_phi: bool, quality_checks: bool, profile: str, enable_compliance: bool = True, template: str | None = None, validators_config: Optional[dict] = None) -> MedicalDataValidator:
    """Create a validator with the specified configuration."""
    # Handle profile-based validation
    if profile and profile.strip():  # Check if profile is not empty
        profile_validator = get_profile(profile)
        if profile_validator:
            return profile_validator.create_validator()

    # Create basic validator with compliance support (v1.2) and optional template
    validator = MedicalDataValidator(enable_compliance=enable_compliance, compliance_template=template)

    # Always add basic quality checks to ensure we have some validation
    validator.add_rule(DataQualityChecker())

    # Add optional rules based on user selection
    if detect_phi:
        validator.add_rule(PHIDetector())

    # Add rules from per-request validators_config, if provided
    if validators_config:
        required_columns = validators_config.get('required_columns')
        column_types = validators_config.get('column_types')
        if required_columns or column_types:
            validator.add_rule(SchemaValidator(required_columns=required_columns, column_types=column_types))

        ranges = validators_config.get('ranges')
        if ranges:
            validator.add_rule(RangeValidator(ranges=ranges))

        date_columns = validators_config.get('date_columns')
        if date_columns:
            validator.add_rule(DateValidator(
                date_columns=date_columns,
                min_date=validators_config.get('min_date'),
                max_date=validators_config.get('max_date'),
            ))

        code_columns = validators_config.get('code_columns')
        if code_columns:
            validator.add_rule(MedicalCodeValidator(code_columns))

    return validator

def register_routes(app):
    """Register all routes (UI and API) with the Flask app."""
    # Auth routes (/api/auth/*)
    try:
        from medical_data_validator.auth import register_auth_routes
    except ImportError:
        try:
            from ..auth import register_auth_routes
        except ImportError:
            register_auth_routes = None

    if register_auth_routes:
        register_auth_routes(app)

    # Security routes (/api/security/*)
    try:
        from medical_data_validator.security import register_security_routes
    except ImportError:
        try:
            from ..security import register_security_routes
        except ImportError:
            register_security_routes = None

    if register_security_routes:
        register_security_routes(app)

    # Audit routes (/api/audit)
    try:
        from medical_data_validator.audit import register_audit_routes
    except ImportError:
        try:
            from ..audit import register_audit_routes
        except ImportError:
            register_audit_routes = None

    if register_audit_routes:
        register_audit_routes(app)

    # Registry routes (/api/registry/*)
    try:
        from medical_data_validator.registry import register_registry_routes
    except ImportError:
        try:
            from ..registry import register_registry_routes
        except ImportError:
            register_registry_routes = None

    if register_registry_routes:
        register_registry_routes(app)

    # Job queue routes (/api/jobs)
    try:
        from medical_data_validator.jobs import register_job_routes
    except ImportError:
        try:
            from ..jobs import register_job_routes
        except ImportError:
            register_job_routes = None

    if register_job_routes:
        register_job_routes(app)

    # Report export routes (/api/report/*)
    try:
        from medical_data_validator.reports import register_report_routes
    except ImportError:
        try:
            from ..reports import register_report_routes
        except ImportError:
            register_report_routes = None

    if register_report_routes:
        register_report_routes(app)

    # Create and register API Blueprint
    api_bp = create_api_blueprint()
    app.register_blueprint(api_bp)
    
    # Register documentation routes
    try:
        from medical_data_validator.dashboard.docs import docs_bp, create_swagger_api
        app.register_blueprint(docs_bp)
        create_swagger_api(app)
    except ImportError as e:
        logger.warning("Documentation routes not available: %s", e)
        # Fallback: create simple docs route
        @app.route('/docs')
        def docs_fallback():
            return """
            <html>
            <head><title>Documentation</title></head>
            <body>
                <h1>Medical Data Validator Documentation</h1>
                <p>Documentation is being loaded...</p>
                <p><a href="/docs/markdown/API_DOCUMENTATION.md">API Documentation</a></p>
                <p><a href="/docs/markdown/API_CURL_EXAMPLES.md">cURL Examples</a></p>
            </body>
            </html>
            """
    
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
            # Generate compliance report
            standards = ['hipaa', 'icd10', 'loinc', 'cpt', 'fhir', 'omop']
            compliance_report = generate_compliance_report(data, result, standards)
            os.unlink(tmp_path)
            # Convert result to dict and handle numpy types
            result_dict = convert_numpy_types(result.to_dict())
            charts_dict = convert_numpy_types(charts)
            
            return jsonify({
                'success': True,
                'result': result_dict,
                'charts': charts_dict,
                'compliance_report': compliance_report,
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