# medical-data-validator: Test Coverage Improvement Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task.

**Goal:** Raise test coverage on pre-existing (pre-Phase-B) code from the measured baseline of 77% by adding real, behavior-verifying tests for genuinely untested logic — not padding for a number. Each task targets specific missing-line ranges identified by `pytest --cov=medical_data_validator --cov-report=term-missing` at commit `5b00cde`, characterized for testability before this plan was written (see the gap-analysis notes embedded in each task).

**Non-goals:**
- Do not write tests for `if __name__ == "__main__":` blocks, `except ImportError:` fallback branches that would require breaking the package/dependencies to trigger, or best-effort `except: pass` telemetry-swallowing blocks — these are explicitly out of scope per task.
- Do not attempt to fix the pre-existing, already-documented `run_production_server()` gunicorn config bug (`access_logfile` unrecognized by the installed gunicorn version) — mock around it (test the calling code's branch logic, don't actually invoke gunicorn's `.run()`).
- Do not touch the pre-existing, already-documented `jobs.py` background-worker-vs-test-fixture race condition — tests touching `jobs.py`'s REST routes must follow the established workaround (use `jobs.create_job()` directly for setup rather than `submit_job()`'s real async path, unless a test specifically needs to exercise the worker).
- This plan does not cover `medical_data_validator/dashboard/docs.py` (thin Swagger/OpenAPI wrapper routes that delegate to already-tested business logic) — explicitly deferred as lower-value.

**Global constraints:**
- Every new test must exercise real behavior (real Flask test client requests, real SQLite-backed modules with isolated temp DBs, real function calls) — no mocking of the code under test itself. Mocking is acceptable only for things outside the unit being tested (e.g., `app.run` when testing that `run_production_server` builds the right config, not testing Flask itself).
- Follow each file's existing test-file conventions (isolated temp-DB fixtures for `registry.py`/`jobs.py`/`audit.py`-backed tests, the `/api/auth/token` JWT-acquisition pattern already used in `tests/test_auth.py` for auth-gated endpoints, the `context_value.set(AttributeDict(triggered_inputs=[...]))` idiom already proven in this session for directly testing Dash `@callback` dispatchers).
- After each task, run the full suite via `--junitxml` (not a piped terminal summary — this environment sometimes doesn't print it) and confirm no regressions, then re-run coverage (`pytest --cov=medical_data_validator --cov-report=term-missing`) scoped to the touched file(s) to confirm the targeted lines are now covered.
- Use this project's own virtualenv (`.venv/bin/python3` or `source .venv/bin/activate`) — the shell's default `python3` may be shadowed by an unrelated project's venv.

---

### Task 1: `dashboard/app.py` — production config and error-handling branches

**File:** Modify `medical_data_validator/dashboard/app.py`'s tests — create `tests/test_dashboard_app.py` (new).

**Missing lines to cover (34 total):**
- `create_dashboard_app()`: the `RuntimeError` raised when `SECRET_KEY` is unset AND `FLASK_ENV=production` (line ~38).
- The Flask `@app.errorhandler(Exception)` handler (`handle_exception`, lines ~55-56) — needs a request that raises an unhandled, non-HTTP exception inside a route to trigger it; assert the JSON shape (`success: False`, `error`, `traceback` only when `app.debug`).
- `create_production_app()` (lines ~87-94) — call it, assert `TESTING=False`, `DEBUG=False`, `JSON_SORT_KEYS=False`, `JSONIFY_PRETTYPRINT_REGULAR=False` are all set.
- `run_production_server(debug=True)` branch (lines ~100-103) — mock `Flask.run` (e.g. `unittest.mock.patch.object`) to avoid actually starting a server; assert it's called with `debug=True` and the given host/port.
- `run_production_server(debug=False)`'s `except ImportError` fallback (line ~136-137) — mock `gunicorn.app.base` to be unimportable (or use `sys.modules` patching for `'gunicorn.app.base'`) and confirm it falls back to `app.run(debug=False)`.
- `run_dashboard()` (lines ~141-142) — mock `Flask.run`, confirm it's called with the documented host/port/debug values.

**Explicitly SKIP:** the gunicorn `StandaloneApplication(app, options).run()` call itself (line ~134) — this hits the known pre-existing gunicorn config bug; test only that `StandaloneApplication` is constructed with the right `options` dict (mock `.run()` on it), not that it actually starts. The `if __name__ == "__main__":` sys.path shim (lines 10-12, 145-146) — untestable/pointless via pytest.

- [ ] Write tests in `tests/test_dashboard_app.py`.
- [ ] Run `pytest tests/test_dashboard_app.py -v` — confirm pass.
- [ ] Run full suite via junitxml — confirm no regressions.
- [ ] Run `pytest tests/test_dashboard_app.py --cov=medical_data_validator.dashboard.app --cov-report=term-missing` — confirm the targeted lines are now covered (some SKIP lines will remain missing; that's expected).
- [ ] Commit: `git add medical_data_validator/dashboard/app.py tests/test_dashboard_app.py` (only if any production code needed adjustment — none is expected) `tests/test_dashboard_app.py` and commit with message "Add tests for dashboard/app.py's production config and error-handling branches".

---

### Task 2: `dashboard/routes.py` Part 1 — untested v1.2/compliance/analytics/monitoring/custom-rules/anonymize endpoints

**File:** Extend `tests/test_flask_api_routes.py` or create `tests/test_flask_api_v12_endpoints.py` (new) — implementer's choice of which fits better after checking existing file organization.

**Missing endpoints (all in `medical_data_validator/dashboard/routes.py`, lines ~551-1018), currently zero coverage:**
- `api_v1_2_compliance` — compliance-check endpoint.
- `api_templates` — list available compliance templates.
- `api_custom_rules` (GET) — list custom rules.
- `api_add_custom_rule` — add/update a custom rule (mirrors the Dash Custom Rules page's `_add_custom_rule_from_form`, already tested at the Dash layer — this is the REST layer).
- `api_remove_custom_rule` — remove a custom rule.
- `api_anonymize` — anonymize PHI/PII columns.
- `api_analytics` — analytics report generation.
- `api_monitoring_stats`, `api_monitoring_alerts`, `api_monitoring_acknowledge`, `api_monitoring_resolve` — monitoring subsystem endpoints.
- `api_quality_trends` — quality trend analysis.
- `api_compliance_check` — standalone compliance check.

For each: a happy-path test (valid input → 200 + expected JSON shape), plus whichever of these apply per endpoint — a "no file/no data" 400, a "bad file format" 400, and a forced-internal-exception 500 (only where cheap to trigger; don't force one artificially if it requires heavy mocking for a single endpoint — note it as skipped if so).

- [ ] Write tests covering each endpoint's happy path plus its natural error branches.
- [ ] Run the new test file, then the full suite via junitxml — confirm no regressions.
- [ ] Run coverage scoped to `routes.py`, confirm the targeted line ranges are now covered.
- [ ] Commit with a message identifying which endpoints gained coverage.

---

### Task 3: `dashboard/routes.py` Part 2 — legacy `/upload`, trivial routes, validate-endpoint edge branches, helper functions

**File:** Extend an existing routes test file or create `tests/test_flask_api_misc_routes.py` (new).

**Missing pieces:**
- Legacy `/upload` endpoint (lines ~1369-1431) — full validate-and-chart flow via a small CSV upload through the test client.
- `/health`, `/home`, `/about`, `/profiles` (lines ~1350-1441) — one `client.get()` each, assert 200.
- `api_validate_data`/`api_validate_file` untested edge branches: non-JSON body → `None` data (line ~300-301), DataFrame-construction failure (~372-374), validator-construction failure (~385-387), validation-itself failure (~405-407), compliance-disabled branch (~417); for the file endpoint: oversized file (~465), unsafe filename (~471), malformed `validators` JSON (~481-484).
- Helper function edge branches, testable as direct unit tests with no Flask needed: `generate_compliance_report`/`convert_validation_issue_to_dict`/`convert_numpy_types` (lines ~99-237, ~257-259).
- `dataframe_from_request`'s remaining branches: empty filename (~1165), bad extension (~1168), non-dict JSON payload (~1188, ~1191).

**Explicitly SKIP:** lines 35-41, 1254-1258, 1266-1270, 1278-1282, 1290-1294, 1302-1306, 1314-1318, 1332-1337 (all `except ImportError` route-registration fallbacks — would require breaking the install), and 84-90 (an exotic-type `str()` fallback inside `convert_numpy_types`, edge-case-within-an-edge-case).

- [ ] Write tests for all of the above.
- [ ] Run the new test file, then the full suite via junitxml — confirm no regressions.
- [ ] Run coverage scoped to `routes.py` — confirm meaningful improvement (Tasks 2+3 combined should close the large majority of `routes.py`'s 344-line gap; the explicitly-skipped lines will remain missing).
- [ ] Commit.

---

### Task 4: `security.py` — DataAnonymizer/SecurityAuditor branches, endpoint error paths, filename validation

**File:** Extend `tests/test_security_endpoints.py` or the existing security test file(s) — check what exists first (`tests/test_flask_api_security.py` also exists; pick whichever fits, or create `tests/test_security_module.py` for the pure-unit-test pieces that don't need Flask).

**Missing pieces:**
- `DataAnonymizer.anonymize_column`'s date/address/default-hash branches (lines ~141, 145, 157) and `_mask_anonymization`'s phone/email/else branches (~174, 179-183) and `_generalize_date` (~187-204, essentially the whole method) — pure unit tests, call with different column names/values, no Flask/DB needed.
- `SecurityAuditor._check_file_permissions`'s world-readable/world-writable branches (~262-264, 268-274) — needs a real temp file with `os.chmod` set to permissive bits (e.g. `0o666`/`0o777`), then confirm the check flags it.
- The 3 `/api/security/*` endpoints' `ValueError→400` and generic `Exception→500` branches (~441-444, 459-462, 477-480) — currently only happy paths are tested (from the original Phase B Task 3). Add: a request with no file/data (triggers `dataframe_from_request`'s `ValueError`), and one that forces the inner check to raise (if cheap to arrange; otherwise note as skipped).
- `validate_filename`/`sanitize_filename` (~403-413) — pure unit tests, zero setup.
- `_sanitize_value`'s `pd.isna` early-return (~385-386) — trivial, pass a NaN value.

**Explicitly SKIP:** lines 236-238 (`audit_security`'s per-check exception handler — would need mocking one of 4 internal checks to raise; low value for the setup required).

- [ ] Write tests for all of the above.
- [ ] Run the new/extended test file(s), then the full suite via junitxml — confirm no regressions.
- [ ] Run coverage scoped to `security.py` — confirm improvement.
- [ ] Commit.

---

### Task 5: `cli.py` — output branches, error handling, command dispatch

**File:** Extend `tests/test_cli.py`.

**Missing pieces:**
- `load_data`'s json/parquet format branches (lines ~41, 43) — real files, matching the existing `TestConsolidatedCLI` style.
- `run_validate`'s `--verbose` print branches (~117, 122, 127) and JSON-to-file `--output` branch (~134-136).
- `run_compliance_check`'s CPT-standard branch (~201) and `--output` file-write branch (~218-226).
- `main()`'s command dispatch (~302-311) and top-level exception handling for `FileNotFoundError`/`ValueError`/generic `Exception` (~312-328) — call with a nonexistent file, a malformed `--range` spec, etc.

**Known measurement quirk, not a real gap (don't duplicate a test to "fix" it):** `run_validate`'s summary-format print block (lines ~145-152) already has real behavioral coverage via `TestConsolidatedCLI`'s existing subprocess-based test — it shows as "missing" only because `coverage.py` doesn't trace code executed in a subprocess without extra subprocess-coverage configuration. If you want the number to reflect this, you may add ONE direct (non-subprocess) unit test calling `run_validate()` in-process for this specific branch — optional, not required.

**Explicitly SKIP or low-priority (implementer's judgment, note which you skipped and why in the report):** `run_dashboard`/`run_api_server` (~161-175, would need mocking `app.run`/`run_production_server` for near-zero incremental value since those functions are tested directly in Task 1), `run_demo` (~231-241, launches the bundled `demo.py` with real side effects — at most, test the "demo.py not found" fallback cheaply), `run_benchmark` (~178-182, imports and runs the whole benchmark suite — expensive, skip entirely).

- [ ] Write tests for the TEST items above.
- [ ] Run `tests/test_cli.py`, then the full suite via junitxml — confirm no regressions.
- [ ] Run coverage scoped to `cli.py` — confirm improvement.
- [ ] Commit.

---

### Task 6: `registry.py` — the entire `register_registry_routes` REST API (0% covered)

**File:** Create `tests/test_registry_routes.py` (new).

**Missing:** all 7 endpoints in `register_registry_routes` (lines ~251-365) have zero coverage: list datasets, create dataset, get dataset, update dataset, delete dataset, get run history, record a run. These are auth-gated (`login_required`/`role_required`).

**Setup:**
- Isolated registry DB — same temp-file + `REGISTRY_DB_PATH` swap + `_conn` reset pattern already used in `tests/test_dash_registry_page.py`.
- A JWT token for auth-gated requests — same `/api/auth/token` acquisition pattern already used in `tests/test_auth.py` (`_admin_token(client)`-style helper).
- Use `create_dashboard_app()` + `app.test_client()`, matching the existing Flask API test files' style.

Cover each endpoint's happy path AND its 404 (not found) / 403 (forbidden — non-admin accessing another tenant's dataset, mirroring the tenant-isolation checks this session already found and fixed on the Dash side) branches. This is a fully-built API surface with real security logic (the `g.role != 'admin' and ds.get('tenant') != g.tenant` checks) that has never been exercised by a single test — treat the tenant/role branches as the highest-value part of this task, not an afterthought.

- [ ] Write tests for all 7 endpoints (happy path + 404 + 403 where applicable).
- [ ] Run `tests/test_registry_routes.py`, then the full suite via junitxml — confirm no regressions.
- [ ] Run coverage scoped to `registry.py` — confirm this closes the large majority of its 50-line gap.
- [ ] Commit.

---

### Task 7: `reports.py` — the entire `register_report_routes` REST API (0% covered)

**File:** Create `tests/test_report_routes.py` (new).

**Missing:** `register_report_routes` (lines ~218-306) — export PDF/CSV from a stored job's result (`/api/report/<id>/pdf|csv`) and inline PDF/CSV from a posted result dict (`/api/report/inline/pdf|csv`). Also the PDF compliance-table's skip-keys branch (~160), which should get incidental coverage once a compliance-bearing result is rendered.

**Suggested order (cheaper first):** start with the inline endpoints (`/api/report/inline/pdf`, `/api/report/inline/csv`) — they just need a posted `result_dict` (reuse a fixture shape from `tests/test_reports.py` if one exists). Then the job-based endpoints — seed a completed job via `jobs.create_job()` + a direct `_update_job(..., status='completed', result=...)` call (avoid `submit_job()`'s real async path per the plan's Global Constraints).

- [ ] Write tests for both inline and job-based report export endpoints.
- [ ] Run `tests/test_report_routes.py`, then the full suite via junitxml — confirm no regressions.
- [ ] Run coverage scoped to `reports.py` — confirm improvement (explicitly-skipped reportlab-ImportError lines, ~74-78, will remain missing — that's expected, reportlab is installed and shouldn't be uninstalled to test its absence).
- [ ] Commit.

---

### Task 8: `jobs.py` — the entire `register_job_routes` REST API (0% covered)

**File:** Create `tests/test_job_routes.py` (new).

**Missing:** `register_job_routes` (lines ~257-301) — submit/list/get job endpoints, auth-gated, same 404/403 tenant-isolation pattern as Task 6's registry routes.

**Critical constraint — the known race condition:** this session already found and documented a real, unfixed race condition between `jobs.py`'s background worker thread and test-fixture DB teardown, which can segfault the test process. New tests here MUST follow the established workaround: use `jobs.create_job()` directly (synchronous, no worker thread) for test setup wherever a test doesn't specifically need to exercise the real async submit-and-process flow. If a test for the submit endpoint specifically needs to prove a real job gets queued and processed, that's acceptable ONLY as a single, minimal test (not several) — check `tests/test_dash_jobs_page.py`'s existing `test_submit_job_from_form_then_appears_in_list` for the established safe-ish polling pattern, and do not add multiple new tests that each start a fresh real async job, since each one increases the probability of triggering the segfault. If in doubt, prefer testing the submit endpoint's request-validation branches (bad `job_type`, malformed payload) which don't need a real worker at all.

**Explicitly SKIP:** lines ~246-252 (`_celery_available()` — optional integration, celery isn't installed in this environment; forcing the ImportError-False branch has near-zero value).

- [ ] Write tests for the 3 endpoints (submit/list/get), minimizing real async job submissions per the constraint above.
- [ ] Run `tests/test_job_routes.py` at least 3 times in a row to confirm no flakiness/segfaults before considering this task done.
- [ ] Run the full suite via junitxml — confirm no regressions.
- [ ] Run coverage scoped to `jobs.py` — confirm improvement.
- [ ] Commit, and explicitly note in the commit message / report if you deliberately limited real-async-job tests to avoid the known race.

---

### Task 9: `auth.py` — security-critical `login_required`/`role_required` decorator branches

**File:** Extend `tests/test_auth.py`.

**Missing (security-critical — this is the actual auth gate protecting every endpoint in Tasks 6-8):**
- `login_required`'s no-token branch (~111), expired/invalid-token branch (~114-117), inactive-user branch (~122), API-key-tenant-mismatch branch (~131).
- `role_required`'s insufficient-role 403 branch (~146).
- `_extract_token`/`_extract_tenant` (~92, 99-101).
- `_verify_password`'s malformed-hash `except` branch (~48-49).

Use a real Flask test client hitting any already-existing protected route (e.g. one of `auth.py`'s own `/api/auth/users` endpoints, or one from Tasks 6-8 once those land — this task can be done independently and doesn't need to wait) with a missing/expired/malformed Authorization header, an inactive user's valid token, and a wrong-role user's valid token.

- [ ] Write tests for each decorator branch listed above.
- [ ] Run `tests/test_auth.py`, then the full suite via junitxml — confirm no regressions.
- [ ] Run coverage scoped to `auth.py` — confirm improvement.
- [ ] Commit.

---

### Task 10: `dashboard/pages/auth.py` — untested `@callback` dispatchers

**File:** Extend `tests/test_dash_auth_page.py`.

**Missing:** `_handle_user_actions`/`_handle_tenant_actions` (lines ~71-97) have zero direct dispatcher tests — this is the exact same "untested `@callback` dispatcher" bug class the Phase B.1 addendum's final review already found and fixed on 4 other pages (Registry, Jobs, Custom Rules — and Audit's helper was already tested), just never back-applied to the Auth page (built in the original Phase B Task 11, before that convention existed).

**Required approach:** use the identical `dash._callback_context.context_value.set(AttributeDict(triggered_inputs=[{'prop_id': '<button-id>.n_clicks'}]))` idiom already proven working multiple times this session (see `tests/test_dash_registry_page.py`'s dispatcher tests for the exact pattern, added in the Phase B.1 fix wave). Test that create-user routes to the right message output (not the tenant one), deactivate routes correctly, and create-tenant routes correctly — mirroring the routing-specificity standard already established (assert the OTHER outputs stay empty/`dash.no_update`, not just that "some" output has content).

- [ ] Write dispatcher tests for `_handle_user_actions` and `_handle_tenant_actions`.
- [ ] Run `tests/test_dash_auth_page.py`, then the full suite via junitxml — confirm no regressions.
- [ ] Run coverage scoped to `dashboard/pages/auth.py` — confirm improvement.
- [ ] Commit.

---

### Task 11: `dashboard/utils.py` — file-format and chart-generation branches

**File:** Extend whichever existing test file covers `dashboard/utils.py` (check `tests/test_dash_layout.py` or create `tests/test_dashboard_utils.py`).

**Missing (all easy, no mocking needed):**
- `load_data`'s xlsx/parquet/unsupported-format branches (lines ~56, 59-62).
- `dataframe_from_upload_bytes`'s xlsx/json/unsupported-format branches (~70-75).
- `generate_charts`'s "no issues" pie-chart branch (~109) and "missing values present" bar-chart branch (~135-141) — validate data with/without issues and with/without missing values to hit both branches.

**Explicitly SKIP:** lines 19-21, 26-28 (import fallbacks — plotly is installed, not worth breaking to test), 83 (a px-is-None branch depending on the same import fallback), 168 (a zero-column DataFrame edge case, practically unreachable in this app's flow).

- [ ] Write tests for the TEST items above.
- [ ] Run the test file, then the full suite via junitxml — confirm no regressions.
- [ ] Run coverage scoped to `dashboard/utils.py` — confirm improvement.
- [ ] Commit.

---

### Task 12: `dashboard/pages/validate.py` — `_download_report` callback

**File:** Extend `tests/test_dash_layout.py`.

**Missing:** `_download_report` (lines ~175-181) has zero tests — flagged as a known gap during the original Phase B Task 8 review, now confirmed as a real, still-open coverage hole. Also `_run_validation_for_upload`'s parse-failure branch (~120-121) if not already covered elsewhere (check first — Task 6/8's existing tests may already hit this).

Test all three of `_download_report`'s branches: the PDF button path (assert `dcc.send_bytes`-shaped output with the right filename), the CSV button path (assert `dcc.send_string`-shaped output), and the `not result_dict` → `dash.no_update` guard (e.g. before any validation has run).

- [ ] Write tests for `_download_report`'s 3 branches, plus the parse-failure branch if genuinely uncovered.
- [ ] Run `tests/test_dash_layout.py`, then the full suite via junitxml — confirm no regressions.
- [ ] Run coverage scoped to `dashboard/pages/validate.py` — confirm improvement.
- [ ] Commit.

---

### Task 13: `core.py` — `MedicalDataValidator`'s untested public API methods

**File:** Extend `tests/test_core.py` (or wherever `MedicalDataValidator`'s other unit tests live — check first).

**Missing:**
- `start_monitoring`/`stop_monitoring` (lines ~205, 210-211).
- `add_custom_compliance_rule`/`remove_custom_compliance_rule`/`get_custom_compliance_rules` (~232, 249).
- `get_available_compliance_templates` (~255).
- `validate()`'s compliance-engine and analytics-engine exception-handling branches (~324-331, 338-344) — mock the relevant engine (`ComplianceEngine`/`AdvancedAnalytics` instance) to raise, confirm `validate()` degrades gracefully rather than crashing.
- `anonymize()`'s bad-data-type `ValueError` (~414) and `DataAnonymizer`-unavailable `RuntimeError` (~402).

**Not a real gap — do NOT write a duplicate test:** lines 26-39 (the shared v1.2-import `except ImportError` fallback) show as "missing" in the coverage report despite `tests/test_security_flask_optional_import.py` (added this session, during the original Phase B final review's fix wave) already exercising exactly this path via `sys.modules` manipulation + `builtins.__import__` patching. This looks like a `coverage.py` measurement quirk with that test's re-import technique not being credited to this file, not an untested behavior. If you have five minutes, a quick look at why `coverage.py` isn't crediting it would be a nice bonus, but it's not required and don't spend the task's main effort here.

**Explicitly SKIP:** lines 351-352, 378-379, 447-448 (best-effort audit-logging `except: pass` blocks wrapping optional telemetry — deliberately fail-silent by design; testing them mostly means testing that failure is swallowed, which is already implied by the code's own comment/intent).

- [ ] Write tests for the TEST items above.
- [ ] Run `tests/test_core.py`, then the full suite via junitxml — confirm no regressions.
- [ ] Run coverage scoped to `core.py` — confirm improvement.
- [ ] Commit.

---

### Task 14: Final verification

**Files:** none (verification only).

- [ ] Run the full suite via junitxml — confirm 0 errors, 0 failures, 0 skipped, and the total test count reflects all 13 tasks' additions.
- [ ] Run `pytest --cov=medical_data_validator --cov-report=term-missing` for the whole package — report the new overall percentage, and list any file that's still notably low despite this plan's efforts (with a one-line reason, e.g. "docs.py — explicitly out of scope").
- [ ] Confirm no test flakiness by running the full suite 2-3 times in a row (this plan touched `jobs.py`'s test surface, which has a known race — extra scrutiny here is warranted).
- [ ] Push (pending explicit user go-ahead, same convention as the Phase B/B.1 plans).
