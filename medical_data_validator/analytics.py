"""
Advanced Analytics for Medical Data Validator v1.2
Statistical analysis, trend detection, and data quality metrics.
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime, timedelta
import json

@dataclass
class DataQualityMetric:
    """Represents a data quality metric."""
    name: str
    value: float
    unit: str
    description: str
    severity: str  # 'excellent', 'good', 'fair', 'poor', 'critical'

@dataclass
class TrendAnalysis:
    """Represents a trend analysis result."""
    metric: str
    trend: str  # 'increasing', 'decreasing', 'stable', 'fluctuating'
    confidence: float
    period: str
    description: str

@dataclass
class AnomalyDetection:
    """Represents an anomaly detection result."""
    column: str
    anomaly_type: str  # 'outlier', 'missing_pattern', 'data_type_mismatch', 'format_inconsistency'
    severity: str
    description: str
    affected_rows: List[int]
    recommendation: str

class AdvancedAnalytics:
    """Advanced analytics engine for medical data validation."""
    
    def __init__(self):
        self.quality_thresholds = {
            'completeness': {'excellent': 0.95, 'good': 0.85, 'fair': 0.70, 'poor': 0.50},
            'consistency': {'excellent': 0.90, 'good': 0.80, 'fair': 0.65, 'poor': 0.45},
            'accuracy': {'excellent': 0.95, 'good': 0.85, 'fair': 0.70, 'poor': 0.50},
            'timeliness': {'excellent': 0.90, 'good': 0.80, 'fair': 0.65, 'poor': 0.45}
        }
    
    def calculate_data_quality_metrics(self, df: pd.DataFrame) -> Dict[str, DataQualityMetric]:
        """Calculate comprehensive data quality metrics."""
        metrics = {}
        
        # Completeness
        completeness = float(1 - (df.isnull().sum().sum() / (df.shape[0] * df.shape[1])))
        metrics['completeness'] = DataQualityMetric(
            name="Data Completeness",
            value=completeness,
            unit="percentage",
            description="Percentage of non-missing values across the dataset",
            severity=self._get_severity(completeness, 'completeness')
        )
        
        # Consistency (check for data type consistency)
        consistency_scores = []
        for col in df.columns:
            if df[col].dtype in ['object', 'string']:
                # Check for mixed data types in string columns
                unique_types = df[col].dropna().apply(type).nunique()
                consistency_scores.append(1.0 if unique_types <= 1 else 0.5)
            else:
                consistency_scores.append(1.0)
        
        consistency = float(np.mean(consistency_scores) if consistency_scores else 1.0)
        metrics['consistency'] = DataQualityMetric(
            name="Data Consistency",
            value=consistency,
            unit="percentage",
            description="Consistency of data types and formats across columns",
            severity=self._get_severity(consistency, 'consistency')
        )
        
        # Accuracy (based on value ranges and patterns)
        accuracy_scores = []
        for col in df.columns:
            if df[col].dtype in ['int64', 'float64']:
                # Check for reasonable value ranges
                q1, q3 = df[col].quantile([0.25, 0.75])
                iqr = q3 - q1
                outliers = ((df[col] < (q1 - 1.5 * iqr)) | (df[col] > (q3 + 1.5 * iqr))).sum()
                accuracy_scores.append(1.0 - (outliers / len(df)))
            else:
                accuracy_scores.append(1.0)
        
        accuracy = np.mean(accuracy_scores) if accuracy_scores else 1.0
        metrics['accuracy'] = DataQualityMetric(
            name="Data Accuracy",
            value=accuracy,
            unit="percentage",
            description="Accuracy of data values based on statistical analysis",
            severity=self._get_severity(accuracy, 'accuracy')
        )
        
        # Timeliness (if date columns exist)
        timeliness = 1.0
        date_columns = df.select_dtypes(include=['datetime64']).columns
        if len(date_columns) > 0:
            # Check if dates are recent (within last year)
            current_date = pd.Timestamp.now()
            for col in date_columns:
                if df[col].dtype == 'datetime64[ns]':
                    days_old = (current_date - df[col].max()).days
                    timeliness = max(0, 1 - (days_old / 365))  # Decay over a year
                    break
        
        metrics['timeliness'] = DataQualityMetric(
            name="Data Timeliness",
            value=timeliness,
            unit="percentage",
            description="Recency of the data based on date fields",
            severity=self._get_severity(timeliness, 'timeliness')
        )
        
        return metrics
    
    def detect_anomalies(self, df: pd.DataFrame) -> List[AnomalyDetection]:
        """Detect anomalies in the dataset."""
        anomalies = []
        
        for col in df.columns:
            col_data = df[col].dropna()
            
            if len(col_data) == 0:
                continue
            
            # Outlier detection for numeric columns
            if df[col].dtype in ['int64', 'float64']:
                col_data = df[col]  # Ensure alignment
                q1, q3 = col_data.quantile([0.25, 0.75])
                iqr = q3 - q1
                outlier_mask = (col_data < (q1 - 1.5 * iqr)) | (col_data > (q3 + 1.5 * iqr))
                outlier_indices = df.index[outlier_mask].tolist()
                
                if len(outlier_indices) > 0:
                    anomalies.append(AnomalyDetection(
                        column=col,
                        anomaly_type="outlier",
                        severity="medium" if len(outlier_indices) < len(df) * 0.1 else "high",
                        description=f"Found {len(outlier_indices)} outliers in column '{col}'",
                        affected_rows=outlier_indices,
                        recommendation="Review outliers for data entry errors or special cases"
                    ))
            
            # Missing pattern detection
            missing_count = df[col].isnull().sum()
            if missing_count > 0:
                # Check if missing values follow a pattern (simplified)
                missing_percentage = missing_count / len(df)
                if missing_percentage > 0.2:  # More than 20% missing
                    anomalies.append(AnomalyDetection(
                        column=col,
                        anomaly_type="missing_pattern",
                        severity="high",
                        description=f"High percentage of missing values detected in column '{col}': {missing_percentage:.1%}",
                        affected_rows=list(range(len(df))),  # Simplified - all rows potentially affected
                        recommendation="Investigate data collection process for this column"
                    ))
            
            # Data type inconsistency
            if df[col].dtype == 'object':
                # Check for mixed data types
                type_counts = col_data.apply(type).value_counts()
                if len(type_counts) > 1:
                    anomalies.append(AnomalyDetection(
                        column=col,
                        anomaly_type="data_type_mismatch",
                        severity="medium",
                        description=f"Mixed data types detected in column '{col}': {type_counts.to_dict()}",
                        affected_rows=df[col].index.tolist(),
                        recommendation="Standardize data types for this column"
                    ))
        
        return anomalies
    
    def analyze_trends(self, df: pd.DataFrame, time_column: Optional[str] = None) -> List[TrendAnalysis]:
        """Analyze trends in the dataset."""
        trends = []
        
        # If no time column specified, try to find one
        if time_column is None:
            time_columns = df.select_dtypes(include=['datetime64']).columns
            if len(time_columns) > 0:
                time_column = time_columns[0]
        
        if time_column is None:
            # No time column available
            return trends
        
        # Sort by time
        df_sorted = df.sort_values(time_column)
        
        # Analyze trends for numeric columns
        numeric_columns = df.select_dtypes(include=['int64', 'float64']).columns
        for col in numeric_columns:
            if col == time_column:
                continue
            
            # Calculate trend using linear regression
            x = np.arange(len(df_sorted))
            y = df_sorted[col].dropna().values
            
            if len(y) < 3:
                continue
            
            # Simple linear trend calculation
            slope = np.polyfit(x[:len(y)], y, 1)[0]
            
            # Determine trend direction
            if slope > 0.01:
                trend = "increasing"
            elif slope < -0.01:
                trend = "decreasing"
            else:
                trend = "stable"
            
            # Calculate confidence (R-squared)
            y_pred = np.polyval([slope, np.mean(y)], x[:len(y)])
            ss_res = np.sum((y - y_pred) ** 2)
            ss_tot = np.sum((y - np.mean(y)) ** 2)
            confidence = 1 - (ss_res / ss_tot) if ss_tot != 0 else 0
            
            trends.append(TrendAnalysis(
                metric=col,
                trend=trend,
                confidence=confidence,
                period=f"{df_sorted[time_column].min()} to {df_sorted[time_column].max()}",
                description=f"{col} shows {trend} trend with {confidence:.2f} confidence"
            ))
        
        return trends
    
    def generate_statistical_summary(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Generate comprehensive statistical summary."""
        summary = {
            'dataset_info': {
                'rows': len(df),
                'columns': len(df.columns),
                'memory_usage': df.memory_usage(deep=True).sum(),
                'data_types': df.dtypes.value_counts().to_dict()
            },
            'missing_data': {
                'total_missing': df.isnull().sum().sum(),
                'missing_percentage': (df.isnull().sum().sum() / (len(df) * len(df.columns))) * 100,
                'columns_with_missing': df.columns[df.isnull().any()].tolist()
            },
            'numeric_summary': {},
            'categorical_summary': {}
        }
        
        # Numeric columns summary
        numeric_cols = df.select_dtypes(include=['int64', 'float64']).columns
        for col in numeric_cols:
            summary['numeric_summary'][col] = {
                'mean': df[col].mean(),
                'median': df[col].median(),
                'std': df[col].std(),
                'min': df[col].min(),
                'max': df[col].max(),
                'q25': df[col].quantile(0.25),
                'q75': df[col].quantile(0.75),
                'missing_count': df[col].isnull().sum()
            }
        
        # Categorical columns summary
        categorical_cols = df.select_dtypes(include=['object']).columns
        for col in categorical_cols:
            value_counts = df[col].value_counts()
            summary['categorical_summary'][col] = {
                'unique_values': df[col].nunique(),
                'most_common': value_counts.index[0] if len(value_counts) > 0 else None,
                'most_common_count': value_counts.iloc[0] if len(value_counts) > 0 else 0,
                'missing_count': df[col].isnull().sum(),
                'top_5_values': value_counts.head(5).to_dict()
            }
        
        return summary
    
    def _get_severity(self, value: float, metric_type: str) -> str:
        """Get severity level based on value and metric type."""
        thresholds = self.quality_thresholds[metric_type]
        
        if value >= thresholds['excellent']:
            return 'excellent'
        elif value >= thresholds['good']:
            return 'good'
        elif value >= thresholds['fair']:
            return 'fair'
        elif value >= thresholds['poor']:
            return 'poor'
        else:
            return 'critical'
    
    def comprehensive_analysis(self, df: pd.DataFrame, time_column: Optional[str] = None) -> Dict[str, Any]:
        """Perform comprehensive analytics analysis."""
        return {
            'quality_metrics': {
                name: {
                    'value': float(metric.value),
                    'unit': metric.unit,
                    'description': metric.description,
                    'severity': metric.severity
                }
                for name, metric in self.calculate_data_quality_metrics(df).items()
            },
            'anomalies': [
                {
                    'column': anomaly.column,
                    'anomaly_type': anomaly.anomaly_type,
                    'severity': anomaly.severity,
                    'description': anomaly.description,
                    'affected_rows_count': len(anomaly.affected_rows),
                    'recommendation': anomaly.recommendation
                }
                for anomaly in self.detect_anomalies(df)
            ],
            'trends': [
                {
                    'metric': trend.metric,
                    'trend': trend.trend,
                    'confidence': float(trend.confidence),
                    'period': str(trend.period),
                    'description': trend.description
                }
                for trend in self.analyze_trends(df, time_column)
            ],
            'statistical_summary': self._serialize_statistical_summary(df),
            'overall_quality_score': float(self._calculate_overall_quality_score(df))
        }
    
    def _serialize_statistical_summary(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Generate serializable statistical summary."""
        summary = self.generate_statistical_summary(df)
        
        # Convert numpy types to native Python types
        def convert_numpy_types(obj):
            if hasattr(obj, 'item'):
                return obj.item()
            elif isinstance(obj, dict):
                # Convert all keys to str for JSON serialization
                return {str(k): convert_numpy_types(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [convert_numpy_types(v) for v in obj]
            else:
                return obj
        
        return convert_numpy_types(summary)
    
    def _calculate_overall_quality_score(self, df: pd.DataFrame) -> float:
        """Calculate overall data quality score."""
        metrics = self.calculate_data_quality_metrics(df)
        weights = {'completeness': 0.3, 'consistency': 0.25, 'accuracy': 0.25, 'timeliness': 0.2}
        
        score = 0
        for metric_name, metric in metrics.items():
            score += metric.value * weights[metric_name]
        
        return score 