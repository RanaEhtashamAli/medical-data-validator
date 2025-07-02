#!/usr/bin/env python3
"""
Medical Data Validator Demo

This script demonstrates the capabilities of the medical data validator
with real-world healthcare data examples.
"""

import pandas as pd
from medical_data_validator import (
    MedicalDataValidator,
    SchemaValidator,
    PHIDetector,
    DataQualityChecker,
    MedicalCodeValidator,
    RangeValidator,
    DateValidator,
)


def create_sample_medical_data():
    """Create realistic sample medical data for demonstration."""
    return {
        "patient_id": ["P001", "P002", "P003", "P004", "P005"],
        "first_name": ["John", "Jane", "Michael", "Sarah", "David"],
        "last_name": ["Smith", "Johnson", "Williams", "Brown", "Jones"],
        "ssn": ["123-45-6789", "234-56-7890", "345-67-8901", "456-78-9012", "567-89-0123"],
        "date_of_birth": ["1985-03-15", "1990-07-22", "1978-11-08", "1982-04-30", "1988-09-12"],
        "age": [38, 33, 45, 41, 35],
        "gender": ["M", "F", "M", "F", "M"],
        "diagnosis": ["Hypertension", "Diabetes Type 2", "Asthma", "Depression", "Migraine"],
        "icd10_code": ["I10", "E11.9", "J45.909", "F32.1", "G43.909"],
        "temperature": [98.6, 99.2, 97.8, 98.9, 100.1],
        "blood_pressure_systolic": [140, 135, 120, 145, 130],
        "blood_pressure_diastolic": [90, 85, 80, 95, 85],
        "admission_date": ["2024-01-15", "2024-01-20", "2024-01-25", "2024-01-30", "2024-02-05"],
        "email": ["john.smith@email.com", "jane.johnson@email.com", "michael.williams@email.com", 
                 "sarah.brown@email.com", "david.jones@email.com"],
        "phone": ["555-0101", "555-0102", "555-0103", "555-0104", "555-0105"],
        "address": ["123 Main St", "456 Oak Ave", "789 Pine Rd", "321 Elm St", "654 Maple Dr"],
        "zip_code": ["12345", "23456", "34567", "45678", "56789"],
    }


def create_problematic_data():
    """Create data with various issues to demonstrate validation."""
    return {
        "patient_id": ["P001", "P002", None, "P004", "P005"],
        "age": [38, 33, 45, 150, 35],  # Invalid age (150)
        "temperature": [98.6, 99.2, 97.8, 98.9, 110.0],  # Invalid temperature (110)
        "icd10_code": ["I10", "INVALID", "J45.909", "F32.1", "G43.909"],  # Invalid ICD-10
        "date_of_birth": ["1985-03-15", "1990-07-22", "INVALID_DATE", "1982-04-30", "1988-09-12"],
        "duplicate_col": ["A", "A", "A", "A", "A"],  # All same values
        "empty_col": [None, None, None, None, None],  # All null
    }


def demonstrate_basic_validation():
    """Demonstrate basic validation capabilities."""
    print("🔍 Basic Medical Data Validation Demo")
    print("=" * 50)
    
    # Create sample data
    data = create_sample_medical_data()
    df = pd.DataFrame(data)
    
    # Create validator with basic rules
    validator = MedicalDataValidator([
        SchemaValidator(
            required_columns=["patient_id", "age", "diagnosis"],
            column_types={"age": "int", "temperature": "float"}
        ),
        PHIDetector(),
        DataQualityChecker()
    ])
    
    # Validate data
    result = validator.validate(df)
    
    # Display results
    print(f"✅ Data is valid: {result.is_valid}")
    print(f"📊 Total issues found: {len(result.issues)}")
    
    if result.issues:
        print("\n🚨 Issues Found:")
        for i, issue in enumerate(result.issues, 1):
            print(f"  {i}. [{issue.severity.upper()}] {issue.message}")
            if issue.column:
                print(f"     Column: {issue.column}")
    
    return result


def demonstrate_advanced_validation():
    """Demonstrate advanced validation with medical-specific rules."""
    print("\n🏥 Advanced Medical Validation Demo")
    print("=" * 50)
    
    # Create data with issues
    data = create_problematic_data()
    df = pd.DataFrame(data)
    
    # Create comprehensive validator
    validator = MedicalDataValidator([
        # Schema validation
        SchemaValidator(
            required_columns=["patient_id", "age"],
            column_types={"age": "int", "temperature": "float"}
        ),
        
        # PHI detection
        PHIDetector(),
        
        # Data quality
        DataQualityChecker(),
        
        # Medical codes
        MedicalCodeValidator({
            "icd10_code": "icd10"
        }),
        
        # Value ranges
        RangeValidator({
            "age": {"min": 0, "max": 120},
            "temperature": {"min": 95.0, "max": 105.0}
        }),
        
        # Date validation
        DateValidator(
            date_columns=["date_of_birth"],
            min_date="1900-01-01",
            max_date="2024-12-31"
        )
    ])
    
    # Validate data
    result = validator.validate(df)
    
    # Display results
    print(f"✅ Data is valid: {result.is_valid}")
    print(f"📊 Total issues found: {len(result.issues)}")
    
    # Group issues by severity
    errors = result.get_issues_by_severity("error")
    warnings = result.get_issues_by_severity("warning")
    
    if errors:
        print(f"\n❌ Errors ({len(errors)}):")
        for issue in errors:
            print(f"  - {issue.message}")
    
    if warnings:
        print(f"\n⚠️  Warnings ({len(warnings)}):")
        for issue in warnings:
            print(f"  - {issue.message}")
    
    return result


def demonstrate_custom_validation():
    """Demonstrate custom validation rules."""
    print("\n⚙️  Custom Validation Demo")
    print("=" * 50)
    
    # Create sample data
    data = create_sample_medical_data()
    df = pd.DataFrame(data)
    
    # Create validator with custom rules
    validator = MedicalDataValidator()
    
    # Add custom validator for blood pressure logic
    def blood_pressure_validator(df):
        from medical_data_validator.core import ValidationIssue
        
        issues = []
        if "blood_pressure_systolic" in df.columns and "blood_pressure_diastolic" in df.columns:
            # Check if systolic > diastolic
            invalid_bp = df["blood_pressure_systolic"] <= df["blood_pressure_diastolic"]
            if invalid_bp.any():
                count = int(invalid_bp.sum())
                issues.append(
                    ValidationIssue(
                        severity="error",
                        message=f"Found {count} records where systolic pressure <= diastolic pressure",
                        rule_name="BloodPressureValidator"
                    )
                )
        
        return issues
    
    validator.add_validator("blood_pressure", blood_pressure_validator)
    
    # Validate data
    result = validator.validate(df)
    
    print(f"✅ Data is valid: {result.is_valid}")
    print(f"📊 Total issues found: {len(result.issues)}")
    
    if result.issues:
        print("\n🚨 Issues Found:")
        for issue in result.issues:
            print(f"  - [{issue.severity.upper()}] {issue.message}")
    
    return result


def demonstrate_reporting():
    """Demonstrate comprehensive reporting capabilities."""
    print("\n📋 Comprehensive Reporting Demo")
    print("=" * 50)
    
    # Create data with issues
    data = create_problematic_data()
    df = pd.DataFrame(data)
    
    # Create validator
    validator = MedicalDataValidator([
        SchemaValidator(required_columns=["patient_id", "age"]),
        PHIDetector(),
        DataQualityChecker(),
        RangeValidator({"age": {"min": 0, "max": 120}})
    ])
    
    # Validate and get detailed report
    result = validator.validate(df)
    
    # Generate comprehensive report
    report = validator.get_report(result)
    print(report)
    
    # Show summary statistics
    print(f"\n📈 Summary Statistics:")
    print(f"  - Total rows: {result.summary['total_rows']}")
    print(f"  - Total columns: {result.summary['total_columns']}")
    print(f"  - Missing values: {sum(result.summary['missing_values'].values())}")
    print(f"  - Duplicate rows: {result.summary['duplicate_rows']}")
    print(f"  - Validation rules applied: {result.summary['validation_rules_applied']}")
    
    return result


def main():
    """Run all demonstrations."""
    print("🏥 Medical Data Validator - Comprehensive Demo")
    print("=" * 60)
    print("This demo showcases the capabilities of the medical data validator")
    print("for healthcare data quality assurance and PHI/PII detection.\n")
    
    try:
        # Run all demos
        demonstrate_basic_validation()
        demonstrate_advanced_validation()
        demonstrate_custom_validation()
        demonstrate_reporting()
        
        print("\n🎉 Demo completed successfully!")
        print("\n💡 Key Benefits:")
        print("  ✅ Automatic PHI/PII detection")
        print("  ✅ Medical code validation (ICD-10, LOINC, etc.)")
        print("  ✅ Data quality assessment")
        print("  ✅ Custom validation rules")
        print("  ✅ Comprehensive reporting")
        print("  ✅ Healthcare compliance support")
        
    except Exception as e:
        print(f"\n❌ Demo failed: {str(e)}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main() 