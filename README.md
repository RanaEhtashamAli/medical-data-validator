# Medical Data Validator

[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.15815620.svg)](https://doi.org/10.5281/zenodo.15815620)
[![CI](https://github.com/RanaEhtashamAli/medical-data-validator/actions/workflows/ci.yml/badge.svg)](https://github.com/RanaEhtashamAli/medical-data-validator/actions/workflows/ci.yml)
[![codecov](https://codecov.io/gh/RanaEhtashamAli/medical-data-validator/branch/master/graph/badge.svg)](https://codecov.io/gh/RanaEhtashamAli/medical-data-validator)

A Python library and REST API for validating healthcare datasets — PHI/PII detection, HIPAA/GDPR/FDA compliance scoring, data quality checks, and interactive dashboards.

> **Scope notice:** This tool assists research and data engineering teams in assessing data quality and identifying compliance risks. It is **not a substitute for a certified HIPAA/GDPR audit**, legal counsel, or a Business Associate Agreement. Regulatory compliance requires organisational controls, staff training, and third-party assessment that go beyond software.

## Features

### Core Validation
- **Multi-format support**: CSV, Excel, JSON, Parquet
- **PHI/PII detection**: All 18 HIPAA Safe Harbor identifiers
- **Medical code validation**: ICD-10, LOINC, CPT
- **Data quality checks**: Completeness, accuracy, consistency, timeliness
- **Extensible rule system**: Custom `ValidationRule` subclasses + setuptools entrypoints

### Compliance & Analytics (v1.2)
- **Compliance scoring**: HIPAA, GDPR, FDA 21 CFR Part 11 (heuristic, not certified)
- **FHIR R4 & SNOMED CT plugins**: via `load_compliance_plugins()`
- **Real-time monitoring**: Background thread, alert deduplication
- **Audit trail**: Append-only SQLite log, JWT authentication, multi-tenancy
- **Async jobs**: SQLite-backed job queue with background worker
- **Report export**: PDF and CSV via `/api/report` endpoints

### Operations
- **REST API**: Flask + Gunicorn, `/api/validate`, `/api/anonymize`, `/api/jobs`, `/api/report`
- **Web dashboard**: Dash + Bootstrap 5, interactive charts
- **Docker**: Multi-stage image, docker-compose with Redis

## Quick Start

```bash
git clone https://github.com/RanaEhtashamAli/medical-data-validator.git
cd medical-data-validator

# Install with all extras
pip install -e ".[all,dev]"

# Run the REST API (port 8000)
python api.py

# Run the web dashboard (port 5000)
SECRET_KEY=$(python -c "import secrets; print(secrets.token_hex(32))") python launch_dashboard.py
```

### Python Library

```python
from medical_data_validator import MedicalDataValidator
from medical_data_validator.validators import PHIDetector, DataQualityChecker
import pandas as pd

validator = MedicalDataValidator(
    enable_compliance=True,
    compliance_template='clinical_trials',
)
validator.add_rule(PHIDetector())
validator.add_rule(DataQualityChecker())

data = pd.read_csv('your_medical_data.csv')
result = validator.validate(data)

print(f"Valid: {result.is_valid}")
print(f"Issues: {len(result.issues)}")

compliance = result.summary.get('compliance_report', {})
print(f"Overall Score: {compliance.get('overall_score', 'N/A')}")
print(f"Risk Level:    {compliance.get('risk_level', 'N/A')}")
```

### FHIR R4 + SNOMED CT

```python
from medical_data_validator.plugins import load_compliance_plugins

engine = load_compliance_plugins()          # auto-discovers installed plugins
report  = engine.comprehensive_compliance_validation(df)
```

### Anonymization

```python
anon_df = validator.anonymize(
    df,
    columns=['patient_name', 'ssn', 'email'],
    method='hipaa_safe_harbor',
)
```

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/health` | Health check |
| POST | `/api/validate/file` | Validate uploaded file |
| POST | `/api/validate/data` | Validate JSON data |
| POST | `/api/anonymize` | Anonymize columns |
| POST | `/api/jobs` | Submit async validation job |
| GET | `/api/jobs/<id>` | Poll job status |
| POST | `/api/report/inline/pdf` | Generate PDF report |
| POST | `/api/report/inline/csv` | Generate CSV report |
| GET | `/api/audit` | Query audit log |

## Docker

```bash
cp env.example .env   # fill in SECRET_KEY, JWT_SECRET, ADMIN_PASSWORD
docker-compose up -d
# API: http://localhost:8000/api/health
# Dashboard: http://localhost:8000/home
```

## Development

```bash
# Run all tests
pytest

# Skip slow/integration tests
pytest -m "not slow and not integration"

# Coverage report
pytest --cov=medical_data_validator --cov-report=term-missing

# Security scan
bandit -r medical_data_validator/ -ll

# Lint
flake8 medical_data_validator/
black medical_data_validator/
isort medical_data_validator/
```

## Supported Standards

| Standard | What is checked |
|---|---|
| HIPAA Safe Harbor | 18 PHI identifier patterns |
| GDPR | Personal and sensitive data presence |
| FDA 21 CFR Part 11 | Audit trail fields, electronic signature fields |
| ICD-10 / LOINC / CPT | Code format validity |
| FHIR R4 | Resource structure (plugin) |
| SNOMED CT | Terminology codes (plugin) |

## Configuration

Copy `env.example` to `.env` and set at minimum:

```bash
SECRET_KEY=<32-byte hex>
JWT_SECRET=<32-byte hex>
ADMIN_PASSWORD=<strong password>
FLASK_ENV=production
```

See `docs/compliance_checklist.md` for the full pre-production checklist.

## Researcher Documentation

- `docs/quickstart.ipynb` — Jupyter notebook: validate → inspect compliance → anonymize → export reports → async jobs
- `docs/compliance_checklist.md` — HIPAA, GDPR, FDA 21 CFR Part 11, GCP feature mapping

## License

MIT — see [LICENSE](LICENSE).

## Support

- Issues: [GitHub Issues](https://github.com/RanaEhtashamAli/medical-data-validator/issues)
- Discussions: [GitHub Discussions](https://github.com/RanaEhtashamAli/medical-data-validator/discussions)
