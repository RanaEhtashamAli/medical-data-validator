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
- **REST API**: Flask + Gunicorn — validation, anonymization, async jobs, report export, dataset registry, security endpoints, JWT auth
- **Web dashboard**: Dash + Bootstrap 5, multi-page admin UI (validate, dataset registry, jobs, custom compliance rules, audit log, users & tenants)
- **CLI**: per-column range/date/medical-code checks alongside file validation
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

### CLI: per-column checks

```bash
medical-validator validate data.csv \
  --detect-phi --quality-checks \
  --range age:0:120 \
  --date-column visit_date --min-date 2020-01-01 --max-date 2026-12-31 \
  --code-column diagnosis_code:icd10 --code-column procedure_code:cpt \
  --format json --output results.json
```

`--range`/`--date-column`/`--code-column` are repeatable and can be combined with `--profile`. See `medical-validator validate --help` for the full flag list.

## API Endpoints

`/api/validate/data` and `/api/validate/file` also accept optional `validators` (JSON-encoded per-column rules: `required_columns`, `column_types`, `ranges`, `date_columns`, `min_date`/`max_date`, `code_columns`), `batch_size`, and `use_cache` query params (or form fields for the file endpoint) — see [API_DOCUMENTATION.md](API_DOCUMENTATION.md) for the full schema.

| Method | Path | Description | Auth |
|--------|------|-------------|------|
| GET | `/api/health` | Health check | none |
| POST | `/api/validate/file` | Validate uploaded file | none |
| POST | `/api/validate/data` | Validate JSON data | none |
| POST | `/api/anonymize` | Anonymize columns | none |
| POST | `/api/security/hipaa-check` | HIPAA Safe Harbor PHI scan (file or JSON) | none |
| POST | `/api/security/audit` | Security posture audit (file permissions, sanitization risk) | none |
| POST | `/api/security/sanitize` | Strip HTML/script injection from text columns | none |
| POST | `/api/compliance/v1.2` | Full HIPAA/GDPR/FDA/medical-coding compliance report | none |
| GET | `/api/compliance/templates` | List built-in compliance templates | none |
| GET | `/api/compliance/plugins` | List discovered compliance plugins (e.g. FHIR R4, SNOMED CT) | none |
| GET/POST | `/api/compliance/custom-templates` | List / add a custom compliance template (named bundle of rules) | none |
| DELETE | `/api/compliance/custom-templates/<name>` | Remove a custom compliance template | none |
| GET/POST | `/api/compliance/custom-rules` | List / add a custom compliance rule (regex pattern) | none |
| DELETE | `/api/compliance/custom-rules/<name>` | Remove a custom compliance rule | none |
| POST | `/api/analytics` | Data quality analytics (completeness, trends, anomalies) | none |
| GET | `/api/monitoring/stats` \| `/alerts` | Real-time validation stats / active alerts | none |
| POST | `/api/monitoring/alerts/<id>/acknowledge` \| `/resolve` | Manage an alert | none |
| GET | `/api/monitoring/trends/<metric>` | Historical trend for one metric | none |
| POST | `/api/jobs` | Submit async validation/anonymize job | JWT (data-steward+) |
| GET | `/api/jobs` \| `/api/jobs/<id>` | List jobs / poll job status | JWT |
| POST | `/api/report/inline/pdf` \| `/csv` | Generate a report from a posted result | JWT |
| GET | `/api/report/<job_id>/pdf` \| `/csv` | Generate a report from a completed job's stored result | JWT |
| GET | `/api/audit` | Query audit log | JWT (data-steward+) |
| POST | `/api/auth/token` | Exchange username + password for a JWT | none |
| GET | `/api/auth/me` | Info about the current authenticated user | JWT |
| GET/POST | `/api/auth/users` | List / create users | JWT (admin) |
| DELETE | `/api/auth/users/<username>` | Deactivate a user | JWT (admin) |
| POST | `/api/auth/tenants` | Create a tenant | JWT (admin) |
| GET/POST | `/api/registry/datasets` | List / register datasets | JWT |
| GET/PATCH/DELETE | `/api/registry/datasets/<id>` | Read, update, or remove a dataset entry | JWT |
| GET | `/api/registry/datasets/<id>/history` | Dataset's validation run history | JWT |
| POST | `/api/registry/datasets/<id>/runs` | Record a validation run against a dataset | JWT (data-steward+) |

JWT-protected endpoints use three roles (`admin` > `data-steward` > `read-only`); acquire a token via `/api/auth/token` and send `Authorization: Bearer <token>`. See [API_DOCUMENTATION.md](API_DOCUMENTATION.md) for request/response bodies, role requirements, and `/v1.2`/legacy-path equivalents.

## Web Dashboard

`/dash/` is a multi-page admin UI (Dash + Bootstrap):

| Page | Path | Purpose |
|---|---|---|
| Validate | `/dash/` | Upload a file, run validation, download the PDF/CSV report |
| Registry | `/dash/registry` | List, register, view, update, delete datasets |
| Jobs | `/dash/jobs` | Submit async jobs, poll status, view results, download reports |
| Custom Rules | `/dash/custom-rules` | List, add, remove custom compliance rules |
| Audit Log | `/dash/audit` | Browse the audit trail |
| Users & Tenants | `/dash/auth` | Manage users and tenants |
| Security | `/dash/security` | Run a HIPAA check or security audit, sanitize a dataset |
| Anonymize | `/dash/anonymize` | Anonymize PHI/PII columns (HIPAA Safe Harbor, hash, or mask) |
| Analytics | `/dash/analytics` | Data quality metrics, anomaly detection, and trend analysis |
| Monitoring | `/dash/monitoring` | Real-time validation stats, alert management, quality trends |
| Compliance | `/dash/compliance` | Run v1.2 compliance reports, manage custom templates, view plugins |

> **Note:** the dashboard calls the underlying business logic directly, in-process, as a fixed `default`-tenant identity — it does **not** go through the REST API's JWT/role checks. Treat `/dash/` as an internal admin tool (e.g. behind a reverse-proxy auth layer or restricted network access), not as a role-scoped, multi-tenant-safe UI on its own.

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
