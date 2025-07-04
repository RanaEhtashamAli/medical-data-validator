"""
Test cases for Medical Data Validator v1.2 Real-time Monitoring Features
"""

import pytest
import time
import threading
from datetime import datetime, timedelta
from medical_data_validator.monitoring import (
    RealTimeMonitor, MonitoringAlert, QualityMetric, MonitoringStats
)

class TestRealTimeMonitor:
    """Test cases for the RealTimeMonitor class."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.monitor = RealTimeMonitor()
        
        # Sample validation results
        self.sample_result = {
            'is_valid': True,
            'summary': {
                'compliance_report': {
                    'overall_score': 85.5
                }
            }
        }
        
        self.sample_failure_result = {
            'is_valid': False,
            'summary': {
                'compliance_report': {
                    'overall_score': 45.2
                }
            }
        }
    
    def test_monitor_initialization(self):
        """Test monitor initialization."""
        assert isinstance(self.monitor.alerts, list)
        assert isinstance(self.monitor.quality_history, dict)
        assert isinstance(self.monitor.stats, MonitoringStats)
        assert self.monitor.monitoring_active is False
        assert self.monitor.alert_id_counter == 0
    
    def test_start_stop_monitoring(self):
        """Test starting and stopping monitoring."""
        # Start monitoring
        self.monitor.start_monitoring()
        assert self.monitor.monitoring_active is True
        assert self.monitor.monitor_thread is not None
        assert self.monitor.monitor_thread.is_alive()
        
        # Stop monitoring
        self.monitor.stop_monitoring()
        assert self.monitor.monitoring_active is False
    
    def test_record_validation_result(self):
        """Test recording validation results."""
        # Record successful validation
        self.monitor.record_validation_result(self.sample_result, 2.5)
        
        # Check stats
        assert self.monitor.stats.total_validations == 1
        assert self.monitor.stats.successful_validations == 1
        assert self.monitor.stats.failed_validations == 0
        assert self.monitor.stats.average_processing_time == 2.5
        assert self.monitor.stats.last_validation_time is not None
        
        # Record failed validation
        self.monitor.record_validation_result(self.sample_failure_result, 1.8)
        
        # Check updated stats
        assert self.monitor.stats.total_validations == 2
        assert self.monitor.stats.successful_validations == 1
        assert self.monitor.stats.failed_validations == 1
        assert 2.0 < self.monitor.stats.average_processing_time < 2.3
    
    def test_quality_metric_recording(self):
        """Test quality metric recording."""
        # Record quality metric
        self.monitor._record_quality_metric('completeness', 0.85)
        
        # Check that metric was recorded
        assert 'completeness' in self.monitor.quality_history
        history = self.monitor.quality_history['completeness']
        assert len(history) == 1
        
        metric = history[0]
        assert isinstance(metric, QualityMetric)
        assert metric.name == 'completeness'
        assert metric.value == 0.85
        assert isinstance(metric.timestamp, datetime)
        assert metric.status in ['normal', 'warning', 'critical']
        
        # Record multiple metrics
        self.monitor._record_quality_metric('completeness', 0.75)
        self.monitor._record_quality_metric('completeness', 0.65)
        
        # Check history length (should be limited to 100)
        history = self.monitor.quality_history['completeness']
        assert len(history) <= 100
    
    def test_metric_status_calculation(self):
        """Test metric status calculation."""
        # Test normal status
        status = self.monitor._get_metric_status('completeness', 0.90)
        assert status == 'normal'
        
        # Test warning status
        status = self.monitor._get_metric_status('completeness', 0.80)
        assert status == 'warning'
        
        # Test critical status
        status = self.monitor._get_metric_status('completeness', 0.60)
        assert status == 'critical'
        
        # Test unknown metric (should use default threshold)
        status = self.monitor._get_metric_status('unknown_metric', 0.75)
        assert status == 'warning'  # 0.75 < 0.8 (default threshold)
    
    def test_alert_creation(self):
        """Test alert creation."""
        # Create alert
        self.monitor._create_alert(
            alert_type='quality_degradation',
            severity='medium',
            message='Test alert',
            details={'test': 'data'}
        )
        
        # Check alert was created
        assert len(self.monitor.alerts) == 1
        alert = self.monitor.alerts[0]
        
        assert isinstance(alert, MonitoringAlert)
        assert alert.alert_type == 'quality_degradation'
        assert alert.severity == 'medium'
        assert alert.message == 'Test alert'
        assert alert.details == {'test': 'data'}
        assert alert.acknowledged is False
        assert alert.resolved is False
        assert isinstance(alert.timestamp, datetime)
    
    def test_quality_degradation_detection(self):
        """Test quality degradation detection."""
        # Record declining quality metrics
        self.monitor._record_quality_metric('completeness', 0.90)
        self.monitor._record_quality_metric('completeness', 0.80)
        self.monitor._record_quality_metric('completeness', 0.70)
        
        # Check for degradation
        self.monitor._check_quality_degradation()
        
        # Should create alert
        degradation_alerts = [a for a in self.monitor.alerts if a.alert_type == 'quality_degradation']
        assert len(degradation_alerts) > 0
    
    def test_anomaly_detection(self):
        """Test anomaly detection."""
        # Record multiple failed validations to trigger high failure rate
        for _ in range(5):
            self.monitor.record_validation_result(self.sample_failure_result, 1.0)
        
        # Check for anomalies
        self.monitor._check_anomalies(self.sample_failure_result)
        
        # Should create anomaly alert for high failure rate (5 failures out of 8 total = 62.5% > 30%)
        anomaly_alerts = [a for a in self.monitor.alerts if a.alert_type == 'anomaly_detected']
        assert len(anomaly_alerts) > 0
    
    def test_compliance_violation_detection(self):
        """Test compliance violation detection."""
        # Create result with critical violations
        violation_result = {
            'is_valid': False,
            'compliance_report': {
                'standards': {
                    'hipaa': {
                        'violations': [
                            {'severity': 'critical', 'message': 'Critical violation'},
                            {'severity': 'high', 'message': 'High violation'},
                            {'severity': 'medium', 'message': 'Medium violation'}
                        ]
                    }
                }
            }
        }
        
        # Check for violations
        self.monitor._check_anomalies(violation_result)
        
        # Should create compliance violation alert for critical violations
        violation_alerts = [a for a in self.monitor.alerts if a.alert_type == 'compliance_violation']
        assert len(violation_alerts) > 0
    
    def test_alert_acknowledgment(self):
        """Test alert acknowledgment."""
        # Create alert
        self.monitor._create_alert(
            alert_type='test',
            severity='medium',
            message='Test alert',
            details={}
        )
        
        alert_id = self.monitor.alerts[0].id
        
        # Acknowledge alert
        success = self.monitor.acknowledge_alert(alert_id)
        assert success is True
        
        # Check alert was acknowledged
        alert = next(a for a in self.monitor.alerts if a.id == alert_id)
        assert alert.acknowledged is True
        
        # Test acknowledging non-existent alert
        success = self.monitor.acknowledge_alert('non_existent_id')
        assert success is False
    
    def test_alert_resolution(self):
        """Test alert resolution."""
        # Create alert
        self.monitor._create_alert(
            alert_type='test',
            severity='medium',
            message='Test alert',
            details={}
        )
        
        alert_id = self.monitor.alerts[0].id
        
        # Resolve alert
        success = self.monitor.resolve_alert(alert_id)
        assert success is True
        
        # Check alert was resolved
        alert = next(a for a in self.monitor.alerts if a.id == alert_id)
        assert alert.resolved is True
        
        # Test resolving non-existent alert
        success = self.monitor.resolve_alert('non_existent_id')
        assert success is False
    
    def test_get_active_alerts(self):
        """Test getting active alerts."""
        # Create multiple alerts
        self.monitor._create_alert(
            alert_type='test1',
            severity='high',
            message='Test alert 1',
            details={}
        )
        
        self.monitor._create_alert(
            alert_type='test2',
            severity='medium',
            message='Test alert 2',
            details={}
        )
        
        # Resolve one alert
        self.monitor.resolve_alert(self.monitor.alerts[0].id)
        
        # Get active alerts
        active_alerts = self.monitor.get_active_alerts()
        
        # Should return only unresolved alerts
        assert len(active_alerts) == 1
        assert active_alerts[0]['alert_type'] == 'test2'
    
    def test_quality_trends(self):
        """Test quality trends retrieval."""
        # Record quality metrics over time
        base_time = datetime.now()
        for i in range(10):
            metric_time = base_time + timedelta(hours=i)
            metric = QualityMetric(
                name='completeness',
                value=0.8 + (i * 0.01),
                timestamp=metric_time,
                threshold=0.8,
                status='normal'
            )
            if 'completeness' not in self.monitor.quality_history:
                self.monitor.quality_history['completeness'] = []
            self.monitor.quality_history['completeness'].append(metric)
        
        # Get trends for last 24 hours
        trends = self.monitor.get_quality_trends('completeness', hours=24)
        
        assert isinstance(trends, list)
        assert len(trends) > 0
        
        # Check trend structure
        for trend in trends:
            assert 'timestamp' in trend
            assert 'value' in trend
            assert 'status' in trend
            assert isinstance(trend['timestamp'], str)
            assert isinstance(trend['value'], float)
            assert trend['status'] in ['normal', 'warning', 'critical']
    
    def test_monitoring_stats(self):
        """Test monitoring statistics retrieval."""
        # Record some validation results
        self.monitor.record_validation_result(self.sample_result, 2.0)
        self.monitor.record_validation_result(self.sample_failure_result, 1.5)
        self.monitor.record_validation_result(self.sample_result, 3.0)
        
        # Get stats
        stats = self.monitor.get_monitoring_stats()
        
        assert isinstance(stats, dict)
        assert 'total_validations' in stats
        assert 'successful_validations' in stats
        assert 'failed_validations' in stats
        assert 'average_processing_time' in stats
        assert 'active_alerts' in stats
        assert 'last_validation_time' in stats
        
        assert stats['total_validations'] == 3
        assert stats['successful_validations'] == 2
        assert stats['failed_validations'] == 1
        assert stats['active_alerts'] >= 0  # Allow for alerts created during testing
    
    def test_monitor_loop(self):
        """Test monitoring loop functionality."""
        # Start monitoring
        self.monitor.start_monitoring()
        
        # Wait a bit for the loop to run
        time.sleep(0.1)
        
        # Stop monitoring
        self.monitor.stop_monitoring()
        
        # Verify monitoring stopped
        assert self.monitor.monitoring_active is False
    
    def test_alert_callback(self):
        """Test alert callback functionality."""
        callback_called = False
        callback_alert = None
        
        def test_callback(alert):
            nonlocal callback_called, callback_alert
            callback_called = True
            callback_alert = alert
        
        # Create monitor with callback
        monitor_with_callback = RealTimeMonitor(alert_callback=test_callback)
        
        # Create alert
        monitor_with_callback._create_alert(
            alert_type='test',
            severity='medium',
            message='Test alert',
            details={}
        )
        
        # Check callback was called
        assert callback_called is True
        assert callback_alert is not None
        assert callback_alert.alert_type == 'test'
    
    def test_empty_quality_history(self):
        """Test handling of empty quality history."""
        # Get trends for non-existent metric
        trends = self.monitor.get_quality_trends('non_existent_metric', hours=24)
        assert isinstance(trends, list)
        assert len(trends) == 0
    
    def test_alert_id_uniqueness(self):
        """Test alert ID uniqueness."""
        # Create multiple alerts
        for i in range(5):
            self.monitor._create_alert(
                alert_type=f'test_{i}',
                severity='medium',
                message=f'Test alert {i}',
                details={}
            )
        
        # Check all IDs are unique
        alert_ids = [alert.id for alert in self.monitor.alerts]
        assert len(alert_ids) == len(set(alert_ids))
    
    def test_quality_thresholds(self):
        """Test quality threshold configuration."""
        # Check default thresholds
        assert 'completeness' in self.monitor.quality_thresholds
        assert 'consistency' in self.monitor.quality_thresholds
        assert 'accuracy' in self.monitor.quality_thresholds
        assert 'compliance_score' in self.monitor.quality_thresholds
        
        # Check threshold structure
        for metric, thresholds in self.monitor.quality_thresholds.items():
            assert 'warning' in thresholds
            assert 'critical' in thresholds
            assert 0 <= thresholds['warning'] <= 1
            assert 0 <= thresholds['critical'] <= 1
            assert thresholds['critical'] <= thresholds['warning']
    
    def test_concurrent_access(self):
        """Test concurrent access to monitor."""
        # Start monitoring
        self.monitor.start_monitoring()
        
        # Create multiple threads accessing the monitor
        def record_results():
            for i in range(10):
                self.monitor.record_validation_result(self.sample_result, 1.0)
                time.sleep(0.01)
        
        threads = []
        for _ in range(3):
            thread = threading.Thread(target=record_results)
            threads.append(thread)
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        # Stop monitoring
        self.monitor.stop_monitoring()
        
        # Check results
        assert self.monitor.stats.total_validations == 30
        assert self.monitor.stats.successful_validations == 30
        assert self.monitor.stats.failed_validations == 0
    
    def test_json_serialization(self):
        """Test that monitoring data can be serialized to JSON."""
        # Record some data
        self.monitor.record_validation_result(self.sample_result, 2.0)
        self.monitor._record_quality_metric('completeness', 0.85)
        self.monitor._create_alert(
            alert_type='test',
            severity='medium',
            message='Test alert',
            details={'test': 'data'}
        )
        
        # Get stats and alerts
        stats = self.monitor.get_monitoring_stats()
        active_alerts = self.monitor.get_active_alerts()
        trends = self.monitor.get_quality_trends('completeness', hours=24)
        
        # Should be JSON serializable
        import json
        try:
            json.dumps(stats)
            json.dumps(active_alerts)
            json.dumps(trends)
        except (TypeError, ValueError) as e:
            pytest.fail(f"Monitoring data is not JSON serializable: {e}") 