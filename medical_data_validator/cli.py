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
    RangeValidator,
    DateValidator,
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

    # Add schema validation if specified
    if getattr(args, 'required_columns', None) or getattr(args, 'column_types', None):
        schema_validator = SchemaValidator(
            required_columns=args.required_columns.split(',') if args.required_columns else None,
            column_types=json.loads(args.column_types) if args.column_types else None,
        )
        validator.add_rule(schema_validator)

    # Add PHI detection
    if getattr(args, 'detect_phi', False):
        validator.add_rule(PHIDetector())

    # Add data quality checks
    if getattr(args, 'quality_checks', False):
        validator.add_rule(DataQualityChecker())

    # Add range checks
    if getattr(args, 'range', None):
        ranges = {}
        for spec in args.range:
            column, min_str, max_str = spec.split(':', 2)
            ranges[column] = {'min': float(min_str), 'max': float(max_str)}
        validator.add_rule(RangeValidator(ranges=ranges))

    # Add date column checks
    if getattr(args, 'date_column', None):
        validator.add_rule(DateValidator(
            date_columns=args.date_column,
            min_date=getattr(args, 'min_date', None),
            max_date=getattr(args, 'max_date', None),
        ))

    # Add medical code column checks
    if getattr(args, 'code_column', None):
        code_columns = {}
        for spec in args.code_column:
            column, standard = spec.split(':', 1)
            code_columns[column] = standard
        validator.add_rule(MedicalCodeValidator(code_columns))

    # Add profile-based validators
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
    subparsers = parser.add_subparsers(dest='command', help='Available commands', required=True)

    validate_parser = subparsers.add_parser('validate', help='Validate medical data files')
    validate_parser.add_argument('file', help='Path to the data file (CSV, Excel, JSON, or Parquet)')
    validate_parser.add_argument('--profile', choices=list_available_profiles(), help='Use a pre-configured validation profile')
    validate_parser.add_argument('--required-columns', help='Comma-separated list of required columns')
    validate_parser.add_argument('--column-types', help='JSON string specifying column types')
    validate_parser.add_argument('--range', action='append', metavar='COLUMN:MIN:MAX', help='Numeric range check (repeatable), e.g. --range age:0:120')
    validate_parser.add_argument('--date-column', action='append', metavar='COLUMN', help='Column to validate as a date (repeatable)')
    validate_parser.add_argument('--min-date', help='Minimum allowed date, applies to all --date-column columns')
    validate_parser.add_argument('--max-date', help='Maximum allowed date, applies to all --date-column columns')
    validate_parser.add_argument('--code-column', action='append', metavar='COLUMN:STANDARD', help='Medical code column check (repeatable), e.g. --code-column diagnosis_code:icd10')
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
    except FileNotFoundError:
        print(f"Error: File '{getattr(args, 'file', '?')}' not found.", file=sys.stderr)
        sys.exit(1)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected error: {e}", file=sys.stderr)
        if getattr(args, 'verbose', False):
            import traceback
            traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
