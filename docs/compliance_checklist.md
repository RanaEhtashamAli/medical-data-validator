# Compliance Checklist

This checklist maps Medical Data Validator settings and features to the
regulatory requirements your institution must satisfy before processing
patient data in production.

---

## HIPAA (Health Insurance Portability and Accountability Act)

| Requirement | Feature / Setting | Status |
|---|---|---|
| De-identify PHI before sharing (Safe Harbor) | `validator.anonymize(df, method='hipaa_safe_harbor')` | ✅ Built-in |
| Detect all 18 PHI identifiers | `PHIDetector` rule + `PHI_PATTERNS` in `utils.py` | ✅ Built-in |
| Audit trail of every disclosure | `audit.log_event()` called automatically by `validate()` | ✅ Built-in |
| Immutable audit records (no deletions) | Append-only SQLite / `INSERT` only, no `DELETE` in `audit.py` | ✅ Built-in |
| Access control to PHI systems | JWT auth with `data-steward` / `admin` roles (`auth.py`) | ✅ Built-in |
| Minimum necessary access principle | Tenant-scoped queries; `read-only` role cannot anonymize | ✅ Built-in |
| Encryption in transit | TLS termination at Nginx (see `docker-compose.yml` nginx service) | ⚙️ Configure |
| Encryption at rest | Mount `/data` on an encrypted volume or enable PostgreSQL TDE | ⚙️ Configure |

**Required settings:**
```bash
ADMIN_PASSWORD=<strong-random-password>
JWT_SECRET=<32-byte-random-hex>
SECRET_KEY=<32-byte-random-hex>
FLASK_ENV=production
```

---

## GDPR (General Data Protection Regulation)

| Requirement | Feature / Setting | Status |
|---|---|---|
| Identify personal data in datasets | `PHIDetector` + GDPR patterns in `ComplianceEngine` | ✅ Built-in |
| Data minimisation — anonymize before storage | `validator.anonymize()` with `hipaa_safe_harbor` or `hash` | ✅ Built-in |
| Right to erasure (forget) | Delete records via `registry.delete_dataset()` + audit note | ⚙️ Implement |
| Records of processing activities | `audit.query_log()` + `/api/audit` endpoint | ✅ Built-in |
| Purpose limitation — tenant isolation | Multi-tenancy: `X-API-Key` + JWT `tenant` claim | ✅ Built-in |
| Data breach detection | `RealTimeMonitor` anomaly alerts in `monitoring.py` | ✅ Built-in |
| DPA / data transfer safeguards | Deploy within EU region; restrict `DEFAULT_TENANT_API_KEY` | ⚙️ Configure |

---

## FDA 21 CFR Part 11 (Electronic Records / Electronic Signatures)

| Requirement | Feature / Setting | Status |
|---|---|---|
| Audit trail with time-stamp, user ID, action | `audit.log_event()` stores `username`, `tenant`, ISO-8601 timestamp | ✅ Built-in |
| Tamper-evident records | Append-only table; each record has UUID primary key | ✅ Built-in |
| Access controls and unique user IDs | JWT auth; each user has unique username + password hash | ✅ Built-in |
| Operational system checks | `/api/health` endpoint + `RealTimeMonitor` | ✅ Built-in |
| Authority checks | `role_required('admin')` / `role_required('data-steward')` decorators | ✅ Built-in |
| Validation of systems | Run `pytest` + `bandit` + `safety` before each deployment | ⚙️ CI/CD |
| Sequenced steps enforced | Job lifecycle: `pending → running → completed/failed` only | ✅ Built-in |
| Record retention (at least 3 years) | Persist `/data/audit.db` on durable storage; snapshot regularly | ⚙️ Configure |

---

## GCP (Good Clinical Practice — ICH E6 R2)

| Requirement | Feature / Setting | Status |
|---|---|---|
| Protocol-specified data quality | `ValidationProfile('clinical_trials')` in `extensions.py` | ✅ Built-in |
| Traceability of source data | Dataset registry (`registry.py`) links dataset hash to run history | ✅ Built-in |
| Audit trail for CRF changes | `audit.log_event('validation')` with `dataset_hash` (SHA-256) | ✅ Built-in |
| Qualified personnel access | Role-based access: admin assigns roles per user | ✅ Built-in |
| ICD-10 / LOINC / CPT code validity | `MedicalCodeValidator` + `ComplianceEngine` medical_coding standard | ✅ Built-in |
| FHIR R4 interoperability | `FHIRCompliancePlugin` via `load_compliance_plugins()` | ✅ Built-in |
| SNOMED CT terminology | `SNOMEDCompliancePlugin` via `load_compliance_plugins()` | ✅ Built-in |

---

## Recommended Pre-Production Checklist

Before going live, verify each item below:

- [ ] `SECRET_KEY`, `JWT_SECRET`, and `ADMIN_PASSWORD` are set from environment (not defaults)
- [ ] HTTPS enabled (Nginx TLS or load-balancer termination)
- [ ] `/data` volume is on encrypted, backed-up storage
- [ ] `FLASK_ENV=production` (disables debug traces in API responses)
- [ ] `pytest` suite passes with no failures: `pytest tests/`
- [ ] `bandit -r medical_data_validator/` reports no HIGH severity issues
- [ ] `safety check` reports no known CVEs in dependencies
- [ ] At least one non-admin user created with the minimum required role
- [ ] Audit log retention policy documented (minimum 3 years for FDA/GCP)
- [ ] Docker image pinned to a specific digest in CI/CD (no `:latest` in prod)
- [ ] Redis password set in production (`requirepass` in `redis.conf`)
- [ ] PostgreSQL enabled and connection string set for `AUDIT_DB_PATH` (production scale)
- [ ] `load_compliance_plugins()` called at startup to activate FHIR/SNOMED checks
- [ ] `ValidationProfile('clinical_trials')` used for clinical trial datasets

---

## Configuration Quick-Reference

```python
# Minimum production validator setup for clinical trials
from medical_data_validator.core import MedicalDataValidator
from medical_data_validator.validators import PHIDetector, DataQualityChecker, MedicalCodeValidator
from medical_data_validator.plugins import load_compliance_plugins

validator = MedicalDataValidator(
    enable_compliance=True,
    compliance_template='clinical_trials',   # GCP-aligned rule set
    enable_analytics=True,
    enable_monitoring=True,
)
validator.add_rule(PHIDetector())
validator.add_rule(DataQualityChecker())
validator.add_rule(MedicalCodeValidator())

# Activate FHIR R4 + SNOMED CT
engine = load_compliance_plugins(validator.compliance_engine)

result = validator.validate(df)
```
