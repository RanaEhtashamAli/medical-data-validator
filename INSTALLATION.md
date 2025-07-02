# Installation Guide

## 🚀 **Installation Options**

The Medical Data Validator supports modular installation, allowing you to install only the components you need.

## 📦 **Core Installation**

Install only the core validation library (no CLI, web UI, or API):

```bash
pip install medical-data-validator
```

**What's included:**
- Core validation engine
- Medical code validators (ICD-10, LOINC, CPT)
- PHI/PII detection
- Data quality checks
- Python API access

## 🖥️ **CLI Installation**

Add command-line interface capabilities:

```bash
pip install medical-data-validator[cli]
```

**What's added:**
- Command-line interface
- Rich terminal output
- Tabular results display
- Interactive validation commands

## 🌐 **Web Dashboard Installation**

Add web dashboard interface:

```bash
pip install medical-data-validator[web]
```

**What's added:**
- Flask-based web dashboard
- Interactive file upload
- Visual charts and reports
- Real-time validation results

## 🔌 **REST API Installation**

Add REST API capabilities:

```bash
pip install medical-data-validator[api]
```

**What's added:**
- Flask-based REST API
- File upload endpoints
- JSON data validation
- Interactive API documentation
- Health check endpoints

## 🌐 **All Web Interfaces**

Install both web dashboard and REST API:

```bash
pip install medical-data-validator[web-all]
```

**What's added:**
- Web dashboard (Flask)
- REST API (Flask)
- All web-related dependencies

## 🎯 **Complete Installation**

Install everything (core + CLI + web + API):

```bash
pip install medical-data-validator[all]
```

**What's included:**
- Core validation engine
- Command-line interface
- Web dashboard
- REST API
- All dependencies

## 🛠️ **Development Installation**

For developers and contributors:

```bash
pip install medical-data-validator[dev]
```

**What's added:**
- Testing framework (pytest)
- Code formatting (black, isort)
- Linting (flake8, mypy)
- Security scanning (bandit, safety)
- Pre-commit hooks

## 📚 **Documentation Installation**

For building documentation:

```bash
pip install medical-data-validator[docs]
```

**What's added:**
- Sphinx documentation builder
- ReadTheDocs theme
- API documentation generation

## 🧪 **Testing Installation**

For running tests:

```bash
pip install medical-data-validator[test]
```

**What's added:**
- pytest testing framework
- Coverage reporting
- Benchmarking tools

## 🔄 **Combination Examples**

Install multiple components:

```bash
# Core + CLI + Web Dashboard
pip install medical-data-validator[cli,web]

# Core + API + Development tools
pip install medical-data-validator[api,dev]

# Everything except documentation
pip install medical-data-validator[all,docs]

# Core + CLI + Testing
pip install medical-data-validator[cli,test]
```

## 📋 **Dependency Summary**

| Component | Dependencies | Size |
|-----------|-------------|------|
| **Core** | pandas, pydantic, numpy, openpyxl | ~50MB |
| **CLI** | click, rich, tabulate | +15MB |
| **Web** | flask, plotly, dash, gunicorn | +80MB |
| **API** | flask, python-multipart | +15MB |
| **All** | Complete stack | ~200MB |

## 🚀 **Quick Start Examples**

### Core Only (Python API)
```python
from medical_data_validator import MedicalDataValidator
import pandas as pd

# Load data
data = pd.read_csv('medical_data.csv')

# Validate
validator = MedicalDataValidator()
result = validator.validate(data)
print(f"Valid: {result.is_valid}")
```

### CLI Usage
```bash
# Install CLI
pip install medical-data-validator[cli]

# Use CLI
medical-validator validate data.csv --detect-phi
```

### Web Dashboard
```bash
# Install web dashboard
pip install medical-data-validator[web]

# Launch dashboard
medical-validator dashboard
# Open http://localhost:5000
```

### REST API
```bash
# Install API
pip install medical-data-validator[api]

# Launch API server
medical-validator api
# Open http://localhost:8000/docs
```

## 🔧 **Environment-Specific Installation**

### Production Deployment
```bash
# Minimal production install
pip install medical-data-validator[api]

# With web dashboard
pip install medical-data-validator[web-all]
```

### Development Environment
```bash
# Full development setup
pip install medical-data-validator[all,dev,test,docs]
```

### Docker Deployment
```dockerfile
# Install only what you need
RUN pip install medical-data-validator[api]

# Or install everything
RUN pip install medical-data-validator[all]
```

## ⚠️ **Troubleshooting**

### Missing Dependencies
If you get import errors, install the required components:

```bash
# For web dashboard errors
pip install medical-data-validator[web]

# For API errors
pip install medical-data-validator[api]

# For CLI errors
pip install medical-data-validator[cli]
```

### Version Conflicts
If you encounter dependency conflicts:

```bash
# Create a fresh virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install with specific version
pip install medical-data-validator[all]==0.1.0
```

### System Requirements
- **Python**: 3.8 or higher
- **Memory**: 512MB minimum (2GB recommended for web interfaces)
- **Disk**: 200MB for complete installation
- **Network**: Required for downloading dependencies

## 📞 **Support**

For installation issues:
- Check the [troubleshooting section](#-troubleshooting)
- Review [dependency requirements](#-dependency-summary)
- Open an issue on GitHub with your error details

---

**Last Updated**: July 2025  
**Package Version**: 0.1.0 