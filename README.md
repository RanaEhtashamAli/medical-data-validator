# Medical Data Validator

[![CI/CD](https://github.com/RanaEhtashamAli/medical-data-validator/workflows/Medical%20Data%20Validator%20CI%2FCD/badge.svg)](https://github.com/RanaEhtashamAli/medical-data-validator/actions)
[![Code Coverage](https://codecov.io/gh/RanaEhtashamAli/medical-data-validator/branch/main/graph/badge.svg)](https://codecov.io/gh/RanaEhtashamAli/medical-data-validator)
[![PyPI Version](https://badge.fury.io/py/medical-data-validator.svg)](https://pypi.org/project/medical-data-validator/)
[![Python Versions](https://img.shields.io/pypi/pyversions/medical-data-validator.svg)](https://pypi.org/project/medical-data-validator/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![HIPAA Compliant](https://img.shields.io/badge/HIPAA-Compliant-green.svg)](https://www.hhs.gov/hipaa/index.html)
[![Medical Standards](https://img.shields.io/badge/Standards-ICD10%2CLOINC%2CCPT-blue.svg)](https://www.cdc.gov/nchs/icd/icd10cm.htm)

## 🎯 Value Proposition

**Validates critical healthcare datasets for format, integrity, and compliance with U.S. medical data standards.**

For researchers, startups, and hospitals who need to validate large CSV/JSON medical data before ingestion into EHR systems, research databases, or clinical trial platforms.

## 🏥 How It Works

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Medical Data  │───▶│  Validation      │───▶│  Compliance     │
│   (CSV/JSON)    │    │  Engine          │    │  Report         │
└─────────────────┘    └──────────────────┘    └─────────────────┘
         │                       │                       │
         ▼                       ▼                       ▼
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│  PHI Detection  │    │  Medical Codes   │    │  HIPAA Status   │
│  (SSN, Email)   │    │  (ICD-10, LOINC) │    │  (Compliant)    │
└─────────────────┘    └──────────────────┘    └─────────────────┘
```

## 🚀 Enterprise-Ready Features

A comprehensive Python library for validating healthcare datasets with support for PHI/PII detection, schema validation, and medical-specific data quality checks. **HIPAA-compliant** and aligned with **US medical standards** (ICD-10, LOINC, CPT). Features both a command-line interface and an interactive web dashboard for easy data validation.

### 🔒 **Security & Compliance**
- **HIPAA Compliant**: Built-in PHI detection and anonymization
- **Zero Data Retention**: All data processed in memory, never stored
- **Enterprise Security**: TLS 1.3, AES-256 encryption, audit trails
- **Medical Standards**: Full support for ICD-10, LOINC, CPT, FHIR

### 🏥 **Medical-Specific Validation**
- **PHI/PII Detection**: Automatic identification of sensitive health information
- **Medical Code Validation**: ICD-10, LOINC, CPT code verification
- **Data Quality Checks**: Missing values, duplicates, outliers, range validation
- **Schema Validation**: Required columns, data types, and format validation

### 🚀 **Multiple Interfaces**
- **REST API**: Enterprise-ready API for system integration
- **Web Dashboard**: Interactive UI with drag-and-drop file upload
- **Command Line**: Batch processing and automation
- **Python Library**: Direct integration into your applications

### 📊 **Comprehensive Reporting**
- **Compliance Reports**: Detailed HIPAA and standards compliance
- **Issue Tracking**: Categorized by severity (Error, Warning, Info)
- **Export Options**: PDF, CSV, JSON reports
- **Real-time Validation**: Live progress tracking and results

## 🖥️ UI Preview

### Web Dashboard
![Dashboard](docs/screenshots/dashboard-home.png)

**Modern, intuitive interface for healthcare professionals:**
- **Drag-and-drop file upload** with instant validation
- **Real-time progress tracking** with visual feedback
- **Interactive compliance reports** with actionable insights
- **Mobile-responsive design** for on-the-go validation

### Validation Results
![Results](docs/screenshots/validation-results.png)

**Comprehensive validation reporting:**
- **Compliance scoring** with visual indicators
- **Issue categorization** by severity (Error, Warning, Info)
- **Medical standards compliance** breakdown
- **Export options** in multiple formats

### API Documentation
![API Docs](docs/screenshots/api-docs.png)

**Interactive API documentation:**
- **Live endpoint testing** directly from the browser
- **Request/response examples** for all endpoints
- **Authentication guides** and integration examples
- **Rate limit monitoring** and usage tracking

**[📖 Full UI Documentation](docs/UI_PREVIEW.md)** - Complete interface guide with all screens

## 🚀 Features

- **Schema Validation**: Required columns, data types, and format validation
- **PHI/PII Detection**: Automatic identification of sensitive health information
- **Data Quality Checks**: Missing values, duplicates, outliers, and range validation
- **Medical-Specific Validations**: ICD-10, LOINC, CPT code validation
- **Date Validation**: Date format and range checking
- **Custom Rules**: Extensible validation framework
- **Comprehensive Reporting**: Detailed validation reports with severity levels
- **Interactive Web Dashboard**: Upload and validate data with visualizations
- **Command-Line Interface**: Batch processing and automation
- **Performance Optimization**: Caching and batch processing for large datasets
- **HIPAA Compliance**: Built-in PHI detection and anonymization tools
- **Security Features**: File validation, sanitization, and audit trails
- **REST API**: Enterprise-ready API for integration
- **Medical Standards Compliance**: Full support for US healthcare standards



## 🚀 Quick Deployment

### Docker (Recommended)
```bash
# Start all services
docker-compose up -d

# Access the application
# - API: http://localhost:8000
# - Dashboard: http://localhost:5000

# Development mode with hot reload
docker-compose --profile dev up -d

# Production with load balancer
docker-compose --profile production up -d
```

### Direct Installation
```bash
# Clone the repository
git clone https://github.com/RanaEhtashamAli/medical-data-validator.git
cd medical-data-validator

# Install dependencies
pip install -r requirements.txt
pip install -r requirements-api.txt

# Start the API server
python api.py --host 0.0.0.0 --port 8000
```

## 📦 Installation

The Medical Data Validator supports modular installation. Choose what you need:

```bash
# Core only (Python API)
pip install medical-data-validator

# Add CLI interface
pip install medical-data-validator[cli]

# Add web dashboard
pip install medical-data-validator[web]

# Add REST API
pip install medical-data-validator[api]

# Add all web interfaces (dashboard + API)
pip install medical-data-validator[web-all]

# Install everything (core + CLI + web + API)
pip install medical-data-validator[all]

# Development setup
pip install medical-data-validator[dev]
```

**📋 [Complete Installation Guide](INSTALLATION.md)** - Detailed options and troubleshooting

## 🚀 Quick Start

### Using the Unified CLI

The Medical Data Validator provides a single, comprehensive command-line interface:

```bash
# Validate medical data files
python medical_data_validator_cli.py validate data.csv --detect-phi

# Launch web dashboard
python medical_data_validator_cli.py dashboard

# Run performance benchmarks
python medical_data_validator_cli.py benchmark

# Check compliance with medical standards
python medical_data_validator_cli.py compliance data.csv --standards icd10,loinc,hipaa

# Launch REST API server
python medical_data_validator_cli.py api

# Run demonstration
python medical_data_validator_cli.py demo
```

### Using the Web Dashboard

1. **Start the dashboard**:
   ```bash
   # Using the launcher script (recommended)
   python launch_dashboard.py
   
   # Or using the CLI
   python medical_data_validator_cli.py dashboard
   ```

2. **Open your browser** and go to: http://localhost:5000

3. **Upload your medical dataset** and get instant validation results with interactive visualizations.

### Using the Command Line

```bash
# Validate a CSV file
medical-validator validate data.csv --output json

# Validate with specific options
medical-validator validate data.csv \
    --detect-phi \
    --quality-checks \
    --profile clinical_trials \
    --output summary
```

### Using the REST API

The Medical Data Validator provides a comprehensive REST API for enterprise integration:

```bash
# Start the API server (recommended)
python launch_api.py --host 0.0.0.0 --port 8000

# Or using the standalone API server
python api.py --host 0.0.0.0 --port 8000

# Or use the CLI
python medical_data_validator_cli.py api

# API endpoints available at:
# - http://localhost:8000/api/health (Health check)
# - http://localhost:8000/api/validate/file (File validation)
# - http://localhost:8000/api/validate/data (JSON data validation)
# - http://localhost:8000/api/compliance/check (Compliance checking)
# - http://localhost:8000/api/profiles (Available profiles)
# - http://localhost:8000/api/standards (Supported standards)
```

**[📚 Complete API Documentation](API_DOCUMENTATION.md)** - Full endpoint reference with examples

Example API usage:
```python
import requests

# Validate uploaded file
with open('medical_data.csv', 'rb') as f:
    response = requests.post(
        'http://localhost:8000/validate/file',
        files={'file': f},
        params={'detect_phi': True, 'quality_checks': True}
    )
    result = response.json()

# Validate JSON data
data = {"patient_id": ["P001"], "age": [30], "diagnosis": ["Diabetes"]}
response = requests.post(
    'http://localhost:8000/validate/data',
    json=data,
    params={'standards': ['icd10', 'loinc', 'hipaa']}
)
result = response.json()
```

### Using Python API

```python
import pandas as pd
from medical_data_validator import MedicalDataValidator, SchemaValidator, PHIDetector

# Sample medical data
data = {
    "patient_id": ["P001", "P002", "P003"],
    "name": ["John Doe", "Jane Smith", "Bob Johnson"],
    "ssn": ["123-45-6789", "987-65-4321", "555-12-3456"],
    "age": [30, 40, 25],
    "diagnosis": ["Diabetes", "Hypertension", "Asthma"],
    "icd10_code": ["E11.9", "I10", "J45.909"]
}

# Create validator with rules
validator = MedicalDataValidator([
    SchemaValidator(
        required_columns=["patient_id", "age"],
        column_types={"age": "int", "diagnosis": "string"}
    ),
    PHIDetector()
])

# Validate the data
result = validator.validate(data)

# Check if valid
print(f"Data is valid: {result.is_valid}")

# Get detailed report
print(validator.get_report(result))

# Access specific issues
for issue in result.get_issues_by_severity("error"):
    print(f"Error: {issue.message}")
```

## 🔒 Security & Privacy

### HIPAA Compliance
- **Zero Data Retention**: All files processed in memory, never stored
- **PHI Detection**: Automatic identification of sensitive health information
- **Data Anonymization**: Built-in tools for data masking and pseudonymization
- **Audit Trails**: Comprehensive logging for compliance reporting

### Enterprise Security
- **TLS 1.3 Encryption**: All communications encrypted with latest standards
- **File Validation**: Malware scanning and format verification
- **Rate Limiting**: DDoS protection and request throttling
- **Input Sanitization**: Protection against injection attacks

**[🔐 Complete Security Documentation](SECURITY.md)** - Detailed security practices and compliance

## 🏥 Medical Standards Compliance

This validator is designed to meet **US healthcare data standards** and regulatory requirements:

### Supported Standards

- **ICD-10-CM**: International Classification of Diseases, 10th Revision (CMS/CDC)
- **LOINC**: Logical Observation Identifiers Names and Codes (Regenstrief Institute)
- **CPT**: Current Procedural Terminology (AMA)
- **HIPAA**: Health Insurance Portability and Accountability Act compliance
- **FHIR**: Fast Healthcare Interoperability Resources (HL7)
- **OMOP CDM**: Observational Medical Outcomes Partnership Common Data Model

### Compliance Features

```python
from medical_data_validator import MedicalDataValidator, HIPAAComplianceChecker

# Check HIPAA compliance
hipaa_checker = HIPAAComplianceChecker()
compliance_report = hipaa_checker.check_hipaa_compliance(data)

# Validate against medical standards
validator = MedicalDataValidator([
    MedicalCodeValidator({
        "diagnosis_code": "icd10",    # E11.9, I10, J45.909
        "test_code": "loinc",         # 58410-2, 789-8
        "procedure_code": "cpt"       # 99213, 93010
    })
])
```

### Security & Privacy

- **PHI/PII Detection**: Automatic identification of 18 categories of protected health information
- **Data Anonymization**: HIPAA Safe Harbor method implementation
- **File Security**: Size limits, type validation, and sanitization
- **Audit Trails**: Comprehensive logging and compliance reporting

For detailed compliance information, see [MEDICAL_STANDARDS_COMPLIANCE.md](MEDICAL_STANDARDS_COMPLIANCE.md).

## 🔧 Core Components

The main class that orchestrates validation:

```python
from medical_data_validator import MedicalDataValidator

validator = MedicalDataValidator()
result = validator.validate(your_data)
```

### Validation Rules

#### SchemaValidator

Validates data structure and types:

```python
from medical_data_validator import SchemaValidator

schema_rule = SchemaValidator(
    required_columns=["patient_id", "age", "diagnosis"],
    column_types={
        "patient_id": "string",
        "age": "int",
        "diagnosis": "string",
        "temperature": "float"
    }
)
```

#### PHIDetector

Detects potential PHI/PII in data:

```python
from medical_data_validator import PHIDetector

phi_rule = PHIDetector()
# Automatically detects SSN, email, phone, dates, etc.
```

#### DataQualityChecker

Performs general data quality checks:

```python
from medical_data_validator import DataQualityChecker

quality_rule = DataQualityChecker()
# Checks for missing values, duplicates, empty columns
```

#### MedicalCodeValidator

Validates medical codes:

```python
from medical_data_validator import MedicalCodeValidator

code_rule = MedicalCodeValidator({
    "icd10_code": "icd10",
    "loinc_code": "loinc",
    "cpt_code": "cpt"
})
```

#### RangeValidator

Validates numeric ranges:

```python
from medical_data_validator import RangeValidator

range_rule = RangeValidator({
    "age": {"min": 0, "max": 120},
    "temperature": {"min": 95.0, "max": 105.0},
    "blood_pressure_systolic": {"min": 70, "max": 200}
})
```

#### DateValidator

Validates date fields:

```python
from medical_data_validator import DateValidator

date_rule = DateValidator(
    date_columns=["birth_date", "admission_date"],
    min_date="1900-01-01",
    max_date="2024-12-31"
)
```

## ⚙️ Advanced Usage

### Custom Validation Rules

```python
from medical_data_validator import ValidationRule, ValidationIssue

class CustomRule(ValidationRule):
    def validate(self, data):
        issues = []
        # Your custom validation logic
        if "custom_column" in data.columns:
            # Check something specific
            pass
        return issues

# Use custom rule
validator = MedicalDataValidator([CustomRule()])
```

### Custom Validators

```python
def custom_validator(df):
    issues = []
    # Your validation logic
    return issues

validator = MedicalDataValidator()
validator.add_validator("my_custom_check", custom_validator)
```

### Working with Results

```python
result = validator.validate(data)

# Check overall validity
if result.is_valid:
    print("✅ Data passed validation")
else:
    print("❌ Data has validation issues")

# Get issues by severity
errors = result.get_issues_by_severity("error")
warnings = result.get_issues_by_severity("warning")
info = result.get_issues_by_severity("info")

# Get issues by column
column_issues = result.get_issues_by_column("patient_id")

# Convert to dictionary
result_dict = result.to_dict()

# Generate human-readable report
report = validator.get_report(result)
print(report)
```

## 💡 Real-World Example

```python
import pandas as pd
from medical_data_validator import (
    MedicalDataValidator,
    SchemaValidator,
    PHIDetector,
    DataQualityChecker,
    MedicalCodeValidator,
    RangeValidator,
    DateValidator
)

# Load your medical data
df = pd.read_csv("patient_data.csv")

# Configure comprehensive validation
validator = MedicalDataValidator([
    # Schema validation
    SchemaValidator(
        required_columns=["patient_id", "age", "diagnosis"],
        column_types={
            "patient_id": "string",
            "age": "int",
            "diagnosis": "string",
            "temperature": "float"
        }
    ),
    
    # PHI detection
    PHIDetector(),
    
    # Data quality
    DataQualityChecker(),
    
    # Medical codes
    MedicalCodeValidator({
        "icd10_code": "icd10",
        "loinc_code": "loinc"
    }),
    
    # Value ranges
    RangeValidator({
        "age": {"min": 0, "max": 120},
        "temperature": {"min": 95.0, "max": 105.0}
    }),
    
    # Dates
    DateValidator(
        date_columns=["birth_date", "admission_date"],
        min_date="1900-01-01"
    )
])

# Validate
result = validator.validate(df)

# Handle results
if result.is_valid:
    print("✅ Data is ready for analysis")
else:
    print("❌ Data needs cleaning:")
    for issue in result.issues:
        print(f"  - {issue.severity.upper()}: {issue.message}")
    
    # Generate detailed report
    with open("validation_report.txt", "w") as f:
        f.write(validator.get_report(result))
```

## 🏥 Supported Medical Codes

- **ICD-10**: `A00.0` to `Z99.9`
- **ICD-9**: `001.0` to `999.9`
- **LOINC**: `12345-6` format
- **CPT**: `1234A` format
- **NDC**: `1234-5678-90` format

## 🔒 PHI/PII Detection

Automatically detects:
- Social Security Numbers (SSN)
- Email addresses
- Phone numbers
- Dates (birth dates, etc.)
- ZIP codes
- Column names containing PHI keywords

## 🌐 Web Dashboard

The Medical Data Validator includes an interactive web dashboard for easy data validation:

### Features
- **Drag & Drop Upload**: Easy file upload with support for CSV, Excel, JSON, and Parquet files
- **Interactive Visualizations**: Charts showing data quality issues, missing values, and validation results
- **Real-time Validation**: Instant feedback on data quality
- **Export Results**: Download validation reports in multiple formats
- **Professional Interface**: Modern, responsive design

### Screenshots
- Upload interface with drag-and-drop functionality
- Interactive charts showing validation results
- Detailed issue reporting with severity levels

## 💻 Command Line Interface

Powerful CLI for batch processing and automation:

```bash
# Basic validation
medical-validator validate data.csv

# Advanced validation with options
medical-validator validate data.csv \
    --detect-phi \
    --quality-checks \
    --profile clinical_trials \
    --output json \
    --verbose

# Validate multiple files
medical-validator validate *.csv --output-dir reports/

# Get help
medical-validator --help
```

### CLI Options
- `--detect-phi`: Enable PHI/PII detection
- `--quality-checks`: Enable data quality checks
- `--profile`: Use predefined validation profiles
- `--output`: Output format (json, summary, html)
- `--verbose`: Detailed output

## 🤝 Contributing

We welcome contributions! Please see our [Contributing Guide](CONTRIBUTING.md) for details.

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Submit a pull request

## 🧪 Testing

```bash
# Install development dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Run with coverage
pytest --cov=medical_data_validator

# Run specific test categories
pytest -m "not slow"  # Skip slow tests
pytest tests/test_core.py  # Run specific test file
```

## 📄 License

MIT License - see [LICENSE](LICENSE) file for details.

## 🆘 Support

- **Documentation**: [Read the Docs](https://medical-data-validator.readthedocs.io)
- **Issues**: [GitHub Issues](https://github.com/RanaEhtashamAli/medical-data-validator/issues)
- **Email**: ranaehtashamali1@gmail.com
- **LinkedIn**: [Rana Ehtasham Ali](https://www.linkedin.com/in/ranaehtashamali/)

## 🚀 Deployment

For production deployment instructions, see [DEPLOYMENT.md](DEPLOYMENT.md).

## 📊 Performance

The Medical Data Validator includes performance optimizations:
- **Caching**: Validation results are cached for repeated checks
- **Batch Processing**: Efficient handling of large datasets
- **Memory Optimization**: Smart memory management for large files
- **Parallel Processing**: Multi-threaded validation for faster results

## 🗺️ Roadmap

- [x] ✅ Core validation framework
- [x] ✅ PHI/PII detection
- [x] ✅ Web dashboard
- [x] ✅ Command-line interface
- [x] ✅ Performance optimizations
- [ ] FHIR resource validation
- [ ] DICOM metadata validation
- [ ] OMOP CDM compliance checking
- [ ] Real-time validation API
- [ ] Integration with popular healthcare frameworks
- [ ] Machine learning-based anomaly detection
- [ ] Cloud deployment (AWS, Azure, GCP)
- [ ] Mobile app for field validation

---

**Developed by [Rana Ehtasham Ali](https://www.linkedin.com/in/ranaehtashamali/) - Senior Software Engineer**

For questions and support: ranaehtashamali1@gmail.com 