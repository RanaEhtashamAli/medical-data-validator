# Medical Data Validator - API cURL Examples

## Quick Reference

### Base URL
```bash
API_URL="http://localhost:8000/api"
```

## Essential Endpoints

### 1. Health Check
```bash
curl -X GET "http://localhost:8000/api/health"
```

### 2. Get Available Profiles
```bash
curl -X GET "http://localhost:8000/api/profiles"
```

### 3. Get Standards Information
```bash
curl -X GET "http://localhost:8000/api/standards"
```

## Data Validation

### 4. Validate JSON Data (Basic)
```bash
curl -X POST "http://localhost:8000/api/validate/data" \
  -H "Content-Type: application/json" \
  -d '{
    "patient_id": ["P001", "P002"],
    "age": [30, 45],
    "diagnosis": ["E11.9", "I10"]
  }'
```

### 5. Validate JSON Data (with PHI Detection)
```bash
curl -X POST "http://localhost:8000/api/validate/data?detect_phi=true" \
  -H "Content-Type: application/json" \
  -d '{
    "patient_id": ["P001", "P002"],
    "age": [30, 45],
    "diagnosis": ["E11.9", "I10"],
    "ssn": ["123-45-6789", "987-65-4321"]
  }'
```

### 6. Validate with Specific Standards
```bash
curl -X POST "http://localhost:8000/api/validate/data?standards=icd10,loinc,hipaa" \
  -H "Content-Type: application/json" \
  -d '{
    "patient_id": ["P001"],
    "diagnosis": ["E11.9"],
    "lab_code": ["58410-2"]
  }'
```

### 7. Validate with Profile
```bash
curl -X POST "http://localhost:8000/api/validate/data?profile=clinical_trials" \
  -H "Content-Type: application/json" \
  -d '{
    "subject_id": ["SUBJ001"],
    "age": [30],
    "treatment": ["Placebo"]
  }'
```

## File Upload

### 8. Upload CSV File
```bash
curl -X POST "http://localhost:8000/api/validate/file" \
  -F "file=@your_data.csv" \
  -F "detect_phi=true" \
  -F "quality_checks=true"
```

### 9. Upload with Profile
```bash
curl -X POST "http://localhost:8000/api/validate/file" \
  -F "file=@your_data.csv" \
  -F "profile=ehr" \
  -F "standards=icd10,loinc"
```

## Compliance Checking

### 10. Quick Compliance Check
```bash
curl -X POST "http://localhost:8000/api/compliance/check" \
  -H "Content-Type: application/json" \
  -d '{
    "patient_id": ["P001", "P002"],
    "diagnosis": ["E11.9", "I10"],
    "procedure": ["99213", "93010"]
  }'
```

## Advanced Examples

### 11. Validate Large Dataset
```bash
curl -X POST "http://localhost:8000/api/validate/data" \
  -H "Content-Type: application/json" \
  -d '{
    "patient_id": ["P001", "P002", "P003", "P004", "P005"],
    "age": [30, 45, 28, 52, 35],
    "diagnosis": ["E11.9", "I10", "Z51.11", "E78.5", "J45.909"],
    "procedure": ["99213", "93010", "80048", "85025", "71046"],
    "lab_code": ["58410-2", "789-8", "718-7", "787-2", "785-6"]
  }'
```

### 12. Validate with All Options
```bash
curl -X POST "http://localhost:8000/api/validate/data?detect_phi=true&quality_checks=true&profile=ehr&standards=icd10,loinc,cpt,hipaa" \
  -H "Content-Type: application/json" \
  -d '{
    "patient_id": ["P001"],
    "age": [30],
    "diagnosis": ["E11.9"],
    "procedure": ["99213"],
    "lab_code": ["58410-2"]
  }'
```

### 13. Upload Multiple File Types
```bash
# CSV
curl -X POST "http://localhost:8000/api/validate/file" \
  -F "file=@data.csv" \
  -F "detect_phi=true"

# Excel
curl -X POST "http://localhost:8000/api/validate/file" \
  -F "file=@data.xlsx" \
  -F "quality_checks=true"

# JSON
curl -X POST "http://localhost:8000/api/validate/file" \
  -F "file=@data.json" \
  -F "profile=clinical_trials"
```

## Error Testing

### 14. Test Invalid JSON
```bash
curl -X POST "http://localhost:8000/api/validate/data" \
  -H "Content-Type: application/json" \
  -d '{invalid json}'
```

### 15. Test Missing File
```bash
curl -X POST "http://localhost:8000/api/validate/file"
```

### 16. Test Unsupported File Type
```bash
curl -X POST "http://localhost:8000/api/validate/file" \
  -F "file=@document.txt"
```

## Response Examples

### Successful Validation Response
```json
{
  "success": true,
  "is_valid": false,
  "total_issues": 2,
  "error_count": 1,
  "warning_count": 1,
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
    "total_issues": 2
  }
}
```

### Health Check Response
```json
{
  "status": "healthy",
  "version": "0.1.0",
  "timestamp": "2024-01-15T10:30:00Z",
  "standards_supported": ["icd10", "loinc", "cpt", "icd9", "ndc", "fhir", "omop"]
}
```

## Testing Scripts

### Run Complete Test Suite

**Linux/Mac:**
```bash
chmod +x test_api.sh
./test_api.sh
```

**Windows:**
```cmd
test_api.bat
```

### Individual Test Commands

```bash
# Test health endpoint
curl -X GET "http://localhost:8000/api/health" | jq '.'

# Test data validation with pretty output
curl -X POST "http://localhost:8000/api/validate/data" \
  -H "Content-Type: application/json" \
  -d '{"patient_id": ["P001"], "age": [30], "diagnosis": ["E11.9"]}' | jq '.'

# Test file upload with progress
curl -X POST "http://localhost:8000/api/validate/file" \
  -F "file=@your_file.csv" \
  -F "detect_phi=true" \
  --progress-bar
```

## Tips

1. **Use `jq` for pretty JSON output**: `curl ... | jq '.'`
2. **Add `-v` flag for verbose output**: `curl -v ...`
3. **Use `-s` flag for silent mode**: `curl -s ...`
4. **Save response to file**: `curl ... > response.json`
5. **Test with real medical data**: Use the provided sample datasets

## Common Issues

- **Connection refused**: Make sure API server is running
- **File not found**: Check file path and permissions
- **Invalid JSON**: Validate JSON syntax before sending
- **Large files**: Use appropriate timeout settings

---

**Note**: Replace `localhost:8000` with your actual server address if running remotely. 