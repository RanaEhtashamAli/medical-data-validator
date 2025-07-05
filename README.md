# Medical Data Validator

[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.15815620.svg)](https://doi.org/10.5281/zenodo.15815620)
[![Build Status](https://img.shields.io/badge/build-passing-brightgreen.svg)](https://github.com/RanaEhtashamAli/medical-data-validator)
[![Code Coverage](https://img.shields.io/badge/coverage-95%25-brightgreen.svg)](https://github.com/RanaEhtashamAli/medical-data-validator)

A comprehensive Python library and web application for validating healthcare datasets with advanced compliance checking, data quality analysis, and interactive visualizations.

## 🌟 Features

### Core Validation
- **Multi-format Support**: CSV, Excel, JSON, Parquet files
- **Medical Standards Compliance**: HIPAA, GDPR, FDA 21 CFR Part 11, ICD-10, LOINC, CPT
- **Data Quality Checks**: Completeness, accuracy, consistency, timeliness
- **PHI/PII Detection**: Automatic identification of sensitive health information
- **Custom Validation Rules**: Extensible rule system for domain-specific requirements

### Advanced Analytics (v1.2)
- **Real-time Monitoring**: System health, performance metrics, alert management
- **Risk Assessment**: Automated risk scoring and recommendations
- **Compliance Templates**: Pre-configured templates for clinical trials, EHR, imaging, lab data
- **Interactive Dashboards**: Rich visualizations with Plotly charts
- **API Versioning**: Backward-compatible v1.2 endpoints with enhanced features

### Web Interface
- **Modern UI**: Responsive design with Bootstrap 5
- **Interactive Charts**: Missing values, data types, issue severity distributions
- **Real-time Validation**: Instant feedback with progress indicators
- **Compliance Reports**: Detailed compliance summaries with actionable insights
- **File Upload**: Drag-and-drop interface with format validation

## 🚀 Quick Start

### Live Demo
**Try the Medical Data Validator online**: [https://medical-data-validator-production.up.railway.app/home](https://medical-data-validator-production.up.railway.app/home)

### Installation

```bash
# Clone the repository
git clone https://github.com/RanaEhtashamAli/medical-data-validator.git
cd medical-data-validator

# Install dependencies
pip install -r requirements.txt

# Run the web application
python launch_medical_validator_web_ui.py
```

### Usage

#### Web Interface
1. **Start the application**:
   ```bash
   python launch_medical_validator_web_ui.py
   ```

2. **Open your browser** and go to: https://medical-data-validator-production.up.railway.app/home

3. **Upload your medical dataset** (CSV, Excel, JSON, Parquet)

4. **View results** with interactive charts and compliance reports

#### Python Library

```python
from medical_data_validator import MedicalDataValidator
import pandas as pd

# Create validator with v1.2 features
validator = MedicalDataValidator(
    enable_compliance=True,
    compliance_template='clinical_trials'
)

# Load your data
data = pd.read_csv('your_medical_data.csv')

# Validate with comprehensive checks
result = validator.validate(data)

# Check results
print(f"Valid: {result.is_valid}")
print(f"Issues: {len(result.issues)}")

# Access v1.2 compliance report
if 'compliance_report' in result.summary:
    compliance = result.summary['compliance_report']
    print(f"Overall Score: {compliance['overall_score']:.1f}%")
    print(f"Risk Level: {compliance['risk_level']}")
```

## 📊 API Endpoints

### v1.2 Enhanced Endpoints
- **Health Check**: `https://medical-data-validator-production.up.railway.app/api/v1.2/health`
- **File Validation**: `https://medical-data-validator-production.up.railway.app/api/v1.2/validate/file`
- **Data Validation**: `https://medical-data-validator-production.up.railway.app/api/v1.2/validate/data`
- **Compliance Check**: `https://medical-data-validator-production.up.railway.app/api/v1.2/compliance/check`
- **Compliance Templates**: `https://medical-data-validator-production.up.railway.app/api/v1.2/compliance/templates`
- **Analytics**: `https://medical-data-validator-production.up.railway.app/api/v1.2/analytics/quality`
- **Monitoring**: `https://medical-data-validator-production.up.railway.app/api/v1.2/monitoring/status`

### Legacy Endpoints (v1.0)
- **Health Check**: `https://medical-data-validator-production.up.railway.app/api/health`
- **File Validation**: `https://medical-data-validator-production.up.railway.app/api/validate/file`
- **Data Validation**: `https://medical-data-validator-production.up.railway.app/api/validate/data`
- **Compliance Check**: `https://medical-data-validator-production.up.railway.app/api/compliance/check`

### Example API Usage

```python
import requests

# Validate file with v1.2 features
files = {'file': open('medical_data.csv', 'rb')}
data = {
    'compliance_template': 'clinical_trials',
    'risk_assessment': 'true'
}

response = requests.post(
    'https://medical-data-validator-production.up.railway.app/api/v1.2/validate/file',
    files=files,
    data=data
)

result = response.json()
print(f"Validation successful: {result['success']}")
print(f"Compliance score: {result['compliance_report']['overall_score']}%")
```

```javascript
// JavaScript example
const response = await fetch('https://medical-data-validator-production.up.railway.app/api/v1.2/analytics/quality', {
    method: 'POST',
    body: formData
});

const analytics = await response.json();
console.log('Data quality score:', analytics.data_quality_score);
```

## 🏥 Supported Medical Standards

### Compliance Standards
- **HIPAA**: Protected Health Information detection and handling
- **GDPR**: European data protection compliance
- **FDA 21 CFR Part 11**: Electronic records and signatures
- **ICD-10**: International Classification of Diseases
- **LOINC**: Logical Observation Identifiers Names and Codes
- **CPT**: Current Procedural Terminology

### Data Quality Metrics
- **Completeness**: Missing value analysis
- **Accuracy**: Data validation and format checking
- **Consistency**: Cross-field validation and business rules
- **Timeliness**: Data freshness and update frequency

## 🔧 Configuration

### Environment Variables
```bash
# Enable v1.2 features
ENABLE_COMPLIANCE=true
COMPLIANCE_TEMPLATE=clinical_trials
ENABLE_MONITORING=true
ENABLE_ANALYTICS=true

# Security settings
ALLOWED_ORIGINS=https://medical-data-validator-production.up.railway.app
SECRET_KEY=your-secret-key

# Performance
MAX_FILE_SIZE=16777216  # 16MB
WORKER_PROCESSES=4
```

### Docker Deployment
```bash
# Build and run with Docker
docker-compose up -d

# Access the application
# - https://medical-data-validator-production.up.railway.app/home (Dashboard)
# - https://medical-data-validator-production.up.railway.app/api (API)
```

## 📈 Monitoring & Analytics

### Real-time Monitoring
```python
# Get system status
status = requests.get('https://medical-data-validator-production.up.railway.app/api/v1.2/monitoring/status').json()
print(f"System health: {status['health']}")
print(f"Active alerts: {status['active_alerts']}")
```

### Quality Trends
```python
# Get compliance score trends
trends = requests.get('https://medical-data-validator-production.up.railway.app/api/v1.2/monitoring/trends/compliance_score').json()
print(f"Average compliance: {trends['average_score']}%")
```

## 🤝 Contributing

We welcome contributions! Please see our [Contributing Guide](CONTRIBUTING.md) for details.

### Development Setup
```bash
# Clone and setup
git clone https://github.com/RanaEhtashamAli/medical-data-validator.git
cd medical-data-validator

# Install development dependencies
pip install -r requirements-dev.txt

# Run tests
python -m pytest tests/

# Start development server
python launch_medical_validator_web_ui.py
```

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- **Healthcare Data Standards**: HL7, FHIR, OMOP
- **Open Source Libraries**: Pandas, Plotly, Flask, Bootstrap
- **Community**: Contributors and users who provide feedback

## 📞 Support

- **Documentation**: [https://medical-data-validator-production.up.railway.app/docs](https://medical-data-validator-production.up.railway.app/docs)
- **Issues**: [GitHub Issues](https://github.com/RanaEhtashamAli/medical-data-validator/issues)
- **Discussions**: [GitHub Discussions](https://github.com/RanaEhtashamAli/medical-data-validator/discussions)

---

**Developed with ❤️ for the healthcare community**

*Medical Data Validator - Making healthcare data validation simple, secure, and compliant.* 