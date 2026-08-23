"""Dash page: advanced analytics — quality metrics, anomalies, trends, and a
statistical summary for an uploaded dataset.

Follows dashboard/pages/validate.py's single-trigger upload-decode pattern
(one action button, one callback) since this page only has one action ("Run
Analysis"), unlike registry.py/security.py's multi-button dispatcher pages.
"""

import json

import dash_bootstrap_components as dbc
from dash import dcc, html, dash_table, Input, Output, State, callback

from medical_data_validator.dashboard.utils import (
    _is_error,
    decode_upload_to_dataframe,
    register_page_once,
)

register_page_once(__name__, path='/analytics', name='Analytics')

METRICS_COLUMNS = [
    {'name': 'Metric', 'id': 'name'},
    {'name': 'Value', 'id': 'value'},
    {'name': 'Severity', 'id': 'severity'},
    {'name': 'Description', 'id': 'description'},
]

ANOMALIES_COLUMNS = [
    {'name': 'Column', 'id': 'column'},
    {'name': 'Type', 'id': 'anomaly_type'},
    {'name': 'Severity', 'id': 'severity'},
    {'name': 'Description', 'id': 'description'},
    {'name': 'Affected rows', 'id': 'affected_rows_count'},
    {'name': 'Recommendation', 'id': 'recommendation'},
]

TRENDS_COLUMNS = [
    {'name': 'Metric', 'id': 'metric'},
    {'name': 'Trend', 'id': 'trend'},
    {'name': 'Confidence', 'id': 'confidence'},
    {'name': 'Period', 'id': 'period'},
    {'name': 'Description', 'id': 'description'},
]

layout = dbc.Container([
    dbc.Row([
        dbc.Col([
            html.H1("Advanced Analytics", className="text-center mb-4"),
            html.P(
                "Upload a dataset to compute data quality metrics, detect anomalies, "
                "and analyze trends",
                className="text-center"
            )
        ])
    ]),
    dbc.Row([
        dbc.Col([
            dcc.Upload(
                id='analytics-upload',
                children=html.Div([
                    'Drag and Drop or ',
                    html.A('Select Files')
                ]),
                style={
                    'width': '100%',
                    'height': '60px',
                    'lineHeight': '60px',
                    'borderWidth': '1px',
                    'borderStyle': 'dashed',
                    'borderRadius': '5px',
                    'textAlign': 'center',
                    'margin': '10px'
                },
                multiple=False
            ),
        ])
    ]),
    dbc.Row([
        dbc.Col([
            dbc.Input(id='analytics-time-column-input', placeholder='Time column (optional)'),
        ], width=6),
        dbc.Col([
            dbc.Button('Run Analysis', id='analytics-run-btn', color='primary'),
        ], width=2),
    ], className='mb-3'),
    dbc.Row([
        dbc.Col([
            html.Div(id='analytics-message'),
            html.H4(id='analytics-quality-score'),
        ])
    ]),
    dbc.Row([
        dbc.Col([
            html.H5("Quality metrics"),
            dash_table.DataTable(id='analytics-metrics-table', columns=METRICS_COLUMNS),
        ])
    ], className='mb-3'),
    dbc.Row([
        dbc.Col([
            html.H5("Anomalies"),
            dash_table.DataTable(id='analytics-anomalies-table', columns=ANOMALIES_COLUMNS),
        ])
    ], className='mb-3'),
    dbc.Row([
        dbc.Col([
            html.H5("Trends"),
            html.Div(id='analytics-trends'),
        ])
    ], className='mb-3'),
    dbc.Row([
        dbc.Col([
            html.H5("Statistical summary"),
            html.Pre(id='analytics-statistical-summary', className='bg-light p-2'),
        ])
    ]),
], fluid=True)


def _run_analytics_from_upload(contents, filename, time_column):
    """Decode the upload and run AdvancedAnalytics().comprehensive_analysis().

    Returns the analysis dict (already passed through convert_numpy_types, so
    it's safe to hand straight to json.dumps or a dash_table's `data`), or
    {'error': message} if there's no upload or it couldn't be parsed.
    """
    if contents is None:
        return {'error': 'Upload a file first'}

    from medical_data_validator.analytics import AdvancedAnalytics
    from medical_data_validator.dashboard.routes import convert_numpy_types

    try:
        df = decode_upload_to_dataframe(contents, filename)
    except Exception as exc:
        return {'error': f"Could not parse {filename}: {exc}"}

    if isinstance(time_column, str):
        time_column = time_column.strip() or None
    else:
        time_column = time_column or None

    try:
        report = AdvancedAnalytics().comprehensive_analysis(df, time_column)
    except Exception as exc:
        return {'error': f"Analysis failed: {exc}"}

    return convert_numpy_types(report)


def _metrics_table_data(quality_metrics):
    return [
        {
            'name': name,
            'value': metric.get('value'),
            'severity': metric.get('severity'),
            'description': metric.get('description'),
        }
        for name, metric in (quality_metrics or {}).items()
    ]


def _render_trends(trends):
    if not trends:
        return "No trends"
    return dash_table.DataTable(data=trends, columns=TRENDS_COLUMNS)


@callback(
    [Output('analytics-message', 'children'),
     Output('analytics-quality-score', 'children'),
     Output('analytics-metrics-table', 'data'),
     Output('analytics-anomalies-table', 'data'),
     Output('analytics-trends', 'children'),
     Output('analytics-statistical-summary', 'children')],
    Input('analytics-run-btn', 'n_clicks'),
    [State('analytics-upload', 'contents'),
     State('analytics-upload', 'filename'),
     State('analytics-time-column-input', 'value')],
    prevent_initial_call=True,
)
def _update_analytics(n_clicks, contents, filename, time_column):
    result = _run_analytics_from_upload(contents, filename, time_column)

    if _is_error(result):
        # Errors render as a dedicated dbc.Alert instead of overloading the
        # quality-score H4 (which used to render a raw error string as an
        # oversized, unstyled heading).
        return dbc.Alert(result['error'], color='danger'), "", [], [], "", ""

    quality_score = f"Overall quality score: {result.get('overall_quality_score')}"
    metrics_data = _metrics_table_data(result.get('quality_metrics', {}))
    anomalies_data = result.get('anomalies', []) or []
    trends_children = _render_trends(result.get('trends', []))
    summary_text = json.dumps(result.get('statistical_summary', {}), indent=2, default=str)

    return "", quality_score, metrics_data, anomalies_data, trends_children, summary_text
