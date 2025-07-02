# Medical Data Validator API Documentation

## Overview

The Medical Data Validator API provides enterprise-grade validation for healthcare datasets, ensuring compliance with HIPAA, medical coding standards, and data quality requirements.

## Quick Start

### Start the API Server

```bash
# Development mode
python api.py --debug

# Production mode
python api.py --host 0.0.0.0 --port 8000

# With custom workers
python api.py --workers 8
```

### Base URL
```
http://localhost:8000/api
```

## Authentication

Currently, the API operates without authentication for development. For production deployment, implement appropriate authentication mechanisms.

## Endpoints

### 1. Health Check

**GET** `/api/health`

Check API status and supported standards.

**Response:**
```json
{
  "status": "healthy",
  "version": "0.1.0",
  "timestamp": "2024-01-15T10:30:00Z",
  "standards_supported": ["icd10", "loinc", "cpt", "icd9", "ndc", "fhir", "omop"]
}
```

### 2. Validate JSON Data

**POST** `/api/validate/data`

Validate structured JSON data for medical compliance.

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
- `standards` (array): Medical standards to check (icd10, loinc, cpt, hipaa)

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
      "score": 50
    },
    "icd10": {
      "compliant": true,
      "issues": [],
      "score": 100
    }
  },
  "issues": [
    {
      "severity": "error",
      "description": "SSN detected in column: ssn",
      "column": "ssn",
      "row": null,
      "value": null,
      "rule_name": "PHIDetector"
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

**POST** `/api/validate/file`

Upload and validate medical data files (CSV, Excel, JSON, Parquet).

**Form Data:**
- `file`: The file to validate
- `detect_phi`: Enable PHI detection (true/false)
- `quality_checks`: Enable quality checks (true/false)
- `profile`: Validation profile
- `standards`: Array of standards to check

**Supported Formats:**
- CSV (.csv)
- Excel (.xlsx, .xls)
- JSON (.json)
- Parquet (.parquet)

**File Size Limit:** 16MB

### 4. Compliance Check

**POST** `/api/compliance/check`

Quick compliance assessment for medical standards.

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
  "icd10_compliant": true,
  "loinc_compliant": false,
  "cpt_compliant": true,
  "fhir_compliant": true,
  "omop_compliant": true,
  "details": {
    "hipaa": {
      "compliant": true,
      "issues": [],
      "score": 100
    }
  }
}
```

### 5. Get Available Profiles

**GET** `/api/profiles`

Retrieve available validation profiles.

**Response:**
```json
{
  "clinical_trials": "Clinical trial data validation",
  "ehr": "Electronic health records validation",
  "imaging": "Medical imaging metadata validation",
  "lab": "Laboratory data validation"
}
```

### 6. Get Standards Information

**GET** `/api/standards`

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
    "description": "Standard for identifying medical laboratory observations"
  }
}
```

## Error Handling

### Standard Error Response

```json
{
  "success": false,
  "error": "Error description",
  "error_type": "ErrorType",
  "traceback": "Full error traceback (in debug mode)"
}
```

### Common HTTP Status Codes

- **200**: Success
- **400**: Bad Request (invalid data, file type not allowed)
- **413**: Payload Too Large (file too big)
- **500**: Internal Server Error

## Rate Limiting

- **Default**: 100 requests per minute per IP
- **File uploads**: 10 requests per minute per IP
- **Burst**: Up to 20 requests in 10 seconds

## Security Features

- **File type validation**: Only allows safe file formats
- **File size limits**: Prevents DoS attacks
- **Input sanitization**: Validates all input data
- **PHI detection**: Automatically identifies sensitive data
- **CORS support**: Configurable cross-origin requests

## Integration Examples

### Python Client

```python
import requests
import json

# Validate JSON data
data = {
    "patient_id": ["001", "002"],
    "age": [30, 45],
    "diagnosis": ["E11.9", "I10"]
}

response = requests.post(
    "http://localhost:8000/api/validate/data",
    json=data,
    params={"detect_phi": "true", "quality_checks": "true"}
)

result = response.json()
print(f"Valid: {result['is_valid']}")
print(f"Issues: {result['total_issues']}")
```

### cURL Example

```bash
# Validate data
curl -X POST "http://localhost:8000/api/validate/data" \
  -H "Content-Type: application/json" \
  -d '{
    "patient_id": ["001", "002"],
    "age": [30, 45],
    "diagnosis": ["E11.9", "I10"]
  }'

# Upload file
curl -X POST "http://localhost:8000/api/validate/file" \
  -F "file=@medical_data.csv" \
  -F "detect_phi=true" \
  -F "quality_checks=true"
```

### JavaScript/Node.js

```javascript
const axios = require('axios');

// Validate data
const validateData = async (data) => {
  try {
    const response = await axios.post('http://localhost:8000/api/validate/data', data, {
      params: {
        detect_phi: true,
        quality_checks: true
      }
    });
    return response.data;
  } catch (error) {
    console.error('Validation failed:', error.response.data);
  }
};

// Usage
const medicalData = {
  patient_id: ["001", "002"],
  age: [30, 45],
  diagnosis: ["E11.9", "I10"]
};

validateData(medicalData).then(result => {
  console.log('Validation result:', result);
});
```

## Production Deployment

### Docker

```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .
EXPOSE 8000

CMD ["python", "api.py", "--host", "0.0.0.0", "--port", "8000"]
```

### Environment Variables

```bash
# API Configuration
API_HOST=0.0.0.0
API_PORT=8000
API_WORKERS=4
API_DEBUG=false

# Security
SECRET_KEY=your-secret-key
ALLOWED_ORIGINS=http://localhost:3000,https://yourdomain.com

# Logging
LOG_LEVEL=INFO
LOG_FILE=api.log
```

### Load Balancer Configuration

```nginx
upstream medical_validator {
    server 127.0.0.1:8000;
    server 127.0.0.1:8001;
    server 127.0.0.1:8002;
    server 127.0.0.1:8003;
}

server {
    listen 80;
    server_name api.medical-validator.com;

    location / {
        proxy_pass http://medical_validator;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

## Monitoring and Logging

### Health Checks

```bash
# Check API health
curl http://localhost:8000/api/health

# Monitor response time
curl -w "@curl-format.txt" http://localhost:8000/api/health
```

### Log Analysis

```bash
# View API logs
tail -f api.log

# Search for errors
grep "ERROR" api.log

# Monitor request patterns
grep "POST /api/validate" api.log | wc -l
```

## Support

For API support and questions:
- **Documentation**: [GitHub Wiki](https://github.com/RanaEhtashamAli/medical-data-validator/wiki)
- **Issues**: [GitHub Issues](https://github.com/RanaEhtashamAli/medical-data-validator/issues)
- **Email**: ranaehtashamali1@gmail.com

## Version History

- **v0.1.0**: Initial release with basic validation endpoints
- **v0.2.0**: Added compliance checking and file upload support
- **v0.3.0**: Enhanced security and performance optimizations 