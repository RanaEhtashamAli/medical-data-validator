# medical-data-validator Phase B: Coverage Gaps — Design

## Problem

Phase A fixed things that were broken. Phase B closes four gaps identified in the same audit where the underlying code is *correct* but never wired up or exposed:

1. `SchemaValidator`, `RangeValidator`, `DateValidator`, `MedicalCodeValidator` (`medical_data_validator/validators.py`) are real, working validation rules, but the REST API's `create_validator()` (`dashboard/routes.py`) only accepts `detect_phi`/`quality_checks`/`profile`/`enable_compliance`/`template` — there's no way to configure required columns, column types, numeric ranges, date formats, or code-column mappings through the API. The CLI's `validate` subcommand has partial support (`--required-columns`, `--column-types`) but nothing for ranges/dates/code-columns.
2. `HIPAAComplianceChecker`, `SecurityAuditor`, `DataSanitizer` (`medical_data_validator/security.py`) are fully implemented but have zero callers outside their own file and tests — no route, CLI command, or Dash callback ever invokes them.
3. `ValidationCache` and `BatchValidator` (`medical_data_validator/performance.py`) are only imported by the package's `__init__.py` (public API export) and their own tests — no request path uses them. `BatchValidator` chunks one large dataset into row-batches (not multiple files, despite the name suggesting otherwise) and caches per-batch results.
4. `medical_data_validator/dashboard/dash_layout.py` (150 lines) has zero UI components for the 17 real routes in `auth.py`, `registry.py`, `jobs.py`, and `audit.py`, plus the compliance custom-rules and inline-report endpoints in `routes.py`/`reports.py` — the Dash UI only covers the original upload/validate flow.

All four are verified directly against the code (grep + read), not inherited from the original audit report unchecked.

## Goals

- `SchemaValidator`/`RangeValidator`/`DateValidator`/`MedicalCodeValidator` are configurable per API request and via CLI flags, with full parity between the two.
- `HIPAAComplianceChecker`/`SecurityAuditor`/`DataSanitizer` are reachable via new REST endpoints.
- `BatchValidator`/`ValidationCache` are wired into the existing validate endpoints as opt-in parameters.
- The Dash UI at `/dash/` becomes a full multi-page admin panel with parity for auth (user/tenant management), dataset registry, job queue, custom compliance rules, report downloads, and the audit log — alongside the existing validate flow.

## Non-goals

- A real login/session gate for the Dash UI. Dash calls the underlying business-logic functions in-process, always acting as a fixed identity (tenant `'default'`), the same way the existing Validate page already bypasses its own HTTP API and calls `create_validator()` directly. This means anyone who can reach `/dash/` has effectively admin-level access to these panels — acceptable only because network/deployment-level access control is out of scope for this app itself (same trust boundary the existing anonymous Validate page already has).
- Changing `ComplianceEngine`, `PHIDetector`, or any other already-correct validation/compliance logic.
- A true "upload N separate files as one batch" endpoint — `BatchValidator` doesn't do this; see Architecture, Batch section.
- Persisting uploaded files to disk to make `SecurityAuditor`'s file-permission check meaningful — uploads are read straight from the request stream today, and this phase doesn't change that.

## Architecture

### A. Per-request validator configuration

`/api/validate/data` and `/api/validate/file`'s JSON body gains an optional `validators` block:

```json
{
  "data": {"...": "..."},
  "validators": {
    "required_columns": ["patient_id", "diagnosis"],
    "column_types": {"age": "int"},
    "ranges": {"age": {"min": 0, "max": 120}},
    "date_columns": ["visit_date", "admission_date"],
    "min_date": "2000-01-01",
    "max_date": "2026-12-31",
    "code_columns": {"diagnosis_code": "icd10", "test_code": "loinc"}
  }
}
```

`create_validator()` gains a new `validators_config: Optional[dict]` parameter. When present, for each key that appears it instantiates and adds the matching rule, using each class's real constructor (verified by reading `validators.py` directly, not assumed):
- `required_columns`/`column_types` → `SchemaValidator(required_columns=..., column_types=...)`
- `ranges` (`{column: {min, max}}`) → a single `RangeValidator(ranges=ranges_dict)` — the class already takes the whole multi-column dict in one constructor call, so the request shape maps straight through with no per-column instantiation needed.
- `date_columns`/`min_date`/`max_date` → a single `DateValidator(date_columns=[...], min_date=..., max_date=...)`. Note this class does **not** take a per-column format string — it auto-detects format via `pd.to_datetime(..., errors="coerce")` — and `min_date`/`max_date` are one shared range applied to every listed column, not configurable per-column. (An earlier draft of this spec incorrectly assumed a `date_formats: {column: format}` shape; corrected after reading the actual class.)
- `code_columns` (`{column: standard}`) → `MedicalCodeValidator(code_columns)`, matching Phase A's CLI fix for the same class

No `validators` key in the request means zero behavior change from today.

CLI parity (`medical_data_validator/cli.py`'s `validate` subcommand): keep existing `--required-columns`/`--column-types`, add `--range COLUMN:MIN:MAX` (repeatable), `--date-column COLUMN` (repeatable) plus single `--min-date`/`--max-date` flags, and `--code-column COLUMN:STANDARD` (repeatable). `create_validator_from_args()` builds the same `validators_config` dict shape and passes it through, so the API and CLI share one config schema.

### B. Security endpoints

New `medical_data_validator/security.py` function `register_security_routes(app)`, called from `routes.py`'s `register_routes(app)` alongside the existing auth/audit/registry/jobs registrations. Same file-or-JSON-data input handling as `api_validate_data`/`api_validate_file` (reuse that parsing, don't duplicate it a third time).

- `POST /api/security/hipaa-check` → `HIPAAComplianceChecker().check_hipaa_compliance(df)`. By default, strip `sample_values` from each `phi_detected` entry (replace with `sample_count: len(...)`) before returning — echoing real PHI values (SSNs, emails) back through an API response defeats the purpose of a HIPAA tool. A request-level `include_samples: true` flag restores the original behavior for callers who explicitly opt in (e.g. internal debugging).
- `POST /api/security/audit` → `SecurityAuditor().audit_security(df, file_path=None)`. `file_path` is always `None` (uploads aren't persisted to disk) — the file-permission sub-check will report no issues, which is correct given its `if file_path:` guard rather than a fabricated result.
- `POST /api/security/sanitize` → `DataSanitizer().sanitize_data(df)`, response is `{"sanitized_data": df.to_dict(orient="records")}`.

### C. Batch + cache wiring

`/api/validate/data` and `/api/validate/file` gain optional `batch_size: int` and `use_cache: bool` fields (JSON body for `/validate/data`; form fields for the multipart `/validate/file`). When `batch_size` is set:

```python
validator = create_validator(...)  # unchanged
if batch_size:
    cache = _validation_cache if use_cache else None
    result = BatchValidator(validator, batch_size=batch_size, cache=cache).validate_batches(df)
else:
    result = validator.validate(df)
```

`_validation_cache` is a single module-level `ValidationCache(max_size=int(os.environ.get('VALIDATION_CACHE_MAX_SIZE', 1000)))` in `routes.py`, created once at import time and shared across all requests for the lifetime of the process — this is new shared mutable state, bounded in size (LRU eviction) but unbounded in lifetime. No cross-process sharing (each Gunicorn worker gets its own cache instance); acceptable since the cache is a performance optimization, not a correctness dependency.

### D. Dash multi-page admin UI

Switch `create_dashboard_app()` (`dashboard/app.py`) from a single-page `dash.Dash(..., url_base_pathname='/dash/')` to `dash.Dash(..., url_base_pathname='/dash/', use_pages=True)`. New structure:

```
medical_data_validator/dashboard/
  pages/
    __init__.py
    validate.py       # today's upload/validate flow, moved as-is (register_page path="/dash/")
    registry.py        # dataset registry CRUD
    jobs.py             # job submission + status polling
    custom_rules.py    # compliance custom-rules CRUD
    audit.py            # audit log viewer
    auth.py              # user/tenant management (no login form)
  dash_layout.py     # becomes the app shell: sidebar (dbc.Nav) + dash.page_container
```

Each page module calls `dash.register_page(__name__, path=..., name=...)` at import time and exposes a `layout` (a Dash component tree, following the existing `setup_dash_layout` style). `dashboard/app.py` imports the `pages` package before constructing the `dash.Dash(...)` instance so registration happens first (standard Dash Pages requirement).

**Calling convention** — every page's callbacks call the same module-level business-logic functions the REST routes call, directly, in-process:
- Registry page → `list_datasets`, `register_dataset`, `get_dataset`, `update_dataset`, `delete_dataset`, `get_run_history` (all in `registry.py`)
- Jobs page → `submit_job`, `get_job`, `list_jobs` (in `jobs.py`)
- Audit page → `query_log`, `count_log` (in `audit.py`)
- Custom Rules page → reads/appends/removes from `routes.py`'s module-level `_custom_rules_storage` list directly (already plain in-memory state, no route-closure indirection to work around)
- Auth page → `list_users`, `create_user`, `deactivate_user`, `create_tenant` — **currently nested as closures inside `register_auth_routes(app)` in `auth.py`**, unlike the other three modules which already keep business logic at module level with thin route-registration wrappers. This phase extracts those four into module-level functions in `auth.py` (matching the established pattern elsewhere), with the existing `@app.route` closures becoming thin wrappers that just add the HTTP/auth-decorator layer — a targeted fix to an inconsistency in the one module that doesn't already follow the codebase's own convention.

All pages act as tenant `'default'` with no role check (bypassing `login_required`/`role_required`, which only wrap the route closures, not these underlying functions).

**Reports**: no dedicated Reports page. `generate_pdf_report`/`generate_csv_report` (`reports.py`) take a `ValidationResult.to_dict()`-shaped dict, so "Download PDF" / "Download CSV" buttons (`dcc.Download` + a button callback) are added directly to the Validate page (after a run completes) and the Jobs page (next to each completed job's stored result).

**Testing**: every page's callback logic is extracted into a plain, directly-testable function first (e.g. `_list_datasets_for_table(tenant, tag, limit, offset)`, `_submit_job_from_form(job_type, payload)`), with the `@dash_app.callback`-decorated function being a thin pass-through — the same pattern Phase A's Task 6 already established for the Validate page's `_run_validation_for_upload`.

**Status (Phase B.1 addendum, closing a gap found in Phase B's final review):** Phase B's initial implementation (Tasks 6-11) shipped list+create only for Registry, Jobs, Audit, and Custom Rules — narrower than this section describes. A final whole-branch review caught the gap; a follow-up addendum (Tasks 13-16) closed it, bringing each page's calling convention in line with what's documented above:
- Registry page now also calls `get_dataset`/`update_dataset`/`delete_dataset` (view/update/delete actions, with a tenant-ownership check added on top since those functions are plain UUID lookups with no tenant filter of their own).
- Jobs page now also calls `get_job` (view job detail, same tenant-ownership check applied) and gained PDF/CSV download buttons next to a viewed job's result, alongside the Validate page's.
- Audit page now also calls `count_log` (a "Showing X of Y records" total, independent of the page-limited list).
- Custom Rules page now also removes rules from `_custom_rules_storage` (no tenant concept applies here — the storage itself is a plain, un-scoped list).

`get_run_history`/`count_runs` (Registry) remain unused by any Dash page — no task has wired up a run-history view yet; this is the one remaining gap between this section and what's shipped.

## Error handling

- New security/batch endpoints reuse the existing `try/except` + `logger.exception` + `traceback` (gated behind `current_app.debug`) pattern already standardized across `routes.py` in Phase A — no new error-handling convention introduced.
- Dash pages: business-logic functions that can raise (`register_dataset` on duplicate name, `submit_job` on bad `job_type`) have their exceptions caught in the extracted callback function and turned into an inline error message component, not an unhandled 500 — matching `_run_validation_for_upload`'s existing `except Exception as exc: return f"Could not parse {filename}: {exc}", ...` pattern.

## Testing

- Unit tests for the `validators_config` → rule-instantiation logic in `create_validator()` (one test per config key, plus a combined-config test).
- Unit tests for each new security endpoint (happy path + the `sample_values` redaction/`include_samples` opt-in).
- Unit tests for the `batch_size`/`use_cache` branch in `api_validate_data`/`api_validate_file` (confirm `BatchValidator` is actually invoked when set, confirm identical results between batched and non-batched validation of the same data).
- Unit tests for each new page's extracted callback function (list/create/update/delete per area), following the existing `test_dash_layout.py` pattern — one new `test_dash_<page>.py` file per page.
- CLI tests for the new `--range`/`--date-format`/`--code-column` flags, following the existing `TestConsolidatedCLI` pattern in `tests/test_cli.py`.

## Self-review notes

- **Placeholder scan**: `RangeValidator`/`DateValidator`'s exact constructor signatures were verified by reading `validators.py` directly during spec-writing (not left as a deferred "confirm during implementation" placeholder) — this caught and corrected a wrong assumption about `DateValidator` taking a per-column format string before the plan was written, not after.
- **Scope check**: this spec covers all four gaps per the user's explicit choice to handle them as one combined plan rather than four sub-projects, given they're independent enough to task out separately within one plan but the user wants Phase B done in full before deployment.
- **Consistency**: the Dash-calls-business-logic-directly convention (D) is the same convention Phase A's Task 6 already established for the Validate page — this spec extends an existing pattern rather than introducing a new one.
