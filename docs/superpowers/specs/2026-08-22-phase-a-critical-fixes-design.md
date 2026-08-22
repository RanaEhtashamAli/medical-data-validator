# medical-data-validator Phase A: Critical Fixes — Design

## Problem

A coverage/quality audit (see conversation context; findings independently verified by running the code, not just reading it) found the core validation library is solid, but several things sitting on top of it are actually broken, not just incomplete:

1. The published `medical-validator` CLI console script cannot run at all (`ModuleNotFoundError`) — the sdist doesn't ship the root-level file the entry point imports.
2. `medical_data_validator_cli.py`'s `dashboard`, `api`, `benchmark`, and `compliance` subcommands are each broken by wrong imports or calls to methods that don't exist.
3. `API_DOCUMENTATION.md` documents `/api/v1.2/*` as the base URL; the real routes are at `/v1.2/*`. Every example 404s.
4. The same `/api/*` paths are registered twice (a plain Flask blueprint and a flask-restx `Api`), and the restx-documented `/v1.2/compliance/check` is silently wired to the legacy v1.0 handler instead of the real v1.2 one.
5. A dataset with a bare SSN column reports `is_valid: True` at the top level, because PHI findings are severity `"warning"` and only `"error"` flips `is_valid` — even though the nested compliance report correctly flags `risk_level: critical`.
6. The Dash UI at `/dash/` looks real (working upload widget, full layout) but its only callback is a literal placeholder that never calls the validator and always returns empty charts.
7. Production hot paths (`routes.py`, `monitoring.py`) are full of debug `print()` calls; the installed package version (1.2.1) lags the committed source (1.3.0); two near-duplicate CI docker-publish workflows exist, one with a typo'd filename targeting a branch (`master`) the repo no longer uses.

## Goals

- The installed `medical-validator` console script works, with all 6 subcommands functional.
- `API_DOCUMENTATION.md` and README accurately describe the real, de-duplicated route surface.
- The API response distinguishes "passed schema/quality checks" from "carries compliance risk" as two separate, unambiguous fields.
- The Dash UI at `/dash/` is a real second interface, not a decoration.
- Production logs are clean by default; packaging/versioning/CI housekeeping is current.

## Non-goals

- Closing the coverage gaps identified in the same audit (SchemaValidator/RangeValidator/DateValidator/MedicalCodeValidator not configurable per API request, `SecurityAuditor`/`HIPAAComplianceChecker`/`DataSanitizer` unwired, batching/caching unused, no dashboard UI for auth/jobs/registry/reports/audit/custom-rules) — that's Phase B, a separate spec.
- Deduplicating the 4+ inline copies of file-parsing logic already scattered across `routes.py` — out of scope beyond not adding a 5th copy for the new Dash callback (see Architecture, Dash section).
- Any change to the underlying validation/compliance logic itself (`ComplianceEngine`, `PHIDetector`, etc.) — those are correct; only what's built on top of them is being fixed.

## Architecture

### A. CLI consolidation

The working multi-subcommand structure (`validate`/`dashboard`/`benchmark`/`compliance`/`api`/`demo`) moves into `medical_data_validator/cli.py`, replacing the orphaned single-command version currently there. `pyproject.toml`'s `[project.scripts]` changes from `medical_data_validator_cli:main` to `medical_data_validator.cli:main` — this is also the packaging fix, since only code inside the `medical_data_validator` package is included by `[tool.setuptools.packages.find]`. The root `medical_data_validator_cli.py` becomes a thin shim (`from medical_data_validator.cli import main; if __name__ == "__main__": main()`) so `python medical_data_validator_cli.py ...` still works for anyone invoking it by path.

Per-subcommand fixes:
- `validate` — keeps the orphaned CLI's richer ergonomics (`--required-columns`, `--column-types`, `--format text/json/summary`) already present in `medical_data_validator/cli.py` today; unchanged in shape.
- `dashboard` — `from medical_data_validator.dashboard.app import app` (no such symbol) becomes `from medical_data_validator.dashboard.app import create_dashboard_app; app = create_dashboard_app(); app.run(host=args.host, port=args.port, debug=args.debug)`.
- `api` — currently assumes a FastAPI+uvicorn architecture that doesn't exist. Replaced to mirror `api.py`'s real production path: build the app via `create_dashboard_app()`, apply the same production config (`DEBUG=False`, etc.), and serve via Gunicorn's `StandaloneApplication` pattern already working in `api.py` (falling back to Flask's dev server if `gunicorn` isn't installed, same fallback `api.py` already has) — extracted into a small shared helper both `api.py` and the CLI's `api` subcommand call, rather than duplicated inline twice.
- `benchmark` — `from run_enhanced_benchmarks import main` / `from run_real_benchmarks import main` point at modules that don't exist at those names; corrected to import from the real locations (`benchmarks/run_benchmarks.py`, `benchmarks/benchmark_framework.py`, `benchmarks/real_datasets.py` — exact function names confirmed during implementation).
- `compliance` — `MedicalCodeValidator({}).add_code_type(...)` calls a method that doesn't exist. Replaced with building the `code_columns` dict upfront (`{"diagnosis_code": "icd10", "test_code": "loinc", "procedure_code": "cpt"}` filtered to the requested `--standards`) and constructing `MedicalCodeValidator(code_columns)` directly, matching the class's actual constructor-only API.
- `demo` — `from demo import main` only works with the repo root on `sys.path`. Since `demo.py` is an intentionally repo-local convenience script (not meant to ship inside the installed package), this subcommand keeps working only when run from the repo, but fails with a clear message ("Demo requires running from the repo root") instead of a bare `ImportError` when it can't be found — no attempt to bundle `demo.py` into the package.

### B. Route de-duplication + docs

Both a plain Flask blueprint (`create_api_blueprint()`) and a flask-restx `Api` register handlers at the same `/api/*` paths. Before removing either, every blueprint-only route (if any) gets added to the restx namespace first — this is a verify-then-remove step, not a blind deletion, done during implementation by diffing the two route sets. flask-restx stays (it's already doing real work: the `/v1.2/*` namespace and the auto-generated Swagger UI at `/docs/swagger`); the plain blueprint registration is removed once parity is confirmed.

While in this code: `/v1.2/compliance/check`'s restx handler currently calls `api_compliance_check()` (the legacy v1.0 handler); it's repointed to call `api_v1_2_compliance()` (the real v1.2-specific handler that already exists and is otherwise unreachable through that path).

`API_DOCUMENTATION.md`: every `/api/v1.2/*` example becomes `/v1.2/*`, verified against the live `url_map` rather than assumed correct this time. README's endpoint table gains the `/api/auth/*` and `/api/registry/*` rows it's currently missing.

### C. `is_compliant` / `compliance_risk_level` fields

`MedicalDataValidator.validate()` (core.py) already runs `ComplianceEngine.comprehensive_compliance_validation(df)` when compliance checking is enabled, producing an `overall_risk` value on the `'low'/'medium'/'high'/'critical'` scale (confirmed in `compliance.py`). The top-level API response (and `ValidationResult.to_dict()`) gains two new fields sourced from that existing result: `compliance_risk_level: str` (the raw scale value) and `is_compliant: bool` (`compliance_risk_level not in ("high", "critical")`). `is_valid` itself is untouched — it continues to mean exactly what it means today (no `"error"`-severity issues), so no existing caller's behavior changes.

### D. Finish the Dash UI

`update_output` (`dash_layout.py`) currently ignores its inputs entirely. Rewritten to:
1. Decode `contents` (Dash's `data:<mimetype>;base64,<data>` upload format).
2. Parse into a DataFrame based on `filename`'s extension. A new small helper, `dataframe_from_upload_bytes(filename, raw_bytes) -> pd.DataFrame` (added to `dashboard/utils.py`, next to `generate_charts`), handles this — this is a genuinely new, shared piece of logic the Dash callback needs, not a duplicate of the 4 existing inline copies elsewhere in `routes.py` (those are left as-is, out of scope per Non-goals).
3. Build a validator via the existing `create_validator()` (`routes.py:1132`) from the checklist (`options`: `phi`/`quality`) and dropdown (`profile`) values already in the layout.
4. Run `validator.validate(df)`, then `generate_charts(df, result)` (`dashboard/utils.py`) — the same function the working `/home` HTML dashboard already uses — to get the 4 figure dicts.
5. Return a results summary (issue counts by severity, plus the new `is_compliant`/`compliance_risk_level`) and the 4 figures, mapped by the existing component IDs: `severity-chart` ← `severity_distribution`, `column-chart` ← `column_issues`, `missing-chart` ← `missing_values`, `dtype-chart` ← `data_types`.

No new charting code — `generate_charts()` already returns Plotly-figure-shaped dicts (confirmed: `fig.to_dict()`), directly usable as a `dcc.Graph`'s `figure` prop.

### E. Hygiene

- `print()` calls in `routes.py` (`convert_numpy_types`, `api_validate_data`, `convert_validation_issue_to_dict`) and `monitoring.py` (emoji status lines) become `logger.debug(...)` calls on a module-level logger, silenced by default at the standard `INFO` level `api.py` already configures.
- Delete `.github/workflows/docker-pubish.yml` (typo'd filename, targets `master`); keep `docker-publish.yml` (targets `main`).
- Reinstall the package (`pip install -e .`) after the packaging fix lands, so the local install matches source version — verification step, not a code change.

## Error handling

No new user-facing error paths are introduced except the CLI's clearer `demo`-outside-repo message (§A) and the route-parity check before blueprint removal (§B), which is a build-time/implementation-time safety check, not a runtime one.

## Testing

- CLI: a new test actually imports and invokes `medical_data_validator.cli:main` the way the installed console script would (not just testing the module in isolation, which is exactly the gap that let the packaging bug ship undetected), plus fixed-subcommand tests for `dashboard`/`api`/`benchmark`/`compliance` confirming they no longer raise on construction/import (without necessarily starting a real server in the test).
- Routes: a route-parity test asserting every path the old blueprint served still resolves after its removal; a test confirming `/v1.2/compliance/check` produces the v1.2-shaped response (not the v1.0 one).
- `is_compliant`: a regression test with a bare-SSN dataset — the exact case that motivated this fix — asserting `is_valid: True` (unchanged) alongside `is_compliant: False`, `compliance_risk_level: "critical"`.
- Dash: a test driving `update_output` directly with a small base64-encoded CSV fixture, asserting all 4 returned figures are non-empty dicts and the summary reflects real issue counts (not the placeholder string).
- Existing 350 tests are expected to keep passing largely unchanged, since most already test the code that's becoming canonical (`medical_data_validator/cli.py`) rather than the code being replaced.
