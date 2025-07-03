"""
Utility functions for the Medical Data Validator Dashboard.
"""

import sys
import os
from pathlib import Path
import pandas as pd

# Add the project root to Python path for direct execution
if __name__ == "__main__":
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    sys.path.insert(0, project_root)

try:
    from medical_data_validator.core import ValidationResult
except ImportError:
    # Fallback for relative imports when used as package
    from ..core import ValidationResult

from typing import Dict, Any
try:
    import plotly.express as px
except ImportError:
    # Fallback if plotly is not installed
    px = None

def load_data(file_path: str) -> pd.DataFrame:
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

def generate_charts(data: pd.DataFrame, result: ValidationResult) -> Dict[str, Any]:
    charts = {}
    
    if px is None:
        # Return empty charts if plotly is not available
        return {
            'severity_distribution': {},
            'column_issues': {},
            'missing_values': {},
            'data_types': {}
        }
    
    severity_counts = {
        'Error': len([i for i in result.issues if i.severity == 'error']),
        'Warning': len([i for i in result.issues if i.severity == 'warning']),
        'Info': len([i for i in result.issues if i.severity == 'info'])
    }
    
    # Only include categories that have actual issues
    non_zero_severities = {k: v for k, v in severity_counts.items() if v > 0}
    
    if non_zero_severities:
        fig_severity = px.pie(
            values=list(non_zero_severities.values()),
            names=list(non_zero_severities.keys()),
            title='Validation Issues by Severity',
            color_discrete_map={'Error': '#d62728', 'Warning': '#ff7f0e', 'Info': '#1f77b4'}
        )
        charts['severity_distribution'] = fig_severity.to_dict()
    else:
        # No issues found - create a simple message chart
        charts['severity_distribution'] = {
            'data': [{
                'type': 'pie',
                'values': [1],
                'labels': ['No Issues Found'],
                'marker': {'colors': ['#28a745']}
            }],
            'layout': {
                'title': 'Validation Issues by Severity',
                'showlegend': False
            }
        }
    column_issues = {}
    for issue in result.issues:
        if issue.column:
            column_issues[issue.column] = column_issues.get(issue.column, 0) + 1
    if column_issues:
        fig_columns = px.bar(
            x=list(column_issues.keys()),
            y=list(column_issues.values()),
            title='Issues by Column',
            labels={'x': 'Column', 'y': 'Number of Issues'}
        )
        charts['column_issues'] = fig_columns.to_dict()
    missing_data = data.isnull().sum()
    if missing_data.sum() > 0:
        fig_missing = px.bar(
            x=missing_data.index,
            y=missing_data.values,
            title='Missing Values by Column',
            labels={'x': 'Column', 'y': 'Missing Count'}
        )
        charts['missing_values'] = fig_missing.to_dict()
    dtype_counts = data.dtypes.value_counts()
    fig_dtypes = px.pie(
        values=dtype_counts.values,
        names=dtype_counts.index.astype(str),
        title='Data Types Distribution'
    )
    charts['data_types'] = fig_dtypes.to_dict()
    return charts 