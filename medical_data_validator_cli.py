#!/usr/bin/env python3
"""
Medical Data Validator - Main Entry Point

A comprehensive healthcare data validation tool with HIPAA compliance,
supporting ICD-10, LOINC, CPT, and other medical standards.

Author: Rana Ehtasham Ali
Email: ranaehtashamali1@gmail.com
"""

import argparse
import sys
import os
from pathlib import Path

def main():
    """Main entry point for Medical Data Validator."""
    parser = argparse.ArgumentParser(
        description="Medical Data Validator - Healthcare Data Validation Tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Validate a CSV file with PHI detection
  python medical_data_validator_cli.py validate data.csv --detect-phi

  # Run web dashboard
  python medical_data_validator_cli.py dashboard

  # Run benchmarks
  python medical_data_validator_cli.py benchmark

  # Check compliance
  python medical_data_validator_cli.py compliance data.csv --standards icd10,loinc,hipaa
        """
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Validate command
    validate_parser = subparsers.add_parser('validate', help='Validate medical data files')
    validate_parser.add_argument('file', help='Path to data file (CSV, Excel, JSON)')
    validate_parser.add_argument('--detect-phi', action='store_true', help='Enable PHI/PII detection')
    validate_parser.add_argument('--quality-checks', action='store_true', default=True, help='Enable data quality checks')
    validate_parser.add_argument('--profile', choices=['clinical_trials', 'ehr', 'lab', 'pharmacy'], help='Validation profile')
    validate_parser.add_argument('--output', help='Output file for results')
    
    # Dashboard command
    dashboard_parser = subparsers.add_parser('dashboard', help='Launch web dashboard')
    dashboard_parser.add_argument('--host', default='localhost', help='Host to bind to')
    dashboard_parser.add_argument('--port', type=int, default=5000, help='Port to bind to')
    dashboard_parser.add_argument('--debug', action='store_true', help='Enable debug mode')
    
    # Benchmark command
    benchmark_parser = subparsers.add_parser('benchmark', help='Run performance benchmarks')
    benchmark_parser.add_argument('--type', choices=['enhanced', 'real'], default='enhanced', help='Benchmark type')
    benchmark_parser.add_argument('--output-dir', help='Output directory for results')
    
    # Compliance command
    compliance_parser = subparsers.add_parser('compliance', help='Check compliance with medical standards')
    compliance_parser.add_argument('file', help='Path to data file')
    compliance_parser.add_argument('--standards', nargs='+', 
                                 choices=['hipaa', 'icd10', 'loinc', 'cpt', 'fhir', 'omop'],
                                 default=['hipaa', 'icd10', 'loinc'], 
                                 help='Standards to check')
    compliance_parser.add_argument('--output', help='Output file for compliance report')
    
    # API command
    api_parser = subparsers.add_parser('api', help='Launch REST API server')
    api_parser.add_argument('--host', default='0.0.0.0', help='Host to bind to')
    api_parser.add_argument('--port', type=int, default=8000, help='Port to bind to')
    api_parser.add_argument('--reload', action='store_true', help='Enable auto-reload')
    
    # Demo command
    demo_parser = subparsers.add_parser('demo', help='Run demonstration with sample data')
    demo_parser.add_argument('--type', choices=['covid19', 'heart_disease', 'breast_cancer'], 
                           default='covid19', help='Demo dataset type')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    try:
        if args.command == 'validate':
            run_validation(args)
        elif args.command == 'dashboard':
            run_dashboard(args)
        elif args.command == 'benchmark':
            run_benchmark(args)
        elif args.command == 'compliance':
            run_compliance_check(args)
        elif args.command == 'api':
            run_api_server(args)
        elif args.command == 'demo':
            run_demo(args)
        else:
            print(f"Unknown command: {args.command}")
            sys.exit(1)
            
    except KeyboardInterrupt:
        print("\nOperation cancelled by user.")
        sys.exit(0)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)

def run_validation(args):
    """Run data validation."""
    from medical_data_validator.core import MedicalDataValidator
    from medical_data_validator.validators import PHIDetector, DataQualityChecker
    import pandas as pd
    
    print(f"🔍 Validating medical data: {args.file}")
    
    # Load data
    try:
        if args.file.endswith('.csv'):
            data = pd.read_csv(args.file)
        elif args.file.endswith(('.xlsx', '.xls')):
            data = pd.read_excel(args.file)
        elif args.file.endswith('.json'):
            data = pd.read_json(args.file)
        else:
            raise ValueError(f"Unsupported file format: {args.file}")
    except Exception as e:
        print(f"❌ Error loading file: {e}")
        return
    
    # Create validator
    validator = MedicalDataValidator()
    
    if args.detect_phi:
        validator.add_rule(PHIDetector())
        print("✅ PHI/PII detection enabled")
    
    if args.quality_checks:
        validator.add_rule(DataQualityChecker())
        print("✅ Data quality checks enabled")
    
    # Run validation
    result = validator.validate(data)
    
    # Display results
    print(f"\n📊 Validation Results:")
    print(f"   Valid: {'✅' if result.is_valid else '❌'}")
    print(f"   Total Issues: {len(result.issues)}")
    print(f"   Errors: {len([i for i in result.issues if i.severity == 'error'])}")
    print(f"   Warnings: {len([i for i in result.issues if i.severity == 'warning'])}")
    print(f"   Info: {len([i for i in result.issues if i.severity == 'info'])}")
    
    if result.issues:
        print(f"\n🚨 Issues Found:")
        for issue in result.issues[:10]:  # Show first 10 issues
            print(f"   {issue.severity.upper()}: {issue.message}")
        if len(result.issues) > 10:
            print(f"   ... and {len(result.issues) - 10} more issues")
    
    # Save results if output specified
    if args.output:
        import json
        with open(args.output, 'w') as f:
            json.dump(result.to_dict(), f, indent=2)
        print(f"\n💾 Results saved to: {args.output}")

def run_dashboard(args):
    """Launch web dashboard."""
    print(f"🌐 Launching Medical Data Validator Dashboard...")
    print(f"   URL: http://{args.host}:{args.port}")
    print(f"   Press Ctrl+C to stop")
    
    try:
        from medical_data_validator.dashboard.app import app
        app.run(host=args.host, port=args.port, debug=args.debug)
    except ImportError as e:
        print(f"❌ Error: Web dashboard dependencies not installed")
        print("   Install with: pip install medical-data-validator[web]")
        print("   Or install all features: pip install medical-data-validator[all]")
        sys.exit(1)

def run_benchmark(args):
    """Run performance benchmarks."""
    print(f"⚡ Running {args.type} benchmarks...")
    
    if args.type == 'enhanced':
        try:
            from run_enhanced_benchmarks import main as run_enhanced
            run_enhanced()
        except ImportError:
            print("❌ Enhanced benchmarks not available")
    else:
        try:
            from run_real_benchmarks import main as run_real
            run_real()
        except ImportError:
            print("❌ Real data benchmarks not available")

def run_compliance_check(args):
    """Check compliance with medical standards."""
    print(f"🏥 Checking compliance with standards: {', '.join(args.standards)}")
    
    from medical_data_validator.core import MedicalDataValidator
    from medical_data_validator.validators import PHIDetector, DataQualityChecker, MedicalCodeValidator
    import pandas as pd
    
    # Load data
    try:
        if args.file.endswith('.csv'):
            data = pd.read_csv(args.file)
        elif args.file.endswith(('.xlsx', '.xls')):
            data = pd.read_excel(args.file)
        elif args.file.endswith('.json'):
            data = pd.read_json(args.file)
        else:
            raise ValueError(f"Unsupported file format: {args.file}")
    except Exception as e:
        print(f"❌ Error loading file: {e}")
        return
    
    # Create validator with compliance checks
    validator = MedicalDataValidator()
    
    if 'hipaa' in args.standards:
        validator.add_rule(PHIDetector())
    
    if 'icd10' in args.standards or 'loinc' in args.standards or 'cpt' in args.standards:
        code_validator = MedicalCodeValidator({})
        if 'icd10' in args.standards:
            code_validator.add_code_type("diagnosis_code", "icd10")
        if 'loinc' in args.standards:
            code_validator.add_code_type("test_code", "loinc")
        if 'cpt' in args.standards:
            code_validator.add_code_type("procedure_code", "cpt")
        validator.add_rule(code_validator)
    
    # Run validation
    result = validator.validate(data)
    
    # Generate compliance report
    print(f"\n📋 Compliance Report:")
    for standard in args.standards:
        if standard == 'hipaa':
            phi_issues = [i for i in result.issues if 'PHI' in i.message or 'PII' in i.message]
            compliant = len(phi_issues) == 0
            print(f"   HIPAA: {'✅ Compliant' if compliant else '❌ Non-compliant'} ({len(phi_issues)} PHI issues)")
        
        elif standard == 'icd10':
            icd_issues = [i for i in result.issues if 'ICD-10' in i.message]
            compliant = len(icd_issues) == 0
            print(f"   ICD-10: {'✅ Compliant' if compliant else '❌ Non-compliant'} ({len(icd_issues)} invalid codes)")
        
        elif standard == 'loinc':
            loinc_issues = [i for i in result.issues if 'LOINC' in i.message]
            compliant = len(loinc_issues) == 0
            print(f"   LOINC: {'✅ Compliant' if compliant else '❌ Non-compliant'} ({len(loinc_issues)} invalid codes)")
        
        elif standard == 'cpt':
            cpt_issues = [i for i in result.issues if 'CPT' in i.message]
            compliant = len(cpt_issues) == 0
            print(f"   CPT: {'✅ Compliant' if compliant else '❌ Non-compliant'} ({len(cpt_issues)} invalid codes)")
    
    # Save report if output specified
    if args.output:
        import json
        report = {
            'standards_checked': args.standards,
            'overall_compliant': result.is_valid,
            'total_issues': len(result.issues),
            'compliance_details': result.to_dict()
        }
        with open(args.output, 'w') as f:
            json.dump(report, f, indent=2)
        print(f"\n💾 Compliance report saved to: {args.output}")

def run_api_server(args):
    """Launch REST API server."""
    print(f"🚀 Launching Medical Data Validator API...")
    print(f"   URL: http://{args.host}:{args.port}")
    print(f"   Documentation: http://{args.host}:{args.port}/docs")
    print(f"   Press Ctrl+C to stop")
    
    try:
        from medical_data_validator.api import app
        import uvicorn
        uvicorn.run(app, host=args.host, port=args.port, reload=args.reload)
    except ImportError as e:
        print(f"❌ Error: REST API dependencies not installed")
        print("   Install with: pip install medical-data-validator[api]")
        print("   Or install all features: pip install medical-data-validator[all]")
        sys.exit(1)

def run_demo(args):
    """Run demonstration with sample data."""
    print(f"🎯 Running demo with {args.type} dataset...")
    
    try:
        from demo import main as run_demo_main
        run_demo_main()
    except ImportError:
        print("❌ Demo not available")

if __name__ == "__main__":
    main() 