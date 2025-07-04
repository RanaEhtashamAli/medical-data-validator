# Medical Data Validator Installation Guide

## Overview

This guide provides step-by-step instructions for installing and setting up the Medical Data Validator v1.2 with all advanced features including compliance validation, analytics, and monitoring.

## 🚀 Quick Start

### Live Demo
**Try the Medical Data Validator online**: [https://medical-data-validator-production.up.railway.app/home](https://medical-data-validator-production.up.railway.app/home)

### Prerequisites

- **Python**: 3.8 or higher
- **pip**: Latest version
- **Git**: For cloning the repository
- **Docker**: (Optional) For containerized deployment

### System Requirements

- **RAM**: Minimum 2GB, Recommended 4GB+
- **Storage**: 1GB free space
- **Network**: Internet connection for package installation

## 📦 Installation Methods

### Method 1: Direct Installation (Recommended)

```bash
# Clone the repository
git clone https://github.com/RanaEhtashamAli/medical-data-validator.git
cd medical-data-validator

# Create virtual environment
python -m venv venv

# Activate virtual environment
# On Windows:
venv\Scripts\activate
# On macOS/Linux:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Install the package in development mode
pip install -e .
```

### Method 2: Docker Installation

```bash
# Clone the repository
git clone https://github.com/RanaEhtashamAli/medical-data-validator.git
cd medical-data-validator

# Build and run with Docker Compose
docker-compose up -d

# Access the application
# - Dashboard: https://medical-data-validator-production.up.railway.app/home
# - API: https://medical-data-validator-production.up.railway.app/api
```

### Method 3: pip Installation

```bash
# Install from PyPI (when available)
pip install medical-data-validator

# Or install from GitHub
pip install git+https://github.com/RanaEhtashamAli/medical-data-validator.git
```

## ⚙️ Configuration

### Environment Variables

Create a `.env` file in the project root:

```bash
# Application Settings
FLASK_ENV=development
SECRET_KEY=your-secret-key-here
DEBUG=true

# v1.2 Features
ENABLE_COMPLIANCE=true
ENABLE_ANALYTICS=true
ENABLE_MONITORING=true
COMPLIANCE_TEMPLATE=clinical_trials

# Security
ALLOWED_ORIGINS=https://medical-data-validator-production.up.railway.app
CORS_ORIGINS=https://medical-data-validator-production.up.railway.app

# Performance
MAX_FILE_SIZE=16777216  # 16MB
WORKER_PROCESSES=4
TIMEOUT=300

# Optional: Database (if using external database)
DATABASE_URL=sqlite:///medical_validator.db

# Optional: Monitoring
ENABLE_ALERTS=true
ALERT_EMAIL=admin@yourdomain.com
```

### Configuration Files

#### Compliance Templates
Create custom compliance templates in `compliance_templates/`:

```json
{
  "custom_template": {
    "name": "Custom Healthcare Template",
    "description": "Custom validation template for healthcare data",
    "standards": ["hipaa", "gdpr", "icd10"],
    "rules": [
      {
        "name": "phi_detection",
        "pattern": "\\b\\d{3}-\\d{2}-\\d{4}\\b",
        "severity": "high",
        "description": "SSN pattern detected"
      }
    ]
  }
}
```

#### Custom Rules
Add custom validation rules in `custom_rules.json`:

```json
{
  "custom_rules": [
    {
      "name": "age_validation",
      "pattern": "^(?:1[0-9]|[2-9][0-9]|1[0-1][0-9]|120)$",
      "severity": "warning",
      "description": "Age must be between 10 and 120",
      "field_pattern": ".*age.*"
    }
  ]
}
```

## 🚀 Running the Application

### Web Interface

```bash
# Start the web application
python launch_medical_validator_web_ui.py

# Or use the dashboard launcher
python launch_dashboard.py
```

**Access the dashboard**: https://medical-data-validator-production.up.railway.app/home

### API Server

```bash
# Start the API server
python launch_api.py

# Or use the Flask development server
python -m flask run --host=0.0.0.0 --port=8000
```

**API endpoints available at**: https://medical-data-validator-production.up.railway.app/api/v1.2/

### Command Line Interface

```bash
# Basic validation
python medical_data_validator_cli.py validate data.csv

# With compliance checking
python medical_data_validator_cli.py validate data.csv --compliance hipaa,gdpr

# With custom template
python medical_data_validator_cli.py validate data.csv --template clinical_trials

# Get help
python medical_data_validator_cli.py --help
```

## 🧪 Testing the Installation

### Health Check

```bash
# Check API health
curl https://medical-data-validator-production.up.railway.app/api/health

# Check dashboard health
curl https://medical-data-validator-production.up.railway.app/health
```

### Validation Test

```python
from medical_data_validator import MedicalDataValidator
import pandas as pd

# Create test data
test_data = pd.DataFrame({
    'patient_id': ['001', '002', '003'],
    'age': [30, 45, 28],
    'diagnosis': ['E11.9', 'I10', 'Z51.11'],
    'ssn': ['123-45-6789', '987-65-4321', '555-12-3456']
})

# Create validator with v1.2 features
validator = MedicalDataValidator(
    enable_compliance=True,
    compliance_template='clinical_trials'
)

# Validate data
result = validator.validate(test_data)

# Check results
print(f"Valid: {result.is_valid}")
print(f"Total issues: {len(result.issues)}")

# Access v1.2 compliance report
if 'compliance_report' in result.summary:
    compliance = result.summary['compliance_report']
    print(f"Overall Score: {compliance['overall_score']:.1f}%")
    print(f"Risk Level: {compliance['risk_level']}")
```

### API Test

```python
import requests

# Test API endpoint
data = {
    'patient_id': ['001', '002'],
    'diagnosis': ['E11.9', 'I10']
}

response = requests.post(
    'https://medical-data-validator-production.up.railway.app/api/v1.2/validate/data',
    json=data
)

result = response.json()
print(f"API test successful: {result['success']}")
```

## 🔧 Development Setup

### Development Dependencies

```bash
# Install development dependencies
pip install -r requirements-dev.txt

# Install pre-commit hooks
pre-commit install
```

### Running Tests

```bash
# Run all tests
python -m pytest tests/

# Run specific test categories
python -m pytest tests/test_v1_2_compliance.py
python -m pytest tests/test_v1_2_api_integration.py

# Run with coverage
python -m pytest --cov=medical_data_validator tests/

# Run performance tests
python -m pytest benchmarks/
```

### Code Quality

```bash
# Run linting
flake8 medical_data_validator/
black medical_data_validator/
isort medical_data_validator/

# Run type checking
mypy medical_data_validator/

# Run security checks
bandit -r medical_data_validator/
```

## 🐳 Docker Development

### Development Container

```bash
# Build development image
docker build -f Dockerfile.dev -t medical-validator-dev .

# Run development container
docker run -it --rm \
  -p 8000:8000 \
  -p 5000:5000 \
  -v $(pwd):/app \
  medical-validator-dev

# Access development environment
# - API: https://medical-data-validator-production.up.railway.app/api
# - Dashboard: https://medical-data-validator-production.up.railway.app/home
```

### Multi-stage Build

```dockerfile
# Development stage
FROM python:3.9-slim as dev
WORKDIR /app
COPY requirements-dev.txt .
RUN pip install -r requirements-dev.txt
COPY . .
CMD ["python", "launch_medical_validator_web_ui.py"]

# Production stage
FROM python:3.9-slim as prod
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
CMD ["python", "launch_api.py"]
```

## 🔒 Security Configuration

### SSL/TLS Setup

```bash
# Generate SSL certificate (for development)
openssl req -x509 -newkey rsa:4096 -keyout key.pem -out cert.pem -days 365 -nodes

# Configure Flask with SSL
export FLASK_SSL_CERT=cert.pem
export FLASK_SSL_KEY=key.pem
```

### Authentication Setup

```python
# Configure JWT authentication
JWT_SECRET_KEY = 'your-jwt-secret-key'
JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=1)
JWT_REFRESH_TOKEN_EXPIRES = timedelta(days=30)
```

### CORS Configuration

```python
# Configure CORS for production
CORS_ORIGINS = [
    'https://medical-data-validator-production.up.railway.app',
    'https://yourdomain.com'
]

CORS_ALLOW_CREDENTIALS = True
CORS_ALLOWED_HEADERS = ['Content-Type', 'Authorization']
```

## 📊 Monitoring Setup

### Health Monitoring

```bash
# Check system health
curl https://medical-data-validator-production.up.railway.app/api/health

# Check specific service health
curl https://medical-data-validator-production.up.railway.app/api/v1.2/health
```

### Performance Monitoring

```python
# Enable performance monitoring
from medical_data_validator.monitoring import monitor

# Track validation performance
@monitor.track_performance
def validate_data(data):
    # Validation logic
    pass
```

### Alert Configuration

```python
# Configure alerts
ALERT_CONFIG = {
    'compliance_threshold': 80,
    'response_time_threshold': 5000,  # ms
    'error_rate_threshold': 0.05,
    'notification_channels': ['email', 'slack']
}
```

## 🚀 Production Deployment

### Environment Variables for Production

```bash
# Production settings
FLASK_ENV=production
SECRET_KEY=your-production-secret-key
DEBUG=false

# Security
ALLOWED_ORIGINS=https://medical-data-validator-production.up.railway.app
CORS_ORIGINS=https://medical-data-validator-production.up.railway.app

# Performance
WORKER_PROCESSES=8
MAX_FILE_SIZE=33554432  # 32MB
TIMEOUT=600

# Monitoring
ENABLE_ALERTS=true
ALERT_EMAIL=admin@yourdomain.com
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/...
```

### Production Docker

```yaml
version: '3.8'
services:
  medical-validator:
    build: .
    ports:
      - "8000:8000"
    environment:
      - FLASK_ENV=production
      - SECRET_KEY=${SECRET_KEY}
      - ENABLE_COMPLIANCE=true
      - ENABLE_ANALYTICS=true
      - ENABLE_MONITORING=true
    volumes:
      - ./compliance_templates:/app/compliance_templates
      - ./logs:/app/logs
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "https://medical-data-validator-production.up.railway.app/api/health"]
      interval: 30s
      timeout: 10s
      retries: 3
```

## 🐛 Troubleshooting

### Common Issues

1. **Import Errors**: Ensure virtual environment is activated
2. **Port Conflicts**: Check if ports 8000/5000 are available
3. **Permission Issues**: Check file permissions for compliance templates
4. **Memory Issues**: Increase system memory for large datasets

### Debug Mode

```bash
# Enable debug mode
export FLASK_ENV=development
export DEBUG=true

# Start with debug logging
python -u launch_medical_validator_web_ui.py --debug
```

### Logs

```bash
# View application logs
tail -f logs/app.log

# View error logs
tail -f logs/error.log

# View access logs
tail -f logs/access.log
```

### Performance Issues

```bash
# Monitor system resources
htop
iotop
netstat -tulpn

# Check application performance
python -m cProfile -o profile.stats launch_api.py
```

## 📚 Next Steps

### Documentation
- **[API Documentation](API_DOCUMENTATION.md)** - Complete API reference
- **[Deployment Guide](DEPLOYMENT_V1.2.md)** - Production deployment
- **[V1.2 Features](V1.2_FEATURES.md)** - Advanced features overview

### Integration
- **[cURL Examples](API_CURL_EXAMPLES.md)** - API usage examples
- **[Python SDK](README.md#python-library)** - Python integration guide
- **[JavaScript Examples](API_DOCUMENTATION.md#javascript-examples)** - Frontend integration

### Support
- **Documentation**: https://medical-data-validator-production.up.railway.app/docs
- **API Docs**: https://medical-data-validator-production.up.railway.app/api/docs
- **Health Check**: https://medical-data-validator-production.up.railway.app/api/health
- **Issues**: [GitHub Issues](https://github.com/RanaEhtashamAli/medical-data-validator/issues)

---

**Medical Data Validator v1.2 - Installation Complete! 🎉**

*Your healthcare data validation system is ready to use.* 