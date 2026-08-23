"""
Utility functions for the Medical Data Validator Dashboard.
"""

import base64
import io
import sys
import os
from pathlib import Path
import pandas as pd
import dash

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

def register_page_once(module_name: str, path: str, name: str, **kwargs) -> None:
    """Register a Dash page unless a page already claims this path.

    Dash's page auto-loader (dash.Dash(use_pages=True)) imports each file
    under dashboard/pages/ under a synthesized module name, while this
    project's tests also import the same file directly by its real dotted
    path to unit-test helpers defined alongside the page. Both routes
    execute the module's top-level dash.register_page(...) call, each under
    a different module name, so calling it unconditionally either raises
    dash.exceptions.PageError ("can't be called within a callback") or
    produces two page_registry entries for the same path.

    Guarding on path rather than module name works regardless of which
    import route ran first, since the two routes never share a module name,
    and matches how Dash's own router resolves requests: by path
    (dash._pages._path_to_page), not by which module registered it.
    """
    if not any(page.get('path') == path for page in dash.page_registry.values()):
        dash.register_page(module_name, path=path, name=name, **kwargs)


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

def dataframe_from_upload_bytes(filename: str, raw_bytes: bytes) -> pd.DataFrame:
    """Parse an uploaded file's raw bytes into a DataFrame, dispatching on extension."""
    suffix = filename.lower().rsplit('.', 1)[-1] if '.' in filename else ''
    buf = io.BytesIO(raw_bytes)
    if suffix == 'csv':
        return pd.read_csv(buf)
    elif suffix in ('xlsx', 'xls'):
        return pd.read_excel(buf)
    elif suffix == 'json':
        return pd.read_json(buf)
    else:
        raise ValueError(f"Unsupported file type: {filename}")


def decode_upload_to_dataframe(contents: str, filename: str) -> pd.DataFrame:
    """Decode a dcc.Upload contents string into a DataFrame. Raises on
    missing upload or an unparseable/unsupported file — callers turn this
    into an inline error message rather than letting the callback crash.

    Shared by every Dash page's upload-decode step (previously copy-pasted
    identically across pages/security.py, pages/anonymize.py,
    pages/compliance.py, and pages/validate.py, plus a differently-shaped
    inline copy in pages/analytics.py).
    """
    if contents is None:
        raise ValueError("Upload a file first")
    _header, b64data = contents.split(',', 1)
    raw_bytes = base64.b64decode(b64data)
    return dataframe_from_upload_bytes(filename or '', raw_bytes)


def _is_error(result) -> bool:
    """True if `result` is the `{'error': ...}` sentinel dict convention used
    by several Dash pages' upload-processing helpers. Shared by
    pages/security.py, pages/analytics.py, and pages/compliance.py (each
    used to define this identically)."""
    return isinstance(result, dict) and 'error' in result


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
    else:
        # No missing values - create a message chart
        charts['missing_values'] = {
            'data': [{
                'type': 'bar',
                'x': ['No Missing Values'],
                'y': [0],
                'marker': {'color': '#28a745'}
            }],
            'layout': {
                'title': 'Missing Values by Column',
                'showlegend': False,
                'yaxis': {'title': 'Missing Count'},
                'xaxis': {'title': 'Column'}
            }
        }
    dtype_counts = data.dtypes.value_counts()
    if len(dtype_counts) > 0:
        fig_dtypes = px.pie(
            values=dtype_counts.values,
            names=dtype_counts.index.astype(str),
            title='Data Types Distribution'
        )
        charts['data_types'] = fig_dtypes.to_dict()
    else:
        # No data types found - create a simple message chart
        charts['data_types'] = {
            'data': [{
                'type': 'pie',
                'values': [1],
                'labels': ['No Data Types'],
                'marker': {'colors': ['#6c757d']}
            }],
            'layout': {
                'title': 'Data Types Distribution',
                'showlegend': False
            }
        }
    return charts 