#!/usr/bin/env python3
"""
Test script for Medical Data Validator v1.2 Medium Priority Features
Custom Rules and Compliance Templates
"""

import requests
import json
import pandas as pd
from io import StringIO

def test_medium_priority_features():
    """Test the new v1.2 medium priority features."""
    
    print("🧪 Testing Medical Data Validator v1.2 - Medium Priority Features")
    print("=" * 70)
    
    base_url = "http://localhost:8000"
    
    # Test 1: Get available compliance templates
    print("\n🔍 Test 1: Compliance Templates")
    try:
        response = requests.get(f"{base_url}/api/templates")
        if response.status_code == 200:
            data = response.json()
            print("✅ Templates API test passed")
            print(f"📋 Available templates: {len(data.get('templates', {}))}")
            for name, description in data.get('templates', {}).items():
                print(f"   • {name}: {description}")
        else:
            print(f"❌ Templates API failed: {response.status_code}")
    except Exception as e:
        print(f"❌ Templates API error: {e}")
    
    # Test 2: Get custom rules (should be empty initially)
    print("\n🔍 Test 2: Custom Rules (Initial)")
    try:
        response = requests.get(f"{base_url}/api/custom-rules")
        if response.status_code == 200:
            data = response.json()
            print("✅ Custom Rules API test passed")
            rules = data.get('rules', [])
            print(f"📋 Custom rules count: {len(rules)}")
            if rules:
                for rule in rules:
                    print(f"   • {rule['name']}: {rule['description']}")
            else:
                print("   • No custom rules configured")
        else:
            print(f"❌ Custom Rules API failed: {response.status_code}")
    except Exception as e:
        print(f"❌ Custom Rules API error: {e}")
    
    # Test 3: Add custom rule
    print("\n🔍 Test 3: Add Custom Rule")
    try:
        custom_rule = {
            "name": "test_rule",
            "pattern": r"^\d{3}-\d{2}-\d{4}$",  # SSN pattern
            "severity": "high",
            "field_pattern": r"ssn|social",
            "description": "Test rule for SSN detection",
            "recommendation": "Remove SSN data for compliance"
        }
        
        response = requests.post(
            f"{base_url}/api/custom-rules",
            json=custom_rule,
            headers={'Content-Type': 'application/json'}
        )
        
        if response.status_code == 200:
            data = response.json()
            print("✅ Add Custom Rule API test passed")
            print(f"📋 Response: {data.get('message', '')}")
        else:
            print(f"❌ Add Custom Rule API failed: {response.status_code}")
            print(f"   Error: {response.text}")
    except Exception as e:
        print(f"❌ Add Custom Rule API error: {e}")
    
    # Test 4: Get custom rules (should now have one)
    print("\n🔍 Test 4: Custom Rules (After Adding)")
    try:
        response = requests.get(f"{base_url}/api/custom-rules")
        if response.status_code == 200:
            data = response.json()
            print("✅ Custom Rules API test passed")
            rules = data.get('rules', [])
            print(f"📋 Custom rules count: {len(rules)}")
            for rule in rules:
                print(f"   • {rule['name']}: {rule['description']}")
                print(f"     Pattern: {rule['pattern']}")
                print(f"     Severity: {rule['severity']}")
        else:
            print(f"❌ Custom Rules API failed: {response.status_code}")
    except Exception as e:
        print(f"❌ Custom Rules API error: {e}")
    
    # Test 5: Test custom rule with sample data
    print("\n🔍 Test 5: Test Custom Rule with Sample Data")
    try:
        # Create sample data with SSN
        sample_data = {
            "patient_id": ["P001", "P002", "P003"],
            "ssn": ["123-45-6789", "987-65-4321", "111-22-3333"],
            "name": ["John Doe", "Jane Smith", "Bob Johnson"]
        }
        
        # Test with clinical trials template
        files = {'file': ('test_data.csv', StringIO(pd.DataFrame(sample_data).to_csv(index=False)))}
        data = {'template': 'clinical_trials'}
        
        response = requests.post(f"{base_url}/api/compliance/v1.2", files=files, data=data)
        
        if response.status_code == 200:
            result = response.json()
            print("✅ Custom Rule Validation test passed")
            
            # Check for custom rule violations
            if 'v1_2_compliance' in result:
                compliance = result['v1_2_compliance']
                if 'standards' in compliance and 'custom_rules' in compliance['standards']:
                    custom_rules = compliance['standards']['custom_rules']
                    print(f"📊 Custom Rules Score: {custom_rules.get('score', 'N/A')}")
                    print(f"📊 Custom Rules Violations: {custom_rules.get('violations_count', 'N/A')}")
                    print(f"📊 Custom Rules Configured: {custom_rules.get('rules_configured', 'N/A')}")
                else:
                    print("⚠️  No custom rules data in compliance report")
            else:
                print("⚠️  No v1.2 compliance data returned")
        else:
            print(f"❌ Custom Rule Validation failed: {response.status_code}")
            print(f"   Error: {response.text}")
    except Exception as e:
        print(f"❌ Custom Rule Validation error: {e}")
    
    # Test 6: Remove custom rule
    print("\n🔍 Test 6: Remove Custom Rule")
    try:
        response = requests.delete(f"{base_url}/api/custom-rules/test_rule")
        
        if response.status_code == 200:
            data = response.json()
            print("✅ Remove Custom Rule API test passed")
            print(f"📋 Response: {data.get('message', '')}")
        else:
            print(f"❌ Remove Custom Rule API failed: {response.status_code}")
            print(f"   Error: {response.text}")
    except Exception as e:
        print(f"❌ Remove Custom Rule API error: {e}")
    
    # Test 7: Verify custom rule removal
    print("\n🔍 Test 7: Verify Custom Rule Removal")
    try:
        response = requests.get(f"{base_url}/api/custom-rules")
        if response.status_code == 200:
            data = response.json()
            print("✅ Custom Rules API test passed")
            rules = data.get('rules', [])
            print(f"📋 Custom rules count: {len(rules)}")
            if not rules:
                print("   ✅ All custom rules successfully removed")
            else:
                print("   ⚠️  Some custom rules still exist")
                for rule in rules:
                    print(f"   • {rule['name']}: {rule['description']}")
        else:
            print(f"❌ Custom Rules API failed: {response.status_code}")
    except Exception as e:
        print(f"❌ Custom Rules API error: {e}")
    
    # Test 8: Test with different templates
    print("\n🔍 Test 8: Test Different Templates")
    templates_to_test = ['ehr', 'laboratory', 'imaging', 'research']
    
    for template_name in templates_to_test:
        try:
            print(f"\n   Testing template: {template_name}")
            
            # Create template-specific sample data
            if template_name == 'ehr':
                sample_data = {
                    "patient_id": ["P12345678", "P87654321"],
                    "bp": ["120/80", "140/90"],
                    "dosage": ["10 mg", "5 mcg"]
                }
            elif template_name == 'laboratory':
                sample_data = {
                    "result": ["15.2 (10.0-20.0 mg/dL)", "8.5 (7.0-10.0 g/dL)"],
                    "specimen": ["SP123456-001", "SP123456-002"],
                    "status": ["completed", "pending"]
                }
            elif template_name == 'imaging':
                sample_data = {
                    "dicom_uid": ["1.2.3.4.5.6", "1.2.3.4.5.7"],
                    "modality": ["CT", "MR"],
                    "quality": ["4", "5"]
                }
            elif template_name == 'research':
                sample_data = {
                    "id": ["R123456", "R654321"],
                    "consent": ["consented", "declined"],
                    "birth_year": ["1985", "1990"]
                }
            
            files = {'file': ('test_data.csv', StringIO(pd.DataFrame(sample_data).to_csv(index=False)))}
            data = {'template': template_name}
            
            response = requests.post(f"{base_url}/api/compliance/v1.2", files=files, data=data)
            
            if response.status_code == 200:
                result = response.json()
                if 'v1_2_compliance' in result:
                    compliance = result['v1_2_compliance']
                    if 'standards' in compliance and 'custom_rules' in compliance['standards']:
                        custom_rules = compliance['standards']['custom_rules']
                        violations = custom_rules.get('violations_count', 0)
                        print(f"      ✅ Template applied - Violations: {violations}")
                    else:
                        print(f"      ⚠️  No custom rules data")
                else:
                    print(f"      ⚠️  No v1.2 compliance data")
            else:
                print(f"      ❌ Template test failed: {response.status_code}")
        except Exception as e:
            print(f"      ❌ Template test error: {e}")
    
    print("\n" + "=" * 70)
    print("✅ v1.2 Medium Priority Features Testing Complete!")
    print("\n📋 Summary of Medium Priority Features:")
    print("   • Custom Rules Management")
    print("   • Compliance Templates (5 pre-built)")
    print("   • Template-specific validation")
    print("   • API endpoints for rule management")
    print("   • Integration with v1.2 compliance engine")

if __name__ == "__main__":
    test_medium_priority_features() 