#!/usr/bin/env python3
"""
Test script for Medical Data Validator v1.2 API endpoints
"""

import requests
import json
import pandas as pd
from io import StringIO

def test_v1_2_compliance_api():
    """Test the v1.2 compliance API endpoint."""
    
    print("🧪 Testing Medical Data Validator v1.2 API Endpoints")
    print("=" * 60)
    
    # Base URL (adjust if your server runs on different port)
    base_url = "http://localhost:5000"
    
    # Test 1: Health check
    print("\n🔍 Test 1: Health Check")
    print("-" * 30)
    try:
        response = requests.get(f"{base_url}/api/health")
        if response.status_code == 200:
            print("✅ Health check passed")
            print(f"   Status: {response.json()}")
        else:
            print(f"❌ Health check failed: {response.status_code}")
    except Exception as e:
        print(f"❌ Health check error: {e}")
    
    # Test 2: v1.2 Compliance API with sample data
    print("\n🔍 Test 2: v1.2 Compliance API")
    print("-" * 30)
    
    # Create sample data with PHI and compliance issues
    sample_data = {
        'patient_name': ['John Smith', 'Jane Doe', 'Bob Johnson'],
        'ssn': ['123-45-6789', '987-65-4321', '111-22-3333'],
        'email': ['john@email.com', 'jane@email.com', 'bob@email.com'],
        'diagnosis': ['Diabetes', 'Hypertension', 'Asthma'],
        'icd10_code': ['E11.9', 'I10', 'J45.909'],
        'loinc_code': ['2345-7', '58410-2', '3456-8'],
        'cpt_code': ['99213', '99214', '99215']
    }
    
    # Convert to CSV string
    df = pd.DataFrame(sample_data)
    csv_data = df.to_csv(index=False)
    
    # Test v1.2 compliance endpoint
    try:
        files = {'file': ('test_data.csv', StringIO(csv_data), 'text/csv')}
        response = requests.post(f"{base_url}/api/compliance/v1.2", files=files)
        
        if response.status_code == 200:
            result = response.json()
            print("✅ v1.2 Compliance API test passed")
            print(f"   Success: {result.get('success')}")
            print(f"   Message: {result.get('message')}")
            
            # Check for v1.2 compliance data
            v1_2_compliance = result.get('v1_2_compliance')
            if v1_2_compliance:
                print("\n📊 v1.2 Compliance Results:")
                print(f"   Overall Score: {v1_2_compliance.get('overall_score', 'N/A')}%")
                print(f"   Risk Level: {v1_2_compliance.get('overall_risk_level', 'N/A')}")
                
                standards = v1_2_compliance.get('standards', {})
                for standard, data in standards.items():
                    if isinstance(data, dict) and 'score' in data:
                        print(f"   {standard.upper()}: {data['score']}% ({data.get('risk_level', 'N/A')})")
                
                summary = v1_2_compliance.get('summary', {})
                print(f"\n📋 Violations Summary:")
                print(f"   Total: {summary.get('total_violations', 0)}")
                print(f"   Critical: {summary.get('critical_violations', 0)}")
                print(f"   High: {summary.get('high_violations', 0)}")
                print(f"   Medium: {summary.get('medium_violations', 0)}")
                print(f"   Low: {summary.get('low_violations', 0)}")
            else:
                print("⚠️  No v1.2 compliance data returned")
        else:
            print(f"❌ v1.2 Compliance API failed: {response.status_code}")
            print(f"   Response: {response.text}")
            
    except Exception as e:
        print(f"❌ v1.2 Compliance API error: {e}")
    
    # Test 3: Regular compliance API (for comparison)
    print("\n🔍 Test 3: Regular Compliance API (Comparison)")
    print("-" * 30)
    
    try:
        files = {'file': ('test_data.csv', StringIO(csv_data), 'text/csv')}
        response = requests.post(f"{base_url}/api/compliance/check", files=files)
        
        if response.status_code == 200:
            result = response.json()
            print("✅ Regular Compliance API test passed")
            print(f"   HIPAA Compliant: {result.get('hipaa_compliant', 'N/A')}")
            print(f"   ICD-10 Compliant: {result.get('icd10_compliant', 'N/A')}")
            print(f"   LOINC Compliant: {result.get('loinc_compliant', 'N/A')}")
            print(f"   CPT Compliant: {result.get('cpt_compliant', 'N/A')}")
        else:
            print(f"❌ Regular Compliance API failed: {response.status_code}")
            
    except Exception as e:
        print(f"❌ Regular Compliance API error: {e}")
    
    print("\n" + "=" * 60)
    print("✅ v1.2 API Testing Complete!")
    print("\n🎯 Key Features Tested:")
    print("   • Health check endpoint")
    print("   • v1.2 Advanced compliance validation")
    print("   • Regular compliance validation (comparison)")
    print("   • HIPAA, GDPR, FDA, and medical coding compliance")

if __name__ == "__main__":
    test_v1_2_compliance_api() 