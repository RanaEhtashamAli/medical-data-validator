"""
Command-line interface for the Medical Data Validator.

This module provides a CLI for validating medical datasets from the command line.
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
    if args.required_columns or args.column_types:
        schema_validator = SchemaValidator(
            required_columns=args.required_columns.split(',') if args.required_columns else None,
            column_types=json.loads(args.column_types) if args.column_types else None,
        )
        validator.add_rule(schema_validator)
    
    # Add PHI detection
    if args.detect_phi:
        validator.add_rule(PHIDetector())
    
    # Add data quality checks
    if args.quality_checks:
        validator.add_rule(DataQualityChecker())
    
    # Add profile-based validators
    if args.profile:
        profile = get_profile(args.profile)
        if profile:
            return profile.create_validator()
        else:
            print(f"Warning: Profile '{args.profile}' not found. Using basic validation.")
    
    return validator


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Medical Data Validator - Validate healthcare datasets",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Basic validation with PHI detection
  medical-validator data.csv --detect-phi --quality-checks
  
  # Use a pre-configured profile
  medical-validator data.csv --profile clinical_trials
  
  # Custom schema validation
  medical-validator data.csv --required-columns "patient_id,age" --column-types '{"age": "int"}'
  
  # Output to JSON file
  medical-validator data.csv --output results.json --format json
  
Available profiles:
  clinical_trials  - Clinical trial data validation
  ehr             - Electronic health records validation
  imaging         - Medical imaging metadata validation
  lab             - Laboratory data validation
        """
    )
    
    parser.add_argument(
        "file",
        help="Path to the data file (CSV, Excel, JSON, or Parquet)"
    )
    
    parser.add_argument(
        "--profile",
        choices=list_available_profiles(),
        help="Use a pre-configured validation profile"
    )
    
    parser.add_argument(
        "--required-columns",
        help="Comma-separated list of required columns"
    )
    
    parser.add_argument(
        "--column-types",
        help="JSON string specifying column types (e.g., '{\"age\": \"int\"}')"
    )
    
    parser.add_argument(
        "--detect-phi",
        action="store_true",
        help="Enable PHI/PII detection"
    )
    
    parser.add_argument(
        "--quality-checks",
        action="store_true",
        help="Enable data quality checks"
    )
    
    parser.add_argument(
        "--output",
        help="Output file path for results"
    )
    
    parser.add_argument(
        "--format",
        choices=["text", "json", "summary"],
        default="text",
        help="Output format (default: text)"
    )
    
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Verbose output"
    )
    
    args = parser.parse_args()
    
    try:
        # Load data
        if args.verbose:
            print(f"Loading data from {args.file}...")
        
        data = load_data(args.file)
        
        if args.verbose:
            print(f"Loaded {len(data)} rows and {len(data.columns)} columns")
        
        # Create validator
        validator = create_validator_from_args(args)
        
        if args.verbose:
            print(f"Running validation with {len(validator.rules)} rules...")
        
        # Run validation
        result = validator.validate(data)
        
        # Output results
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
                print(f"Validation Summary:")
                print(f"  Valid: {summary['is_valid']}")
                print(f"  Total Issues: {summary['total_issues']}")
                print(f"  Errors: {summary['error_count']}")
                print(f"  Warnings: {summary['warning_count']}")
                print(f"  Info: {summary['info_count']}")
            else:
                print(validator.get_report(result))
        
        # Exit with appropriate code
        sys.exit(0 if result.is_valid else 1)
        
    except FileNotFoundError:
        print(f"Error: File '{args.file}' not found.", file=sys.stderr)
        sys.exit(1)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected error: {e}", file=sys.stderr)
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main() 