# Medical Data Validator API Documentation

## Overview

The Medical Data Validator API provides comprehensive validation services for healthcare datasets with support for multiple medical standards, compliance checking, and advanced analytics.

## Base URLs
```
# v1.2 endpoints (recommended)
https://medical-data-validator-production.up.railway.app/api/v1.2

# Legacy v1.0 endpoints (backward compatible)
https://medical-data-validator-production.up.railway.app/api
```

## Authentication

Currently, the API operates without authentication for development. For production deployment, implement appropriate authentication mechanisms.

## API v1.2 Endpoints

### 1. Health Check

**GET** `/api/v1.2/health`

Check API status and supported standards.

**Response:**
```json
{
  "status": "healthy",
  "version": "1.2.0",
  "timestamp": "2024-01-15T10:30:00Z",
  "standards_supported": ["icd10", "loinc", "cpt", "icd9", "ndc", "fhir", "omop"],
  "compliance_templates": ["clinical_trials", "ehr", "imaging", "lab"],
  "features": ["advanced_compliance", "analytics", "monitoring", "risk_assessment"]
}
```

### 2. Validate JSON Data

**POST** `/api/v1.2/validate/data`

Validate structured JSON data for medical compliance with advanced v1.2 features.

**Request Body:**
```json
{
  "patient_id": ["001", "002", "003"],
  "age": [30, 45, 28],
  "diagnosis": ["E11.9", "I10", "Z51.11"],
  "ssn": ["123-45-6789", "987-65-4321", "555-12-3456"]
}
```

**Query Parameters:**
- `detect_phi` (boolean): Enable PHI/PII detection (default: true)
- `quality_checks` (boolean): Enable data quality checks (default: true)
- `profile` (string): Validation profile (clinical_trials, ehr, imaging, lab)
- `standards` (array): Medical standards to check (icd10, loinc, cpt, hipaa, gdpr, fda)
- `compliance_template` (string): Use predefined compliance template
- `risk_assessment` (boolean): Enable risk assessment (default: true)

**Response:**
```json
{
  "success": true,
  "is_valid": false,
  "total_issues": 3,
  "error_count": 1,
  "warning_count": 2,
  "info_count": 0,
  "compliance_report": {
    "hipaa": {
      "compliant": false,
      "issues": ["SSN detected in column: ssn"],
      "score": 50,
      "risk_level": "high"
    },
    "gdpr": {
      "compliant": true,
      "issues": [],
      "score": 100,
      "risk_level": "low"
    },
    "fda_21_cfr_part_11": {
      "compliant": true,
      "issues": [],
      "score": 100,
      "risk_level": "low"
    },
    "icd10": {
      "compliant": true,
      "issues": [],
      "score": 100,
      "risk_level": "low"
    }
  },
  "risk_assessment": {
    "overall_risk": "medium",
    "risk_score": 65,
    "recommendations": [
      "Remove or encrypt SSN data",
      "Implement data anonymization",
      "Review data retention policies"
    ]
  },
  "analytics": {
    "data_quality_score": 85,
    "completeness": 95,
    "accuracy": 90,
    "consistency": 80,
    "timeliness": 100
  },
  "issues": [
    {
      "severity": "error",
      "description": "SSN detected in column: ssn",
      "column": "ssn",
      "row": null,
      "value": null,
      "rule_name": "PHIDetector",
      "compliance_impact": ["hipaa"]
    }
  ],
  "summary": {
    "total_rows": 3,
    "total_columns": 4,
    "is_valid": false,
    "total_issues": 3
  }
}
```

### 3. Validate File Upload

**POST** `/api/v1.2/validate/file`

Upload and validate medical data files (CSV, Excel, JSON, Parquet) with v1.2 compliance features.

**Form Data:**
- `file`: The file to validate
- `detect_phi`: Enable PHI detection (true/false)
- `quality_checks`: Enable quality checks (true/false)
- `profile`: Validation profile
- `standards`: Array of standards to check
- `compliance_template`: Use predefined compliance template
- `risk_assessment`: Enable risk assessment (true/false)

**Supported Formats:**
- CSV (.csv)
- Excel (.xlsx, .xls)
- JSON (.json)
- Parquet (.parquet)

**File Size Limit:** 16MB

### 4. Compliance Check

**POST** `/api/v1.2/compliance/check`

Advanced compliance assessment for medical standards with risk assessment.

**Request Body:**
```json
{
  "patient_id": ["001", "002"],
  "diagnosis": ["E11.9", "I10"],
  "procedure": ["99213", "93010"]
}
```

**Response:**
```json
{
  "hipaa_compliant": true,
  "gdpr_compliant": true,
  "fda_21_cfr_part_11_compliant": true,
  "icd10_compliant": true,
  "loinc_compliant": false,
  "cpt_compliant": true,
  "fhir_compliant": true,
  "omop_compliant": true,
  "overall_compliance_score": 85,
  "risk_assessment": {
    "overall_risk": "low",
    "risk_score": 25,
    "risk_factors": ["loinc_validation_failed"]
  },
  "details": {
    "hipaa": {
      "compliant": true,
      "issues": [],
      "score": 100,
      "risk_level": "low"
    },
    "gdpr": {
      "compliant": true,
      "issues": [],
      "score": 100,
      "risk_level": "low"
    }
  }
}
```

### 5. Compliance Templates

**GET** `/api/v1.2/compliance/templates`

Get available compliance templates.

**Response:**
```json
{
  "clinical_trials": {
    "name": "Clinical Trials Compliance",
    "description": "FDA 21 CFR Part 11 compliant validation for clinical trial data",
    "standards": ["fda_21_cfr_part_11", "hipaa", "icd10", "loinc"],
    "required_checks": ["audit_trail", "electronic_signatures", "data_integrity"]
  },
  "ehr": {
    "name": "Electronic Health Records",
    "description": "HIPAA and Meaningful Use compliant validation for EHR data",
    "standards": ["hipaa", "icd10", "loinc", "cpt"],
    "required_checks": ["phi_detection", "data_quality", "medical_codes"]
  },
  "imaging": {
    "name": "Medical Imaging",
    "description": "DICOM and HIPAA compliant validation for imaging metadata",
    "standards": ["hipaa", "dicom"],
    "required_checks": ["metadata_validation", "phi_detection"]
  },
  "lab": {
    "name": "Laboratory Data",
    "description": "CLIA and LOINC compliant validation for laboratory data",
    "standards": ["clia", "loinc", "hipaa"],
    "required_checks": ["loinc_validation", "quality_control"]
  }
}
```

### 6. Data Quality Analytics

**GET** `/api/v1.2/analytics/quality`

Get detailed data quality analytics and metrics.

**Query Parameters:**
- `dataset_id` (string): Dataset identifier for historical analysis
- `time_range` (string): Time range for analytics (1d, 7d, 30d, 90d)

**Response:**
```json
{
  "data_quality_score": 85,
  "metrics": {
    "completeness": 95,
    "accuracy": 90,
    "consistency": 80,
    "timeliness": 100,
    "validity": 88
  },
  "trends": {
    "completeness_trend": [92, 94, 95, 96, 95],
    "accuracy_trend": [88, 89, 90, 91, 90],
    "consistency_trend": [75, 78, 80, 82, 80]
  },
  "anomalies": [
    {
      "metric": "completeness",
      "value": 85,
      "expected_range": [90, 100],
      "severity": "warning"
    }
  ],
  "recommendations": [
    "Improve data completeness by 5%",
    "Address consistency issues in patient_id field"
  ]
}
```

### 7. System Monitoring

**GET** `/api/v1.2/monitoring/status`

Get real-time system monitoring and performance metrics.

**Response:**
```json
{
  "system_status": "healthy",
  "uptime": "7d 12h 30m",
  "performance": {
    "response_time_avg": 150,
    "throughput": 1000,
    "error_rate": 0.1,
    "cpu_usage": 45,
    "memory_usage": 60
  },
  "compliance_monitoring": {
    "active_validations": 25,
    "compliance_score_avg": 88,
    "risk_alerts": 2,
    "last_alert": "2024-01-15T10:25:00Z"
  },
  "alerts": [
    {
      "type": "compliance_risk",
      "message": "High risk data detected in validation",
      "severity": "warning",
      "timestamp": "2024-01-15T10:25:00Z"
    }
  ]
}
```

### 8. Get Available Profiles

**GET** `/api/v1.2/profiles`

Retrieve available validation profiles.

**Response:**
```json
{
  "clinical_trials": "Clinical trial data validation with FDA 21 CFR Part 11 compliance",
  "ehr": "Electronic health records validation with HIPAA compliance",
  "imaging": "Medical imaging metadata validation with DICOM compliance",
  "lab": "Laboratory data validation with CLIA and LOINC compliance"
}
```

### 9. Get Standards Information

**GET** `/api/v1.2/standards`

Get detailed information about supported medical standards.

**Response:**
```json
{
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
    "description": "Universal standard for identifying medical laboratory observations"
  },
  "hipaa": {
    "name": "Health Insurance Portability and Accountability Act",
    "version": "2023",
    "authority": "HHS",
    "description": "Federal law for protecting patient health information"
  },
  "gdpr": {
    "name": "General Data Protection Regulation",
    "version": "2018",
    "authority": "EU",
    "description": "EU regulation for data protection and privacy"
  },
  "fda_21_cfr_part_11": {
    "name": "FDA 21 CFR Part 11",
    "version": "2023",
    "authority": "FDA",
    "description": "Electronic records and electronic signatures regulation"
  }
}
```

## Legacy v1.0 Endpoints (Backward Compatible)

The following v1.0 endpoints remain functional for backward compatibility:

### Health Check (v1.0)
**GET** `/api/health`

### Validate JSON Data (v1.0)
**POST** `/api/validate/data`

### Validate File Upload (v1.0)
**POST** `/api/validate/file`

### Compliance Check (v1.0)
**POST** `/api/compliance/check`

### Get Available Profiles (v1.0)
**GET** `/api/profiles`

### Get Standards Information (v1.0)
**GET** `/api/standards`

## Error Handling

### Standard Error Response Format

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Invalid data format",
    "details": {
      "field": "patient_id",
      "issue": "Missing required column"
    },
    "timestamp": "2024-01-15T10:30:00Z"
  }
}
```

### Common Error Codes

- `VALIDATION_ERROR`: Data validation failed
- `COMPLIANCE_ERROR`: Compliance check failed
- `FILE_ERROR`: File upload or processing error
- `SYSTEM_ERROR`: Internal system error
- `RATE_LIMIT_ERROR`: Too many requests

## Rate Limiting

- **Standard endpoints**: 100 requests per minute
- **File upload endpoints**: 10 requests per minute
- **Analytics endpoints**: 50 requests per minute

## CORS Support

The API supports Cross-Origin Resource Sharing (CORS) for web applications:

```javascript
// Example CORS request
fetch('https://medical-data-validator-production.up.railway.app/api/v1.2/validate/data', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
  },
  body: JSON.stringify(data)
})
.then(response => response.json())
.then(result => console.log(result));
```

## SDK Examples

### Python SDK

```python
import requests

# Validate data with v1.2 features
response = requests.post(
    'https://medical-data-validator-production.up.railway.app/api/v1.2/validate/data',
    json=medical_data,
    params={
        'compliance_template': 'clinical_trials',
        'risk_assessment': True
    }
)

# Get analytics
analytics = requests.get(
    'https://medical-data-validator-production.up.railway.app/api/v1.2/analytics/quality',
    params={'dataset_id': 'dataset_123'}
).json()

# Check system status
status = requests.get('https://medical-data-validator-production.up.railway.app/api/v1.2/monitoring/status').json()
```

### JavaScript/Node.js

```javascript
const axios = require('axios');

// Validate data
const validateData = async (data) => {
  const response = await axios.post(
    'https://medical-data-validator-production.up.railway.app/api/v1.2/validate/data',
    data,
    {
      params: {
        compliance_template: 'clinical_trials',
        risk_assessment: true
      }
    }
  );
  return response.data;
};

// Get compliance templates
const getTemplates = async () => {
  const response = await axios.get('https://medical-data-validator-production.up.railway.app/api/v1.2/compliance/templates');
  return response.data;
};
```

### JavaScript Example

```javascript
// Validate data with v1.2 features
const data = {
    patient_id: ['001', '002', '003'],
    diagnosis: ['E11.9', 'I10', 'Z51.11'],
    procedure: ['99213', '93010', '80048']
};

fetch('https://medical-data-validator-production.up.railway.app/api/v1.2/validate/data', {
    method: 'POST',
    headers: {
        'Content-Type': 'application/json',
    },
    body: JSON.stringify(data)
})
.then(response => response.json())
.then(result => {
    console.log('Validation result:', result);
    console.log('Compliance score:', result.compliance_report.overall_score);
});
```

### Python Example

```python
import requests

# Validate data
data = {
    'patient_id': ['001', '002', '003'],
    'diagnosis': ['E11.9', 'I10', 'Z51.11'],
    'procedure': ['99213', '93010', '80048']
}

response = requests.post(
    'https://medical-data-validator-production.up.railway.app/api/v1.2/validate/data',
    json=data
)

result = response.json()
print(f"Valid: {result['is_valid']}")
print(f"Total issues: {result['total_issues']}")
```

### Advanced Analytics

```python
# Get data quality analytics
response = requests.post(
    'https://medical-data-validator-production.up.railway.app/api/v1.2/analytics/quality',
    json=data
)

analytics = response.json()
print(f"Data quality score: {analytics['data_quality_score']}%")

# Get monitoring status
status = requests.get('https://medical-data-validator-production.up.railway.app/api/v1.2/monitoring/status').json()
print(f"System health: {status['health']}")
```

### File Upload Example

```python
import requests

# Upload and validate file
with open('medical_data.csv', 'rb') as f:
    files = {'file': f}
    data = {
        'compliance_template': 'clinical_trials',
        'risk_assessment': 'true'
    }
    
    response = requests.post(
        'https://medical-data-validator-production.up.railway.app/api/v1.2/validate/data',
        files=files,
        data=data
    )

result = response.json()
print(f"File validation successful: {result['success']}")
```

### Compliance Templates

```javascript
// Get available compliance templates
const response = await axios.get('https://medical-data-validator-production.up.railway.app/api/v1.2/compliance/templates');
const templates = response.data;
console.log('Available templates:', templates);
```

## Legacy API (v1.0)

### Basic Validation

```python
import requests

data = {
    'patient_id': ['001', '002'],
    'diagnosis': ['E11.9', 'I10']
}

response = requests.post(
    'https://medical-data-validator-production.up.railway.app/api/validate/data',
    json=data
)

result = response.json()
print(f"Valid: {result['is_valid']}")
```

### v1.2 Enhanced Validation

```python
# Same endpoint with enhanced features
response = requests.post(
    'https://medical-data-validator-production.up.railway.app/api/v1.2/validate/data',
    json=data
)

result = response.json()
print(f"Compliance score: {result['compliance_report']['overall_score']}%")
```

## Support

For API support and questions:
- **Documentation**: [API Documentation](API_DOCUMENTATION.md)
- **Issues**: [GitHub Issues](https://github.com/RanaEhtashamAli/medical-data-validator/issues)
- **Email**: ranaehtashamali1@gmail.com 