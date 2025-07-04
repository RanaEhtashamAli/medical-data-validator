"""
Real-time Monitoring for Medical Data Validator v1.2
Live data quality tracking and alerting system.
"""

import time
import threading
from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from collections import deque
import json

@dataclass
class MonitoringAlert:
    """Represents a monitoring alert."""
    id: str
    timestamp: datetime
    alert_type: str  # 'quality_degradation', 'anomaly_detected', 'compliance_violation', 'system_error'
    severity: str  # 'low', 'medium', 'high', 'critical'
    message: str
    details: Dict[str, Any]
    acknowledged: bool = False
    resolved: bool = False

@dataclass
class QualityMetric:
    """Represents a quality metric for monitoring."""
    name: str
    value: float
    timestamp: datetime
    threshold: float
    status: str  # 'normal', 'warning', 'critical'

@dataclass
class MonitoringStats:
    """Represents monitoring statistics."""
    total_validations: int = 0
    successful_validations: int = 0
    failed_validations: int = 0
    average_processing_time: float = 0.0
    active_alerts: int = 0
    last_validation_time: Optional[datetime] = None

class RealTimeMonitor:
    """Real-time monitoring system for data quality tracking."""
    
    def __init__(self, alert_callback: Optional[Callable] = None):
        self.alerts: List[MonitoringAlert] = []
        self.quality_history: Dict[str, deque] = {}
        self.stats = MonitoringStats()
        self.alert_callback = alert_callback
        self.monitoring_active = False
        self.monitor_thread = None
        self.alert_id_counter = 0
        
        # Quality thresholds
        self.quality_thresholds = {
            'completeness': {'warning': 0.85, 'critical': 0.70},
            'consistency': {'warning': 0.80, 'critical': 0.65},
            'accuracy': {'warning': 0.85, 'critical': 0.70},
            'compliance_score': {'warning': 0.80, 'critical': 0.65}
        }
    
    def start_monitoring(self) -> None:
        """Start the monitoring system."""
        if not self.monitoring_active:
            self.monitoring_active = True
            self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
            self.monitor_thread.start()
            print("🔍 Real-time monitoring started")
    
    def stop_monitoring(self) -> None:
        """Stop the monitoring system."""
        self.monitoring_active = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=5)
        print("🔍 Real-time monitoring stopped")
    
    def record_validation_result(self, result: Dict[str, Any], processing_time: float) -> None:
        """Record a validation result for monitoring."""
        self.stats.total_validations += 1
        self.stats.last_validation_time = datetime.now()
        
        if result.get('is_valid', False):
            self.stats.successful_validations += 1
        else:
            self.stats.failed_validations += 1
        
        # Update average processing time
        if self.stats.total_validations == 1:
            self.stats.average_processing_time = processing_time
        else:
            self.stats.average_processing_time = (
                (self.stats.average_processing_time * (self.stats.total_validations - 1) + processing_time) 
                / self.stats.total_validations
            )
        
        # Record quality metrics if available
        if 'compliance_report' in result.get('summary', {}):
            compliance_report = result['summary']['compliance_report']
            if 'overall_score' in compliance_report:
                self._record_quality_metric('compliance_score', compliance_report['overall_score'] / 100.0)
        
        # Check for quality degradation
        self._check_quality_degradation()
        
        # Check for anomalies
        self._check_anomalies(result)
    
    def _record_quality_metric(self, metric_name: str, value: float) -> None:
        """Record a quality metric with timestamp."""
        if metric_name not in self.quality_history:
            self.quality_history[metric_name] = deque(maxlen=100)  # Keep last 100 values
        
        metric = QualityMetric(
            name=metric_name,
            value=value,
            timestamp=datetime.now(),
            threshold=self.quality_thresholds.get(metric_name, {}).get('warning', 0.8),
            status=self._get_metric_status(metric_name, value)
        )
        
        self.quality_history[metric_name].append(metric)
    
    def _get_metric_status(self, metric_name: str, value: float) -> str:
        """Get the status of a metric based on thresholds."""
        thresholds = self.quality_thresholds.get(metric_name, {})
        warning_threshold = thresholds.get('warning', 0.8)  # Default to 0.8 for unknown metrics
        critical_threshold = thresholds.get('critical', 0.6)
        
        if value >= warning_threshold:
            return 'normal'
        elif value >= critical_threshold:
            return 'warning'
        else:
            return 'critical'
    
    def _check_quality_degradation(self) -> None:
        """Check for quality degradation and create alerts."""
        for metric_name, history in self.quality_history.items():
            if len(history) < 3:
                continue
            
            # Check if quality is declining
            recent_values = [m.value for m in list(history)[-3:]]
            if len(recent_values) >= 3:
                trend = recent_values[-1] - recent_values[0]
                
                if trend < -0.1:  # 10% decline
                    self._create_alert(
                        alert_type='quality_degradation',
                        severity='medium' if trend > -0.2 else 'high',
                        message=f"Quality degradation detected in {metric_name}",
                        details={
                            'metric': metric_name,
                            'trend': trend,
                            'current_value': recent_values[-1],
                            'previous_value': recent_values[0]
                        }
                    )
    
    def _check_anomalies(self, result: Dict[str, Any]) -> None:
        """Check for anomalies in validation results."""
        try:
            # Check for high failure rate
            failure_rate = self.stats.failed_validations / max(1, self.stats.total_validations)
            if failure_rate > 0.3:  # 30% failure rate
                self._create_alert(
                    alert_type='anomaly_detected',
                    severity='high',
                    message=f"High validation failure rate detected: {failure_rate:.1%}",
                    details={
                        'failure_rate': failure_rate,
                        'total_validations': self.stats.total_validations,
                        'failed_validations': self.stats.failed_validations
                    }
                )
            
            # Check for critical compliance violations
            compliance_report = result.get('compliance_report', {})
            if compliance_report:
                # Handle both old and new compliance report structures
                if 'standards' in compliance_report:
                    # New v1.2 structure
                    standards = compliance_report['standards']
                    all_violations = []
                    for standard_name, standard_data in standards.items():
                        violations = standard_data.get('violations', [])
                        all_violations.extend(violations)
                else:
                    # Old structure
                    all_violations = compliance_report.get('all_violations', [])
                
                # Convert ComplianceViolation objects to dicts if needed
                violations_dict = []
                for v in all_violations:
                    if hasattr(v, 'severity'):  # ComplianceViolation object
                        violations_dict.append({
                            'severity': v.severity,
                            'standard': v.standard,
                            'field': v.field,
                            'message': v.message
                        })
                    else:  # Already a dict
                        violations_dict.append(v)
                
                critical_violations = [v for v in violations_dict if v.get('severity') == 'critical']
                if critical_violations:
                    self._create_alert(
                        alert_type='compliance_violation',
                        severity='critical',
                        message=f"Critical compliance violations detected: {len(critical_violations)}",
                        details={
                            'critical_violations': critical_violations,
                            'total_violations': len(violations_dict)
                        }
                    )
            
            # Check validation failure rate
            total_issues = len(result.get('issues', []))
            if total_issues > 10:
                self._create_alert(
                    alert_type='anomaly_detected',
                    severity='high',
                    message=f"High number of validation issues: {total_issues}",
                    details={
                        'total_issues': total_issues
                    }
                )
                
        except Exception as e:
            print(f"Monitoring recording failed: {e}")
    
    def _create_alert(self, alert_type: str, severity: str, message: str, details: Dict[str, Any]) -> None:
        """Create a new monitoring alert."""
        self.alert_id_counter += 1
        alert = MonitoringAlert(
            id=f"alert_{self.alert_id_counter}",
            timestamp=datetime.now(),
            alert_type=alert_type,
            severity=severity,
            message=message,
            details=details
        )
        
        self.alerts.append(alert)
        self.stats.active_alerts = len([a for a in self.alerts if not a.resolved])
        
        # Call alert callback if provided
        if self.alert_callback:
            try:
                self.alert_callback(alert)
            except Exception as e:
                print(f"Error in alert callback: {e}")
        
        print(f"🚨 Alert created: {message} (Severity: {severity})")
    
    def acknowledge_alert(self, alert_id: str) -> bool:
        """Acknowledge an alert."""
        for alert in self.alerts:
            if alert.id == alert_id:
                alert.acknowledged = True
                return True
        return False
    
    def resolve_alert(self, alert_id: str) -> bool:
        """Resolve an alert."""
        for alert in self.alerts:
            if alert.id == alert_id:
                alert.resolved = True
                self.stats.active_alerts = len([a for a in self.alerts if not a.resolved])
                return True
        return False
    
    def get_active_alerts(self) -> List[Dict[str, Any]]:
        """Get all active (unresolved) alerts."""
        return [
            {
                'id': alert.id,
                'timestamp': alert.timestamp.isoformat(),
                'alert_type': alert.alert_type,
                'severity': alert.severity,
                'message': alert.message,
                'details': alert.details,
                'acknowledged': alert.acknowledged
            }
            for alert in self.alerts
            if not alert.resolved
        ]
    
    def get_quality_trends(self, metric_name: str, hours: int = 24) -> List[Dict[str, Any]]:
        """Get quality trends for a specific metric."""
        if metric_name not in self.quality_history:
            return []
        
        cutoff_time = datetime.now() - timedelta(hours=hours)
        recent_metrics = [
            metric for metric in self.quality_history[metric_name]
            if metric.timestamp >= cutoff_time
        ]
        
        return [
            {
                'timestamp': metric.timestamp.isoformat(),
                'value': metric.value,
                'status': metric.status
            }
            for metric in recent_metrics
        ]
    
    def get_monitoring_stats(self) -> Dict[str, Any]:
        """Get current monitoring statistics."""
        return {
            'total_validations': self.stats.total_validations,
            'successful_validations': self.stats.successful_validations,
            'failed_validations': self.stats.failed_validations,
            'success_rate': self.stats.successful_validations / max(1, self.stats.total_validations),
            'average_processing_time': self.stats.average_processing_time,
            'active_alerts': self.stats.active_alerts,
            'last_validation_time': self.stats.last_validation_time.isoformat() if self.stats.last_validation_time else None,
            'monitoring_active': self.monitoring_active
        }
    
    def _monitor_loop(self) -> None:
        """Main monitoring loop."""
        while self.monitoring_active:
            try:
                # Check for stale data (no validations in last hour)
                if (self.stats.last_validation_time and 
                    datetime.now() - self.stats.last_validation_time > timedelta(hours=1)):
                    self._create_alert(
                        alert_type='system_error',
                        severity='medium',
                        message="No validation activity detected in the last hour",
                        details={
                            'last_validation_time': self.stats.last_validation_time.isoformat(),
                            'inactive_duration_hours': 1
                        }
                    )
                
                # Clean up old alerts (older than 7 days)
                cutoff_time = datetime.now() - timedelta(days=7)
                self.alerts = [alert for alert in self.alerts if alert.timestamp >= cutoff_time]
                
                time.sleep(60)  # Check every minute
                
            except Exception as e:
                print(f"Error in monitoring loop: {e}")
                time.sleep(60)

# Global monitoring instance
monitor = RealTimeMonitor() 