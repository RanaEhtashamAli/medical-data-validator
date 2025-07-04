#!/usr/bin/env python3
"""
Test script for Medical Data Validator v1.2 Advanced Compliance Features
"""

import pandas as pd
from medical_data_validator.core import MedicalDataValidator
from medical_data_validator.validators import DataQualityChecker, PHIDetector

def test_v1_2_compliance():
    """Test the new v1.2 compliance features."""
    
    print("🧪 Testing Medical Data Validator v1.2 - Advanced Compliance Features")
    print("=" * 70)
    
    # Create sample medical data with PHI and compliance issues
    sample_data = {
        'patient_name': ['John Smith', 'Jane Doe', 'Bob Johnson', 'Alice Brown'],
        'ssn': ['123-45-6789', '987-65-4321', '111-22-3333', '444-55-6666'],
        'email': ['john.smith@email.com', 'jane.doe@email.com', 'bob.j@email.com', 'alice@email.com'],
        'phone': ['(555) 123-4567', '(555) 987-6543', '(555) 111-2222', '(555) 444-5555'],
        'address': ['123 Main St', '456 Oak Ave', '789 Pine Rd', '321 Elm Blvd'],
        'diagnosis': ['Diabetes', 'Hypertension', 'Asthma', 'Heart Disease'],
        'icd10_code': ['E11.9', 'I10', 'J45.909', 'I25.10'],
        'loinc_code': ['2345-7', '58410-2', '3456-8', '7890-1'],
        'cpt_code': ['99213', '99214', '99215', '99212'],
        'treatment': ['Insulin', 'Lisinopril', 'Albuterol', 'Aspirin'],
        'timestamp': ['2024-01-01 10:00:00', '2024-01-01 11:00:00', '2024-01-01 12:00:00', '2024-01-01 13:00:00'],
        'user_id': ['user1', 'user2', 'user3', 'user4']
    }
    
    df = pd.DataFrame(sample_data)
    
    print(f"📊 Sample Dataset:")
    print(f"   Rows: {len(df)}")
    print(f"   Columns: {len(df.columns)}")
    print(f"   Columns: {', '.join(df.columns)}")
    print()
    
    # Test 1: Basic validation with compliance enabled
    print("🔍 Test 1: Basic Validation with Compliance (v1.2)")
    print("-" * 50)
    
    validator = MedicalDataValidator(enable_compliance=True)
    validator.add_rule(DataQualityChecker())
    validator.add_rule(PHIDetector())
    
    result = validator.validate(df)
    
    print(f"✅ Validation completed")
    print(f"   Overall valid: {result.is_valid}")
    print(f"   Total issues: {len(result.issues)}")
    print(f"   Errors: {len(result.get_issues_by_severity('error'))}")
    print(f"   Warnings: {len(result.get_issues_by_severity('warning'))}")
    print(f"   Info: {len(result.get_issues_by_severity('info'))}")
    
    # Check if compliance report was generated
    if 'compliance_report' in result.summary:
        compliance = result.summary['compliance_report']
        print(f"\n📋 Compliance Report (v1.2):")
        print(f"   Overall Score: {compliance['overall_score']:.1f}%")
        print(f"   Risk Level: {compliance['overall_risk_level'].upper()}")
        print(f"   Total Violations: {compliance['summary']['total_violations']}")
        
        print(f"\n🏥 Standards Compliance:")
        for standard, data in compliance['standards'].items():
            if isinstance(data, dict) and 'score' in data:
                print(f"   {standard.upper()}: {data['score']:.1f}% ({data['risk_level']}) - {data['violations_count']} violations")
        
        print(f"\n⚠️  Critical Violations: {compliance['summary']['critical_violations']}")
        print(f"🔴 High Violations: {compliance['summary']['high_violations']}")
        print(f"🟡 Medium Violations: {compliance['summary']['medium_violations']}")
        print(f"🟢 Low Violations: {compliance['summary']['low_violations']}")
        
        # Show some specific violations
        if compliance['all_violations']:
            print(f"\n🚨 Sample Violations:")
            for i, violation in enumerate(compliance['all_violations'][:5]):
                print(f"   {i+1}. {violation['standard']} - {violation['severity']}: {violation['message']}")
                if violation['recommendation']:
                    print(f"      💡 Recommendation: {violation['recommendation']}")
    else:
        print("❌ No compliance report generated")
    
    print("\n" + "=" * 70)
    
    # Test 2: Compliance disabled
    print("🔍 Test 2: Validation with Compliance Disabled")
    print("-" * 50)
    
    validator_no_compliance = MedicalDataValidator(enable_compliance=False)
    validator_no_compliance.add_rule(DataQualityChecker())
    validator_no_compliance.add_rule(PHIDetector())
    
    result_no_compliance = validator_no_compliance.validate(df)
    
    print(f"✅ Validation completed")
    print(f"   Overall valid: {result_no_compliance.is_valid}")
    print(f"   Total issues: {len(result_no_compliance.issues)}")
    print(f"   Compliance report present: {'compliance_report' in result_no_compliance.summary}")
    
    print("\n" + "=" * 70)
    
    # Test 3: Show detailed compliance breakdown
    if 'compliance_report' in result.summary:
        print("🔍 Test 3: Detailed Compliance Breakdown")
        print("-" * 50)
        
        compliance = result.summary['compliance_report']
        
        print("📊 HIPAA Compliance:")
        hipaa = compliance['standards']['hipaa']
        print(f"   Score: {hipaa['score']:.1f}%")
        print(f"   Risk Level: {hipaa['risk_level']}")
        print(f"   Recommendations:")
        for rec in hipaa['recommendations']:
            print(f"     • {rec}")
        
        print(f"\n📊 GDPR Compliance:")
        gdpr = compliance['standards']['gdpr']
        print(f"   Score: {gdpr['score']:.1f}%")
        print(f"   Risk Level: {gdpr['risk_level']}")
        print(f"   Recommendations:")
        for rec in gdpr['recommendations']:
            print(f"     • {rec}")
        
        print(f"\n📊 FDA Compliance:")
        fda = compliance['standards']['fda']
        print(f"   Score: {fda['score']:.1f}%")
        print(f"   Risk Level: {fda['risk_level']}")
        print(f"   Recommendations:")
        for rec in fda['recommendations']:
            print(f"     • {rec}")
        
        print(f"\n📊 Medical Coding Compliance:")
        coding = compliance['standards']['medical_coding']
        for code_type, data in coding.items():
            print(f"   {code_type.upper()}: {data['score']:.1f}% ({data['risk_level']})")
    
    print("\n" + "=" * 70)
    print("✅ v1.2 Compliance Testing Complete!")
    print("\n🎯 Key Features Demonstrated:")
    print("   • HIPAA PHI detection and scoring")
    print("   • GDPR personal data validation")
    print("   • FDA 21 CFR Part 11 compliance")
    print("   • Medical coding standards validation")
    print("   • Comprehensive risk assessment")
    print("   • Actionable recommendations")

if __name__ == "__main__":
    test_v1_2_compliance() 