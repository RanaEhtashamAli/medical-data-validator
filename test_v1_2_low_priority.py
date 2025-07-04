#!/usr/bin/env python3
"""
Test script for Medical Data Validator v1.2 Low Priority Features
Advanced Analytics and Real-time Monitoring
"""

import requests
import json
import pandas as pd
from io import StringIO
import time

def test_low_priority_features():
    """Test the new v1.2 low priority features."""
    
    print("🧪 Testing Medical Data Validator v1.2 - Low Priority Features")
    print("=" * 70)
    
    base_url = "http://localhost:8000"
    
    # Test 1: Advanced Analytics
    print("\n🔍 Test 1: Advanced Analytics")
    try:
        # Create sample data with various data types
        sample_data = {
            "patient_id": ["P001", "P002", "P003", "P004", "P005"],
            "age": [25, 30, 35, 40, 45],
            "blood_pressure": [120, 125, 130, 135, 140],
            "temperature": [98.6, 98.8, 99.0, 98.4, 98.9],
            "visit_date": ["2024-01-01", "2024-01-02", "2024-01-03", "2024-01-04", "2024-01-05"],
            "status": ["active", "active", "inactive", "active", "active"]
        }
        
        files = {'file': ('test_data.csv', StringIO(pd.DataFrame(sample_data).to_csv(index=False)))}
        data = {'time_column': 'visit_date'}
        
        response = requests.post(f"{base_url}/api/analytics", files=files, data=data)
        
        if response.status_code == 200:
            result = response.json()
            print("✅ Analytics API test passed")
            
            if 'analytics' in result:
                analytics = result['analytics']
                print(f"📊 Overall Quality Score: {analytics.get('overall_quality_score', 'N/A'):.2f}")
                
                # Quality metrics
                if 'quality_metrics' in analytics:
                    print("📋 Quality Metrics:")
                    for metric_name, metric in analytics['quality_metrics'].items():
                        print(f"   • {metric_name}: {metric['value']:.2f} ({metric['severity']})")
                
                # Anomalies
                if 'anomalies' in analytics:
                    print(f"🚨 Anomalies detected: {len(analytics['anomalies'])}")
                    for anomaly in analytics['anomalies']:
                        print(f"   • {anomaly['column']}: {anomaly['anomaly_type']} ({anomaly['severity']})")
                
                # Trends
                if 'trends' in analytics:
                    print(f"📈 Trends detected: {len(analytics['trends'])}")
                    for trend in analytics['trends']:
                        print(f"   • {trend['metric']}: {trend['trend']} (confidence: {trend['confidence']:.2f})")
                
                # Statistical summary
                if 'statistical_summary' in analytics:
                    summary = analytics['statistical_summary']
                    print(f"📊 Dataset: {summary['dataset_info']['rows']} rows, {summary['dataset_info']['columns']} columns")
            else:
                print("⚠️  No analytics data returned")
        else:
            print(f"❌ Analytics API failed: {response.status_code}")
            print(f"   Error: {response.text}")
    except Exception as e:
        print(f"❌ Analytics API error: {e}")
    
    # Test 2: Monitoring Statistics
    print("\n🔍 Test 2: Monitoring Statistics")
    try:
        response = requests.get(f"{base_url}/api/monitoring/stats")
        
        if response.status_code == 200:
            result = response.json()
            print("✅ Monitoring Stats API test passed")
            
            if 'stats' in result:
                stats = result['stats']
                print(f"📊 Total Validations: {stats.get('total_validations', 0)}")
                print(f"📊 Success Rate: {stats.get('success_rate', 0):.1%}")
                print(f"📊 Average Processing Time: {stats.get('average_processing_time', 0):.2f}s")
                print(f"📊 Active Alerts: {stats.get('active_alerts', 0)}")
                print(f"📊 Monitoring Active: {stats.get('monitoring_active', False)}")
            else:
                print("⚠️  No monitoring stats returned")
        else:
            print(f"❌ Monitoring Stats API failed: {response.status_code}")
            print(f"   Error: {response.text}")
    except Exception as e:
        print(f"❌ Monitoring Stats API error: {e}")
    
    # Test 3: Monitoring Alerts
    print("\n🔍 Test 3: Monitoring Alerts")
    try:
        response = requests.get(f"{base_url}/api/monitoring/alerts")
        
        if response.status_code == 200:
            result = response.json()
            print("✅ Monitoring Alerts API test passed")
            
            if 'alerts' in result:
                alerts = result['alerts']
                print(f"📊 Active Alerts: {len(alerts)}")
                
                for alert in alerts:
                    print(f"   • {alert['alert_type']}: {alert['message']} (Severity: {alert['severity']})")
            else:
                print("   • No active alerts")
        else:
            print(f"❌ Monitoring Alerts API failed: {response.status_code}")
            print(f"   Error: {response.text}")
    except Exception as e:
        print(f"❌ Monitoring Alerts API error: {e}")
    
    # Test 4: Trigger some validations to generate monitoring data
    print("\n🔍 Test 4: Generate Monitoring Data")
    try:
        # Run a few validations to generate monitoring data
        for i in range(3):
            print(f"   Running validation {i+1}/3...")
            
            # Create sample data with some issues to trigger alerts
            sample_data = {
                "patient_id": [f"P{i*100+1}", f"P{i*100+2}", f"P{i*100+3}"],
                "ssn": ["123-45-6789", "987-65-4321", "111-22-3333"],  # SSN pattern
                "age": [25 + i*5, 30 + i*5, 35 + i*5],
                "missing_data": [None, "value", None]  # Missing data pattern
            }
            
            files = {'file': ('test_data.csv', StringIO(pd.DataFrame(sample_data).to_csv(index=False)))}
            data = {'template': 'ehr'}
            
            response = requests.post(f"{base_url}/api/compliance/v1.2", files=files, data=data)
            
            if response.status_code == 200:
                print(f"      ✅ Validation {i+1} completed")
            else:
                print(f"      ❌ Validation {i+1} failed: {response.status_code}")
            
            time.sleep(1)  # Small delay between validations
        
        print("   ✅ Monitoring data generation completed")
        
    except Exception as e:
        print(f"❌ Monitoring data generation error: {e}")
    
    # Test 5: Check updated monitoring stats
    print("\n🔍 Test 5: Updated Monitoring Statistics")
    try:
        response = requests.get(f"{base_url}/api/monitoring/stats")
        
        if response.status_code == 200:
            result = response.json()
            print("✅ Updated Monitoring Stats API test passed")
            
            if 'stats' in result:
                stats = result['stats']
                print(f"📊 Total Validations: {stats.get('total_validations', 0)}")
                print(f"📊 Success Rate: {stats.get('success_rate', 0):.1%}")
                print(f"📊 Average Processing Time: {stats.get('average_processing_time', 0):.2f}s")
                print(f"📊 Active Alerts: {stats.get('active_alerts', 0)}")
            else:
                print("⚠️  No monitoring stats returned")
        else:
            print(f"❌ Updated Monitoring Stats API failed: {response.status_code}")
    except Exception as e:
        print(f"❌ Updated Monitoring Stats API error: {e}")
    
    # Test 6: Check for new alerts
    print("\n🔍 Test 6: Check for New Alerts")
    try:
        response = requests.get(f"{base_url}/api/monitoring/alerts")
        
        if response.status_code == 200:
            result = response.json()
            print("✅ New Alerts API test passed")
            
            if 'alerts' in result:
                alerts = result['alerts']
                print(f"📊 Active Alerts: {len(alerts)}")
                
                for alert in alerts:
                    print(f"   • {alert['alert_type']}: {alert['message']} (Severity: {alert['severity']})")
                    
                    # Test acknowledging the alert
                    if not alert['acknowledged']:
                        ack_response = requests.post(f"{base_url}/api/monitoring/alerts/{alert['id']}/acknowledge")
                        if ack_response.status_code == 200:
                            print(f"      ✅ Alert {alert['id']} acknowledged")
                        else:
                            print(f"      ❌ Failed to acknowledge alert {alert['id']}")
            else:
                print("   • No active alerts")
        else:
            print(f"❌ New Alerts API failed: {response.status_code}")
    except Exception as e:
        print(f"❌ New Alerts API error: {e}")
    
    # Test 7: Quality Trends
    print("\n🔍 Test 7: Quality Trends")
    try:
        response = requests.get(f"{base_url}/api/monitoring/trends/compliance_score?hours=24")
        
        if response.status_code == 200:
            result = response.json()
            print("✅ Quality Trends API test passed")
            
            if 'trends' in result:
                trends = result['trends']
                print(f"📊 Quality Trends: {len(trends)} data points")
                
                if trends:
                    latest_trend = trends[-1]
                    print(f"   • Latest: {latest_trend['value']:.2f} ({latest_trend['status']})")
                    print(f"   • Timestamp: {latest_trend['timestamp']}")
            else:
                print("   • No trend data available")
        else:
            print(f"❌ Quality Trends API failed: {response.status_code}")
    except Exception as e:
        print(f"❌ Quality Trends API error: {e}")
    
    print("\n" + "=" * 70)
    print("✅ v1.2 Low Priority Features Testing Complete!")
    print("\n📋 Summary of Low Priority Features:")
    print("   • Advanced Analytics (Data Quality Metrics)")
    print("   • Anomaly Detection")
    print("   • Trend Analysis")
    print("   • Real-time Monitoring")
    print("   • Alert Management")
    print("   • Quality Trend Tracking")
    print("   • Statistical Analysis")

if __name__ == "__main__":
    test_low_priority_features() 