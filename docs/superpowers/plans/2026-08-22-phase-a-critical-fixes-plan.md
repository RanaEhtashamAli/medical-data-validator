# medical-data-validator Phase A: Critical Fixes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix the CLI packaging break, de-duplicate/correct the API routes, add compliance-risk visibility the current `is_valid` field hides, finish the placeholder Dash UI, and clean up production logging/CI hygiene.

**Architecture:** The working multi-subcommand CLI logic moves inside the `medical_data_validator` package (fixing packaging at the root); duplicate `/api/*` route registrations are trimmed to the 6 that are true duplicates, leaving the 13 blueprint-only routes untouched; a new `is_compliant`/`compliance_risk_level` pair is read from the compliance report already computed in `validate()`; the Dash callback is wired to the same `create_validator()`/`generate_charts()` functions the working `/home` HTML dashboard already uses.

**Tech Stack:** Flask, flask-restx, Dash/Plotly, pandas, pytest.

**Spec:** `docs/superpowers/specs/2026-08-22-phase-a-critical-fixes-design.md`

## Global Constraints

- `master` is the live default branch (confirmed via `git remote show origin`), not `main` — any branch-targeting fix uses `master`.
- `is_valid`'s existing meaning (no `"error"`-severity issues) is never changed — compliance risk is surfaced through new, separate fields.
- Removing duplicate routes never removes a route that has no restx equivalent — verified per-route in Task 5, not assumed.
- No new charting code for the Dash UI — it reuses `generate_charts()`, the same function `/home` already calls.

---

## Task 1: `is_compliant` / `compliance_risk_level` fields

**Files:**
- Modify: `medical_data_validator/core.py:75-97` (`ValidationResult.to_dict()`)
- Test: `tests/test_core.py`

**Interfaces:**
- Produces: `ValidationResult.to_dict()` gains two keys, `is_compliant: Optional[bool]` and `compliance_risk_level: Optional[str]`, both `None` when no compliance report was computed (compliance checking disabled or it errored).

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_core.py`:

```python
def test_to_dict_includes_compliance_risk_when_present():
    result = ValidationResult(is_valid=True)
    result.summary['compliance_report'] = {'risk_level': 'critical', 'overall_score': 42.0}
    d = result.to_dict()
    assert d['compliance_risk_level'] == 'critical'
    assert d['is_compliant'] is False


def test_to_dict_is_compliant_true_for_low_risk():
    result = ValidationResult(is_valid=True)
    result.summary['compliance_report'] = {'risk_level': 'low', 'overall_score': 95.0}
    d = result.to_dict()
    assert d['is_compliant'] is True


def test_to_dict_compliance_fields_none_when_no_report():
    result = ValidationResult(is_valid=True)
    d = result.to_dict()
    assert d['compliance_risk_level'] is None
    assert d['is_compliant'] is None


def test_bare_ssn_is_valid_true_but_not_compliant():
    """Regression test for the bug that motivated this fix: a bare SSN column
    must not silently read as fully fine just because is_valid is True."""
    import pandas as pd
    from medical_data_validator.core import MedicalDataValidator
    from medical_data_validator.validators import PHIDetector

    validator = MedicalDataValidator(enable_compliance=True)
    validator.add_rule(PHIDetector())
    df = pd.DataFrame({'ssn': ['123-45-6789', '987-65-4321']})
    result = validator.validate(df)
    d = result.to_dict()

    assert d['is_valid'] is True  # unchanged: PHI findings are "warning", not "error"
    assert d['compliance_risk_level'] in ('high', 'critical')
    assert d['is_compliant'] is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_core.py -k "compliance_risk or bare_ssn" -v`
Expected: FAIL — `KeyError: 'compliance_risk_level'`.

- [ ] **Step 3: Add the fields in `ValidationResult.to_dict()`**

In `medical_data_validator/core.py`, replace the `to_dict` method:

```python
    def to_dict(self) -> Dict[str, Any]:
        """Convert the validation result to a dictionary."""
        compliance_report = self.summary.get('compliance_report')
        compliance_risk_level = compliance_report.get('risk_level') if compliance_report else None
        is_compliant = (
            compliance_risk_level not in ('high', 'critical')
            if compliance_risk_level is not None
            else None
        )
        return {
            "is_valid": self.is_valid,
            "is_compliant": is_compliant,
            "compliance_risk_level": compliance_risk_level,
            "total_issues": len(self.issues),
            "error_count": len(self.get_issues_by_severity("error")),
            "warning_count": len(self.get_issues_by_severity("warning")),
            "info_count": len(self.get_issues_by_severity("info")),
            "issues": [
                {
                    "severity": issue.severity,
                    "message": issue.message,
                    "column": issue.column,
                    "row": issue.row,
                    "value": str(issue.value) if issue.value is not None else None,
                    "rule_name": issue.rule_name,
                    "timestamp": issue.timestamp.isoformat(),
                }
                for issue in self.issues
            ],
            "summary": self.summary,
            "timestamp": self.timestamp.isoformat(),
        }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_core.py -k "compliance_risk or bare_ssn" -v`
Expected: PASS.

- [ ] **Step 5: Run the full core test file to check for regressions**

Run: `pytest tests/test_core.py -v`
Expected: all pass (58 tests per the earlier audit).

- [ ] **Step 6: Commit**

```bash
cd "/home/lenovo/Own Projects/medical-data-validator" && git add medical_data_validator/core.py tests/test_core.py
git commit -m "Add is_compliant/compliance_risk_level so PHI risk isn't hidden behind is_valid"
```

---

## Task 2: Hygiene — replace debug print() with logging

**Files:**
- Modify: `medical_data_validator/dashboard/routes.py` (functions: `convert_numpy_types`, `api_validate_data`, `convert_validation_issue_to_dict`)
- Modify: `medical_data_validator/monitoring.py`
- Modify: `medical_data_validator/core.py:317` (the `monitor.record_validation_result` failure handler found during Task 1's investigation — same bug class, same file family)

**Interfaces:** none new — purely internal logging changes, no signature changes.

- [ ] **Step 1: Find every debug print() in the three files**

Run: `grep -n "print(" medical_data_validator/dashboard/routes.py medical_data_validator/monitoring.py medical_data_validator/core.py`

Expected: a list of `print(...)` call sites inside `convert_numpy_types`, `api_validate_data`, `convert_validation_issue_to_dict` (routes.py), the emoji status lines (monitoring.py), and the `Monitoring recording failed` line (core.py:317).

- [ ] **Step 2: Add a module logger and replace each print() with logger.debug()**

For each of the three files, add near the top (if not already present):

```python
import logging
logger = logging.getLogger(__name__)
```

Then replace each `print(f"...")` debug/status line with `logger.debug(f"...")`, and the `core.py:317` failure line specifically:

```python
            except Exception as e:
                logger.debug(f"Monitoring recording failed: {e}")
```

Leave any `print()` that is a CLI's actual user-facing output (none of these three files are CLI-facing) untouched — this task only touches the three files above, not the CLI (Task 4 handles CLI output separately, where prints are the intended UX, not debug spam).

- [ ] **Step 3: Verify no print() calls remain in the three files**

Run: `grep -n "print(" medical_data_validator/dashboard/routes.py medical_data_validator/monitoring.py medical_data_validator/core.py`
Expected: no output (or only non-debug lines you've deliberately decided are real output — there should be none in these three files per the audit).

- [ ] **Step 4: Run the full test suite to confirm nothing broke**

Run: `pytest tests/ -q`
Expected: same pass count as before this task (no test should have been asserting on stdout print output from these specific lines — if one does, convert that assertion to check the logger instead, using `caplog`).

- [ ] **Step 5: Commit**

```bash
cd "/home/lenovo/Own Projects/medical-data-validator" && git add medical_data_validator/dashboard/routes.py medical_data_validator/monitoring.py medical_data_validator/core.py
git commit -m "Replace debug print() spam with logger.debug() in production hot paths"
```

---

## Task 3: CI workflow fix

**Files:**
- Modify: `.github/workflows/docker-publish.yml` (branch trigger)
- Delete: `.github/workflows/docker-pubish.yml`

**Interfaces:** none — CI config only.

- [ ] **Step 1: Change docker-publish.yml's branch trigger to master**

In `.github/workflows/docker-publish.yml`, change:

```yaml
on:
  push:
    branches: [ main ]
```

to:

```yaml
on:
  push:
    branches: [ master ]
```

- [ ] **Step 2: Delete the typo'd duplicate**

```bash
cd "/home/lenovo/Own Projects/medical-data-validator" && rm .github/workflows/docker-pubish.yml
```

- [ ] **Step 3: Confirm exactly one docker-publish workflow remains, targeting master**

Run: `ls .github/workflows/ | grep -i docker` — expect only `docker-publish.yml`.
Run: `grep -A2 "^on:" .github/workflows/docker-publish.yml` — expect `branches: [ master ]`.

- [ ] **Step 4: Commit**

```bash
cd "/home/lenovo/Own Projects/medical-data-validator" && git add .github/workflows/docker-publish.yml
git rm .github/workflows/docker-pubish.yml
git commit -m "Fix CI docker-publish workflow: master is the live branch, remove the typo'd duplicate"
```

---

## Task 4: CLI consolidation and packaging fix

**Files:**
- Modify: `medical_data_validator/cli.py` (replace entirely with the consolidated multi-subcommand CLI)
- Modify: `medical_data_validator_cli.py` (becomes a thin shim)
- Modify: `pyproject.toml` (both `[project.scripts]` and `[project.entry-points."console_scripts"]`)
- Test: `tests/test_cli.py`

**Interfaces:**
- Produces: `medical_data_validator.cli:main` — the console-script entry point, with subcommands `validate`, `dashboard`, `api`, `benchmark`, `compliance`, `demo`.
- Consumes: `create_dashboard_app` (`medical_data_validator.dashboard.app`), `create_api_server` (new small helper, extracted from `api.py`, see Step 3), `benchmarks.run_benchmarks.main`, `MedicalCodeValidator` (`medical_data_validator.validators`).

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_cli.py`:

```python
def test_console_script_module_imports_cleanly():
    """Regression test for the packaging bug: the entry point pyproject.toml
    declares must actually be importable — this is exactly the gap that let
    a broken console script ship undetected."""
    import importlib
    module = importlib.import_module("medical_data_validator.cli")
    assert hasattr(module, "main")


def test_cli_has_all_six_subcommands(capsys):
    from medical_data_validator.cli import main
    import sys
    old_argv = sys.argv
    try:
        sys.argv = ["medical-validator", "--help"]
        try:
            main()
        except SystemExit:
            pass
    finally:
        sys.argv = old_argv
    out = capsys.readouterr().out
    for cmd in ("validate", "dashboard", "api", "benchmark", "compliance", "demo"):
        assert cmd in out


def test_compliance_subcommand_builds_code_validator_without_error(tmp_path):
    """Regression test: the old code called MedicalCodeValidator.add_code_type(),
    which doesn't exist. This must not raise for the default --standards."""
    import pandas as pd
    from medical_data_validator.cli import run_compliance_check
    import argparse

    csv_path = tmp_path / "data.csv"
    pd.DataFrame({"diagnosis_code": ["A00.0"], "test_code": ["1234-5"]}).to_csv(csv_path, index=False)

    args = argparse.Namespace(
        file=str(csv_path),
        standards=["hipaa", "icd10", "loinc"],
        output=None,
    )
    run_compliance_check(args)  # must not raise


def test_dashboard_subcommand_imports_real_symbol():
    """Regression test: the old code imported a module-level `app` that
    doesn't exist in dashboard.app. Must import create_dashboard_app instead."""
    from medical_data_validator.dashboard.app import create_dashboard_app
    app = create_dashboard_app()
    assert app is not None


def test_benchmark_subcommand_imports_real_module():
    """Regression test: the old code imported run_enhanced_benchmarks /
    run_real_benchmarks, neither of which exist anywhere in the repo."""
    from benchmarks.run_benchmarks import main as benchmark_main
    assert callable(benchmark_main)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_cli.py -k "console_script or six_subcommands or compliance_subcommand or dashboard_subcommand or benchmark_subcommand" -v`
Expected: FAIL — `main` in `medical_data_validator/cli.py` is currently the old single-command version with no subcommands, and `run_compliance_check` doesn't exist in that module yet.

- [ ] **Step 3: Extract a shared production-server helper from `api.py`**

`api.py`'s `create_api_server()` and the Gunicorn-vs-dev-server branching in its `main()` are needed by both the root script and the new CLI subcommand. Move this into a new function in `medical_data_validator/dashboard/app.py`, directly below `create_dashboard_app`:

```python
def create_production_app():
    """Build the dashboard app configured for production (non-debug) serving."""
    app = create_dashboard_app()
    app.config.update({
        'TESTING': False,
        'DEBUG': False,
        'JSON_SORT_KEYS': False,
        'JSONIFY_PRETTYPRINT_REGULAR': False,
    })
    return app


def run_production_server(host: str = '0.0.0.0', port: int = 8000, workers: int = 4, debug: bool = False) -> None:
    """Serve the app via Gunicorn if available, else Flask's dev server."""
    app = create_production_app()
    if debug:
        app.config['DEBUG'] = True
        app.run(host=host, port=port, debug=True)
        return
    try:
        import gunicorn.app.base

        class StandaloneApplication(gunicorn.app.base.BaseApplication):
            def __init__(self, app, options=None):
                self.options = options or {}
                self.application = app
                super().__init__()

            def load_config(self):
                for key, value in self.options.items():
                    self.cfg.set(key.lower(), value)

            def load(self):
                return self.application

        options = {
            'bind': f'{host}:{port}',
            'workers': workers,
            'worker_class': 'sync',
            'timeout': 120,
            'keepalive': 2,
            'max_requests': 1000,
            'max_requests_jitter': 100,
            'preload_app': True,
            'access_logfile': '-',
            'error_logfile': '-',
            'loglevel': 'info',
        }
        StandaloneApplication(app, options).run()
    except ImportError:
        app.run(host=host, port=port, debug=False)
```

Update `api.py` to use it (replacing its own duplicated copy):

```python
from medical_data_validator.dashboard.app import run_production_server

def main():
    parser = argparse.ArgumentParser(description='Medical Data Validator API Server')
    parser.add_argument('--host', default='0.0.0.0', help='Host to bind to (default: 0.0.0.0)')
    parser.add_argument('--port', type=int, default=8000, help='Port to bind to (default: 8000)')
    parser.add_argument('--debug', action='store_true', help='Enable debug mode')
    parser.add_argument('--workers', type=int, default=4, help='Number of worker processes (default: 4)')
    args = parser.parse_args()
    run_production_server(host=args.host, port=args.port, workers=args.workers, debug=args.debug)

if __name__ == '__main__':
    main()
```

(Keep `api.py`'s existing logging setup — `logging.basicConfig(...)` — above this; only the server-building logic moves.)

- [ ] **Step 4: Replace `medical_data_validator/cli.py` with the consolidated CLI**

```python
"""
Command-line interface for the Medical Data Validator.

Console script entry point: `medical-validator` (see pyproject.toml
[project.scripts]). This module lives inside the package so it ships in
the built distribution — the CLI previously lived at the repo root
(medical_data_validator_cli.py) and was never included in the sdist,
making the installed console script unusable.
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Optional

import pandas as pd

from . import (
    MedicalDataValidator,
    get_profile,
    list_available_profiles,
    SchemaValidator,
    PHIDetector,
    DataQualityChecker,
)
from .validators import MedicalCodeValidator


def load_data(file_path: str) -> pd.DataFrame:
    """Load data from various file formats."""
    path = Path(file_path)
    if path.suffix.lower() == '.csv':
        return pd.read_csv(file_path)
    elif path.suffix.lower() in ['.xlsx', '.xls']:
        return pd.read_excel(file_path)
    elif path.suffix.lower() == '.json':
        return pd.read_json(file_path)
    elif path.suffix.lower() == '.parquet':
        return pd.read_parquet(file_path)
    else:
        raise ValueError(f"Unsupported file format: {path.suffix}")


def create_validator_from_args(args) -> MedicalDataValidator:
    """Create a validator based on command line arguments."""
    validator = MedicalDataValidator()

    if getattr(args, 'required_columns', None) or getattr(args, 'column_types', None):
        schema_validator = SchemaValidator(
            required_columns=args.required_columns.split(',') if args.required_columns else None,
            column_types=json.loads(args.column_types) if args.column_types else None,
        )
        validator.add_rule(schema_validator)

    if getattr(args, 'detect_phi', False):
        validator.add_rule(PHIDetector())

    if getattr(args, 'quality_checks', False):
        validator.add_rule(DataQualityChecker())

    if getattr(args, 'profile', None):
        profile = get_profile(args.profile)
        if profile:
            return profile.create_validator()
        else:
            print(f"Warning: Profile '{args.profile}' not found. Using basic validation.")

    return validator


def run_validate(args) -> None:
    """Validate a file and print/save the result."""
    if getattr(args, 'verbose', False):
        print(f"Loading data from {args.file}...")

    data = load_data(args.file)

    if args.verbose:
        print(f"Loaded {len(data)} rows and {len(data.columns)} columns")

    validator = create_validator_from_args(args)

    if args.verbose:
        print(f"Running validation with {len(validator.rules)} rules...")

    result = validator.validate(data)

    if args.output:
        output_path = Path(args.output)
        if args.format == "json":
            with open(output_path, 'w') as f:
                json.dump(result.to_dict(), f, indent=2)
            print(f"Results saved to {args.output}")
        else:
            with open(output_path, 'w') as f:
                f.write(validator.get_report(result))
            print(f"Report saved to {args.output}")
    else:
        if args.format == "json":
            print(json.dumps(result.to_dict(), indent=2))
        elif args.format == "summary":
            summary = result.to_dict()
            print("Validation Summary:")
            print(f"  Valid: {summary['is_valid']}")
            print(f"  Compliant: {summary['is_compliant']}")
            print(f"  Total Issues: {summary['total_issues']}")
            print(f"  Errors: {summary['error_count']}")
            print(f"  Warnings: {summary['warning_count']}")
            print(f"  Info: {summary['info_count']}")
        else:
            print(validator.get_report(result))

    sys.exit(0 if result.is_valid else 1)


def run_dashboard(args) -> None:
    """Launch the web dashboard (Flask dev server)."""
    from .dashboard.app import create_dashboard_app
    print("Launching Medical Data Validator Dashboard...")
    print(f"  URL: http://{args.host}:{args.port}")
    print("  Press Ctrl+C to stop")
    app = create_dashboard_app()
    app.run(host=args.host, port=args.port, debug=args.debug)


def run_api_server(args) -> None:
    """Launch the production-style API server (same app as the dashboard)."""
    from .dashboard.app import run_production_server
    print("Launching Medical Data Validator API...")
    print(f"  URL: http://{args.host}:{args.port}")
    print("  Press Ctrl+C to stop")
    run_production_server(host=args.host, port=args.port, debug=args.reload)


def run_benchmark(args) -> None:
    """Run the real benchmark suite."""
    from benchmarks.run_benchmarks import main as benchmark_main
    print("Running benchmarks...")
    benchmark_main()


def run_compliance_check(args) -> None:
    """Check compliance with medical standards."""
    print(f"Checking compliance with standards: {', '.join(args.standards)}")

    data = load_data(args.file)
    validator = MedicalDataValidator()

    if 'hipaa' in args.standards:
        validator.add_rule(PHIDetector())

    code_columns = {}
    if 'icd10' in args.standards:
        code_columns['diagnosis_code'] = 'icd10'
    if 'loinc' in args.standards:
        code_columns['test_code'] = 'loinc'
    if 'cpt' in args.standards:
        code_columns['procedure_code'] = 'cpt'
    if code_columns:
        validator.add_rule(MedicalCodeValidator(code_columns))

    result = validator.validate(data)

    print("\nCompliance Report:")
    for standard in args.standards:
        if standard == 'hipaa':
            phi_issues = [i for i in result.issues if 'PHI' in i.message or 'PII' in i.message]
            print(f"  HIPAA: {'Compliant' if not phi_issues else 'Non-compliant'} ({len(phi_issues)} PHI issues)")
        elif standard in ('icd10', 'loinc', 'cpt'):
            label = standard.upper()
            issues = [i for i in result.issues if label in i.message]
            print(f"  {label}: {'Compliant' if not issues else 'Non-compliant'} ({len(issues)} invalid codes)")

    if args.output:
        report = {
            'standards_checked': args.standards,
            'overall_compliant': result.is_valid,
            'total_issues': len(result.issues),
            'compliance_details': result.to_dict(),
        }
        with open(args.output, 'w') as f:
            json.dump(report, f, indent=2)
        print(f"\nCompliance report saved to: {args.output}")


def run_demo(args) -> None:
    """Run the bundled demo, if available from the repo root."""
    import sys as _sys
    from pathlib import Path as _Path
    repo_root = _Path(__file__).resolve().parent.parent
    demo_path = repo_root / "demo.py"
    if not demo_path.exists():
        print("Demo requires running from the repo root (demo.py not found alongside the package).")
        sys.exit(1)
    if str(repo_root) not in _sys.path:
        _sys.path.insert(0, str(repo_root))
    from demo import main as run_demo_main
    run_demo_main()


def main() -> None:
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Medical Data Validator - Validate healthcare datasets",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  medical-validator validate data.csv --detect-phi --quality-checks
  medical-validator validate data.csv --profile clinical_trials
  medical-validator dashboard
  medical-validator api --port 8000
  medical-validator benchmark
  medical-validator compliance data.csv --standards hipaa icd10 loinc
        """,
    )
    subparsers = parser.add_subparsers(dest='command', help='Available commands')

    validate_parser = subparsers.add_parser('validate', help='Validate medical data files')
    validate_parser.add_argument('file', help='Path to the data file (CSV, Excel, JSON, or Parquet)')
    validate_parser.add_argument('--profile', choices=list_available_profiles(), help='Use a pre-configured validation profile')
    validate_parser.add_argument('--required-columns', help='Comma-separated list of required columns')
    validate_parser.add_argument('--column-types', help='JSON string specifying column types')
    validate_parser.add_argument('--detect-phi', action='store_true', help='Enable PHI/PII detection')
    validate_parser.add_argument('--quality-checks', action='store_true', help='Enable data quality checks')
    validate_parser.add_argument('--output', help='Output file path for results')
    validate_parser.add_argument('--format', choices=['text', 'json', 'summary'], default='text', help='Output format')
    validate_parser.add_argument('--verbose', '-v', action='store_true', help='Verbose output')

    dashboard_parser = subparsers.add_parser('dashboard', help='Launch web dashboard')
    dashboard_parser.add_argument('--host', default='localhost', help='Host to bind to')
    dashboard_parser.add_argument('--port', type=int, default=5000, help='Port to bind to')
    dashboard_parser.add_argument('--debug', action='store_true', help='Enable debug mode')

    api_parser = subparsers.add_parser('api', help='Launch the production-style API server')
    api_parser.add_argument('--host', default='0.0.0.0', help='Host to bind to')
    api_parser.add_argument('--port', type=int, default=8000, help='Port to bind to')
    api_parser.add_argument('--reload', action='store_true', help='Run with the Flask dev server instead of Gunicorn')

    subparsers.add_parser('benchmark', help='Run the performance benchmark suite')

    compliance_parser = subparsers.add_parser('compliance', help='Check compliance with medical standards')
    compliance_parser.add_argument('file', help='Path to data file')
    compliance_parser.add_argument('--standards', nargs='+', choices=['hipaa', 'icd10', 'loinc', 'cpt'], default=['hipaa', 'icd10', 'loinc'], help='Standards to check')
    compliance_parser.add_argument('--output', help='Output file for compliance report')

    demo_parser = subparsers.add_parser('demo', help='Run demonstration with sample data')
    demo_parser.add_argument('--type', choices=['covid19', 'heart_disease', 'breast_cancer'], default='covid19', help='Demo dataset type')

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    try:
        if args.command == 'validate':
            run_validate(args)
        elif args.command == 'dashboard':
            run_dashboard(args)
        elif args.command == 'api':
            run_api_server(args)
        elif args.command == 'benchmark':
            run_benchmark(args)
        elif args.command == 'compliance':
            run_compliance_check(args)
        elif args.command == 'demo':
            run_demo(args)
    except KeyboardInterrupt:
        print("\nOperation cancelled by user.")
        sys.exit(0)
    except SystemExit:
        raise
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
```

Note: `run_validate`'s `sys.exit(...)` call means `test_cli_has_all_six_subcommands`'s `--help` invocation must hit `SystemExit` from argparse itself (before dispatch), which the test already catches — no conflict.

- [ ] **Step 5: Turn the root script into a thin shim**

Replace the full contents of `medical_data_validator_cli.py` with:

```python
#!/usr/bin/env python3
"""
Thin shim for running the CLI by file path (python medical_data_validator_cli.py ...).
The real implementation lives in medical_data_validator/cli.py so it ships inside
the installed package — see pyproject.toml's [project.scripts].
"""
from medical_data_validator.cli import main

if __name__ == "__main__":
    main()
```

- [ ] **Step 6: Fix pyproject.toml's entry points**

In `pyproject.toml`, change both occurrences:

```toml
[project.scripts]
medical-validator = "medical_data_validator.cli:main"

[project.entry-points."console_scripts"]
medical-validator = "medical_data_validator.cli:main"
```

- [ ] **Step 7: Reinstall and run the tests**

```bash
cd "/home/lenovo/Own Projects/medical-data-validator" && pip install -e . --no-deps --force-reinstall
pytest tests/test_cli.py -v
```

Expected: all pass, including the new regression tests.

- [ ] **Step 8: Verify the installed console script actually runs**

```bash
medical-validator --help
```

Expected: prints the help text listing all 6 subcommands, no `ModuleNotFoundError`. This is the exact failure mode being fixed — confirm it directly, not just via pytest.

- [ ] **Step 9: Run the full test suite**

Run: `pytest tests/ -q`
Expected: no new failures.

- [ ] **Step 10: Commit**

```bash
cd "/home/lenovo/Own Projects/medical-data-validator" && git add medical_data_validator/cli.py medical_data_validator_cli.py medical_data_validator/dashboard/app.py api.py pyproject.toml tests/test_cli.py
git commit -m "Fix the broken installed CLI: move it inside the package, fix every subcommand's imports"
```

---

## Task 5: Route de-duplication, v1.2 compliance fix, and doc corrections

**Files:**
- Modify: `medical_data_validator/dashboard/routes.py` (remove 6 duplicated blueprint routes)
- Modify: `medical_data_validator/dashboard/docs.py` (fix `ComplianceCheckV1_2.post()`)
- Modify: `API_DOCUMENTATION.md` (base URL correction)
- Modify: `README.md` (add missing `/api/auth/*`, `/api/registry/*` rows)
- Test: `tests/test_flask_api_routes.py` (or the closest existing route test file — verify exact filename during implementation)

**Interfaces:** none new — route surface correction only. Verified overlap (confirmed by reading both files directly): the plain blueprint (`routes.py:1035-1125`) registers 19 paths; the flask-restx `api` namespace (`docs.py`, `api_docs_legacy`) registers 6 of those same paths (`/health`, `/validate/data`, `/validate/file`, `/compliance/check`, `/profiles`, `/standards`) via `HealthCheckLegacy`, `ValidateDataLegacy`, `ValidateFileLegacy`, `ComplianceCheckLegacy`, `ProfilesLegacy`, `StandardsLegacy`. The other 13 blueprint routes (`/`, `/compliance/v1.2`, `/compliance/templates`, `/compliance/custom-rules` ×3, `/anonymize`, `/analytics`, `/monitoring/*` ×5) have no restx equivalent and must not be removed.

- [ ] **Step 1: Write the failing tests**

Find the existing route-testing file first: `grep -rl "app.test_client\|test_client()" tests/*.py` and use whichever file already tests `/api/health` or similar (per the earlier audit, likely `tests/test_flask_api_*.py`). Append:

```python
def test_no_duplicate_route_registration_for_the_six_shared_paths(client):
    """The 6 paths flask-restx now owns exclusively must resolve exactly once
    at the URL-map level, not twice (blueprint + restx)."""
    from medical_data_validator.dashboard.app import create_dashboard_app
    app = create_dashboard_app()
    rules_by_path = {}
    for rule in app.url_map.iter_rules():
        rules_by_path.setdefault(rule.rule, []).append(rule.endpoint)
    for path in ('/api/health', '/api/validate/data', '/api/validate/file',
                 '/api/compliance/check', '/api/profiles', '/api/standards'):
        assert path in rules_by_path, f"{path} missing entirely"
        assert len(rules_by_path[path]) == 1, f"{path} still registered {len(rules_by_path[path])} times"


def test_blueprint_only_routes_still_present(client):
    """The 13 routes with no restx equivalent must survive the de-dup."""
    r = client.get('/api/monitoring/stats')
    assert r.status_code != 404
    r = client.get('/api/compliance/templates')
    assert r.status_code != 404
    r = client.get('/')
    # root without /api prefix is a different route (home page or similar) —
    # explicitly check the /api blueprint's own root instead:
    from medical_data_validator.dashboard.app import create_dashboard_app
    app = create_dashboard_app()
    paths = {rule.rule for rule in app.url_map.iter_rules()}
    assert '/api/' in paths


def test_v1_2_compliance_check_uses_the_v1_2_handler(client):
    """Regression test: /v1.2/compliance/check was silently calling the
    legacy v1.0 handler instead of the real v1.2 one."""
    resp = client.post('/v1.2/compliance/check', json={
        'data': {'ssn': ['123-45-6789']},
        'standards': ['hipaa'],
    })
    assert resp.status_code == 200
    body = resp.get_json()
    # api_v1_2_compliance's report shape includes 'risk_level' at the top
    # level (per compliance.py's comprehensive_compliance_validation) —
    # the legacy v1.0 handler's shape does not.
    assert 'risk_level' in body or 'compliance_report' in body
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_flask_api_routes.py -k "duplicate_route or blueprint_only or v1_2_compliance" -v` (adjust filename to whatever Step 1 found)
Expected: the duplicate-route test fails (2 registrations for each of the 6 paths); the v1.2 test may pass or fail depending on whether the legacy handler happens to include a similar-looking field — check the actual response body if it passes unexpectedly, and tighten the assertion to something the v1.0 handler's shape definitely lacks.

- [ ] **Step 3: Remove the 6 duplicated routes from the blueprint**

In `medical_data_validator/dashboard/routes.py`, delete these 6 route registrations (lines ~1040-1074, exact numbers will have shifted after Task 1/2's edits — locate by content):

```python
    @api_bp.route('/health', methods=['GET'])
    def api_health_endpoint():
        """Health check endpoint for monitoring."""
        return api_health()

    @api_bp.route('/validate/data', methods=['POST'])
    def api_validate_data_endpoint():
        """Validate JSON data via API."""
        return api_validate_data()

    @api_bp.route('/validate/file', methods=['POST'])
    def api_validate_file_endpoint():
        """Validate uploaded file via API."""
        return api_validate_file()

    @api_bp.route('/compliance/check', methods=['POST'])
    def api_compliance_check_endpoint():
        """Check compliance with medical standards."""
        return api_compliance_check()

    @api_bp.route('/profiles', methods=['GET'])
    def api_profiles_endpoint():
        """Get available validation profiles."""
        return api_profiles()

    @api_bp.route('/standards', methods=['GET'])
    def api_standards_endpoint():
        """Get supported medical standards information."""
        return api_standards()
```

Leave `/` (`api_root_endpoint`) and `/compliance/v1.2` (`api_v1_2_compliance_endpoint`) in place — neither has a restx equivalent. The underlying handler functions (`api_health`, `api_validate_data`, `api_validate_file`, `api_compliance_check`, `api_profiles`, `api_standards`) stay — restx's `HealthCheckLegacy` etc. already call them directly; only the duplicate `@api_bp.route` wrapper functions are deleted.

- [ ] **Step 4: Fix the v1.2 compliance handler wiring**

In `medical_data_validator/dashboard/docs.py`, in `ComplianceCheckV1_2.post()`, change:

```python
        from medical_data_validator.dashboard.routes import api_compliance_check
        resp = api_compliance_check()
```

to:

```python
        from medical_data_validator.dashboard.routes import api_v1_2_compliance
        resp = api_v1_2_compliance()
```

Run the test from Step 1 pointed at `/v1.2/compliance/check` and inspect the actual response body (`resp.get_json()` printed manually if needed) to confirm `compliance_response_model_v1_2`'s `@marshal_with` schema doesn't silently drop fields `api_v1_2_compliance()` returns that `api_compliance_check()` didn't — if the marshal model is missing fields the real v1.2 handler produces, add them to `compliance_response_model_v1_2` in the same file so the documented Swagger schema matches what actually comes back.

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_flask_api_routes.py -v` (or whatever file Step 1 targeted)
Expected: all pass.

- [ ] **Step 6: Fix `API_DOCUMENTATION.md`'s base URL**

Every example using `https://.../api/v1.2/...` or a bare `/api/v1.2/...` path becomes `/v1.2/...`. Find them all:

```bash
grep -n "api/v1.2" API_DOCUMENTATION.md
```

Fix each occurrence in place.

- [ ] **Step 7: Add the missing README rows**

In `README.md`'s API endpoint table, add rows for `/api/auth/token`, `/api/auth/me`, `/api/auth/users`, `/api/registry/datasets` alongside the existing entries, matching that table's existing format.

- [ ] **Step 8: Run the full test suite**

Run: `pytest tests/ -q`
Expected: no new failures.

- [ ] **Step 9: Commit**

```bash
cd "/home/lenovo/Own Projects/medical-data-validator" && git add medical_data_validator/dashboard/routes.py medical_data_validator/dashboard/docs.py API_DOCUMENTATION.md README.md tests/
git commit -m "De-duplicate the 6 truly-shared API routes, fix v1.2 compliance wiring, correct docs"
```

---

## Task 6: Finish the Dash UI

**Files:**
- Modify: `medical_data_validator/dashboard/dash_layout.py`
- Modify: `medical_data_validator/dashboard/utils.py` (new helper)
- Test: `tests/test_dash_layout.py` (new file)

**Interfaces:**
- Consumes: `create_validator` (`medical_data_validator.dashboard.routes`), `generate_charts` (`medical_data_validator.dashboard.utils`).
- Produces: `dataframe_from_upload_bytes(filename: str, raw_bytes: bytes) -> pd.DataFrame` (`medical_data_validator/dashboard/utils.py`), used only by the Dash callback.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_dash_layout.py`:

```python
"""Tests for the Dash callback that validates an uploaded file."""

import base64
import pandas as pd


def _make_upload_contents(df: pd.DataFrame) -> tuple[str, str]:
    csv_bytes = df.to_csv(index=False).encode("utf-8")
    b64 = base64.b64encode(csv_bytes).decode("utf-8")
    return f"data:text/csv;base64,{b64}", "test.csv"


def test_dataframe_from_upload_bytes_parses_csv():
    from medical_data_validator.dashboard.utils import dataframe_from_upload_bytes
    df = pd.DataFrame({"a": [1, 2], "b": ["x", "y"]})
    raw = df.to_csv(index=False).encode("utf-8")
    parsed = dataframe_from_upload_bytes("test.csv", raw)
    assert list(parsed.columns) == ["a", "b"]
    assert len(parsed) == 2


def test_update_output_no_upload_returns_placeholder():
    from medical_data_validator.dashboard.dash_layout import _run_validation_for_upload
    result = _run_validation_for_upload(None, None, ["phi", "quality"], None)
    assert result[0] == "Upload a file to start validation"


def test_update_output_with_real_upload_calls_validator():
    from medical_data_validator.dashboard.dash_layout import _run_validation_for_upload
    df = pd.DataFrame({"ssn": ["123-45-6789", "000-00-0000"], "notes": ["a", "b"]})
    contents, filename = _make_upload_contents(df)

    summary, severity_fig, column_fig, missing_fig, dtype_fig = _run_validation_for_upload(
        contents, filename, ["phi", "quality"], None
    )

    assert "coming soon" not in str(summary).lower()
    assert severity_fig != {}
    assert isinstance(severity_fig, dict) and "data" in severity_fig
    for fig in (column_fig, missing_fig, dtype_fig):
        assert fig != {}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_dash_layout.py -v`
Expected: FAIL — `dataframe_from_upload_bytes` and `_run_validation_for_upload` don't exist yet.

- [ ] **Step 3: Add `dataframe_from_upload_bytes` to `dashboard/utils.py`**

Add near `generate_charts`:

```python
import io


def dataframe_from_upload_bytes(filename: str, raw_bytes: bytes) -> pd.DataFrame:
    """Parse an uploaded file's raw bytes into a DataFrame, dispatching on extension."""
    suffix = filename.lower().rsplit('.', 1)[-1] if '.' in filename else ''
    buf = io.BytesIO(raw_bytes)
    if suffix == 'csv':
        return pd.read_csv(buf)
    elif suffix in ('xlsx', 'xls'):
        return pd.read_excel(buf)
    elif suffix == 'json':
        return pd.read_json(buf)
    else:
        raise ValueError(f"Unsupported file type: {filename}")
```

- [ ] **Step 4: Rewrite `dash_layout.py`'s callback**

Replace the full contents of `medical_data_validator/dashboard/dash_layout.py` from `setup_dash_callbacks` onward:

```python
import base64

from .utils import dataframe_from_upload_bytes, generate_charts


def _run_validation_for_upload(contents, filename, options, profile):
    """Parse an uploaded file, run validation, and build the 4 chart figures.
    Extracted from the Dash callback so it's directly testable without a
    running Dash app."""
    if contents is None:
        return "Upload a file to start validation", {}, {}, {}, {}

    from .routes import create_validator

    _header, b64data = contents.split(',', 1)
    raw_bytes = base64.b64decode(b64data)

    try:
        df = dataframe_from_upload_bytes(filename or '', raw_bytes)
    except Exception as exc:
        return f"Could not parse {filename}: {exc}", {}, {}, {}, {}

    options = options or []
    validator = create_validator(
        detect_phi='phi' in options,
        quality_checks='quality' in options,
        profile=profile,
    )
    result = validator.validate(df)
    result_dict = result.to_dict()

    summary_lines = [
        f"Valid: {result_dict['is_valid']}",
        f"Compliant: {result_dict['is_compliant']}",
        f"Total issues: {result_dict['total_issues']} "
        f"(errors: {result_dict['error_count']}, warnings: {result_dict['warning_count']}, "
        f"info: {result_dict['info_count']})",
    ]
    summary = " | ".join(summary_lines)

    charts = generate_charts(df, result)
    return (
        summary,
        charts.get('severity_distribution', {}),
        charts.get('column_issues', {}),
        charts.get('missing_values', {}),
        charts.get('data_types', {}),
    )


def setup_dash_callbacks(dash_app):
    @dash_app.callback(
        [Output('validation-results', 'children'),
         Output('severity-chart', 'figure'),
         Output('column-chart', 'figure'),
         Output('missing-chart', 'figure'),
         Output('dtype-chart', 'figure')],
        [Input('upload-data', 'contents')],
        [State('upload-data', 'filename'),
         State('validation-options', 'value'),
         State('profile-dropdown', 'value')]
    )
    def update_output(contents, filename, options, profile):
        return _run_validation_for_upload(contents, filename, options, profile)
```

Leave `setup_dash_layout` (the layout definition) unchanged — only `setup_dash_callbacks` and its imports at the top of the file change. Keep the existing `import dash_bootstrap_components as dbc` / `from dash import dcc, html, Input, Output, State` imports at the top of the file (needed by `setup_dash_layout` and the callback decorator).

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_dash_layout.py -v`
Expected: PASS.

- [ ] **Step 6: Manual verification against a running dashboard**

```bash
cd "/home/lenovo/Own Projects/medical-data-validator" && python launch_dashboard.py &
sleep 2
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:5000/dash/
```

Expected: `200`. No browser automation available in this environment — note explicitly that the actual drag-and-drop upload interaction wasn't visually verified, only that the route serves and the underlying callback function (tested directly in Step 5) does real work instead of returning the placeholder string.

```bash
kill %1
```

- [ ] **Step 7: Run the full test suite**

Run: `pytest tests/ -q`
Expected: no new failures.

- [ ] **Step 8: Commit**

```bash
cd "/home/lenovo/Own Projects/medical-data-validator" && git add medical_data_validator/dashboard/dash_layout.py medical_data_validator/dashboard/utils.py tests/test_dash_layout.py
git commit -m "Finish the Dash UI: wire the upload callback to the real validator and charts"
```

---

## Task 7: End-to-end verification and push

**Files:** none (verification only).

- [ ] **Step 1: Full test suite**

Run: `pytest tests/ -v --tb=short 2>&1 | tail -60`
Expected: all tests pass (350+ original tests plus the new regression tests from Tasks 1, 4, 5, 6).

- [ ] **Step 2: Confirm the installed console script works end to end**

```bash
cd "/home/lenovo/Own Projects/medical-data-validator" && pip install -e . --no-deps --force-reinstall
medical-validator --help
echo '{"ssn": ["123-45-6789"], "notes": ["a"]}' | python -c "
import json, sys, pandas as pd
pd.DataFrame(json.load(sys.stdin)).to_json('/tmp/mdv_test.json', orient='records')
"
medical-validator validate /tmp/mdv_test.json --detect-phi --format summary
medical-validator compliance /tmp/mdv_test.json --standards hipaa icd10 loinc
rm -f /tmp/mdv_test.json
```

Expected: `validate` prints a summary including `Compliant: False`; `compliance` runs without an `AttributeError`.

- [ ] **Step 3: Confirm the API server starts and the corrected routes work**

```bash
cd "/home/lenovo/Own Projects/medical-data-validator" && python api.py --debug &
sleep 2
curl -s -o /dev/null -w "health: %{http_code}\n" http://localhost:8000/v1.2/health
curl -s -o /dev/null -w "old-wrong-url (expect 404): %{http_code}\n" http://localhost:8000/api/v1.2/health
curl -s -o /dev/null -w "monitoring (blueprint-only, must survive): %{http_code}\n" http://localhost:8000/api/monitoring/stats
kill %1
```

Expected: `/v1.2/health` returns 200 (confirming `API_DOCUMENTATION.md`'s corrected URL is right); the old documented-but-wrong URL 404s (confirming the doc fix was necessary and the app never served that path); `/api/monitoring/stats` still resolves (confirming the blueprint-only routes survived Task 5's de-dup).

- [ ] **Step 4: Verify no debug print() spam during a real validate call**

```bash
cd "/home/lenovo/Own Projects/medical-data-validator" && python api.py --debug > /tmp/mdv_api.log 2>&1 &
sleep 2
curl -s -X POST http://localhost:8000/api/validate/data -H "Content-Type: application/json" -d '{"data": {"ssn": ["123-45-6789"]}}' > /dev/null
kill %1
sleep 1
grep -c "🔍\|📊\|✅" /tmp/mdv_api.log || echo "0 emoji debug lines found"
rm -f /tmp/mdv_api.log
```

Expected: no (or drastically fewer) emoji-prefixed debug lines in the log compared to before Task 2.

- [ ] **Step 5: Push**

```bash
cd "/home/lenovo/Own Projects/medical-data-validator" && git log --oneline -10
git push origin master
```

---

## Self-Review

**Spec coverage:** CLI consolidation + packaging fix ✓ (Task 4), route de-dup with verified (not assumed) parity ✓ (Task 5), v1.2 compliance miswiring ✓ (Task 5), API doc + README corrections ✓ (Task 5), `is_compliant`/`compliance_risk_level` ✓ (Task 1), Dash UI finished via `generate_charts()` reuse ✓ (Task 6), hygiene (print→logging, CI workflow, version reinstall) ✓ (Tasks 2, 3, 7).

**Placeholder scan:** no TBD/TODO; every step has concrete code or an exact command. The one place a plan step says "verify X during implementation" (Task 5 Step 4's marshal-model check) is a real runtime verification step with a clear pass/fail criterion, not a deferred decision.

**Type consistency:** `dataframe_from_upload_bytes(filename: str, raw_bytes: bytes) -> pd.DataFrame` (Task 6) matches its one call site in `_run_validation_for_upload`. `create_validator(detect_phi, quality_checks, profile, ...)` (Task 6, consumed from `routes.py`) matches the real signature confirmed during investigation (`routes.py:1132`). `run_production_server`/`create_production_app` (Task 4) are defined once in `dashboard/app.py` and consumed identically by both `api.py` and `cli.py`'s `run_api_server`.

**Correction carried from the spec:** the spec originally assumed route parity existed between the blueprint and restx before verification; Task 5 reflects the actual, verified 6-vs-19 split, not the spec's initial assumption.
