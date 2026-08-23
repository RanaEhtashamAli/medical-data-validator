"""Dash page: security tools — HIPAA check, security audit, and data sanitization.

Follows dashboard/pages/validate.py's upload-decode pattern (dcc.Upload +
base64 decode + dataframe_from_upload_bytes) combined with
dashboard/pages/registry.py's multi-button dash.ctx.triggered_id dispatcher,
since this page has three actions sharing a single upload.
"""

import base64

import dash
import dash_bootstrap_components as dbc
import pandas as pd
from dash import dcc, html, dash_table, Input, Output, State, callback

from medical_data_validator.dashboard.utils import (
    dataframe_from_upload_bytes,
    register_page_once,
)
from medical_data_validator.security import (
    DataSanitizer,
    HIPAAComplianceChecker,
    SecurityAuditor,
    _strip_phi_samples,
)

register_page_once(__name__, path='/security', name='Security')

layout = dbc.Container([
    dbc.Row([
        dbc.Col([
            html.H1("Security Tools", className="text-center mb-4"),
            html.P(
                "Upload a dataset to run a HIPAA check, security audit, or sanitize it",
                className="text-center"
            )
        ])
    ]),
    dbc.Row([
        dbc.Col([
            dcc.Upload(
                id='security-upload',
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
            dbc.Checkbox(
                id='security-samples-checkbox',
                label='Include PHI sample values',
                value=False,
            )
        ])
    ]),
    dbc.Row([
        dbc.Col([
            dbc.ButtonGroup([
                dbc.Button('HIPAA Check', id='security-hipaa-btn', color='primary'),
                dbc.Button('Security Audit', id='security-audit-btn', color='secondary'),
                dbc.Button('Sanitize', id='security-sanitize-btn', color='warning'),
            ]),
        ])
    ], className='mb-3'),
    dbc.Row([
        dbc.Col([
            html.Div(id='security-results')
        ])
    ]),
    dbc.Row([
        dbc.Col([
            dbc.Button('Download sanitized CSV', id='security-sanitize-download-btn', className='mt-3'),
            dcc.Download(id='security-sanitize-download'),
            dcc.Store(id='security-sanitize-store'),
        ])
    ]),
], fluid=True)


def _decode_upload(contents, filename):
    """Decode a dcc.Upload contents string into a DataFrame. Raises on
    missing upload or an unparseable/unsupported file — callers turn this
    into an inline error message rather than letting the callback crash."""
    if contents is None:
        raise ValueError("Upload a file first")
    _header, b64data = contents.split(',', 1)
    raw_bytes = base64.b64decode(b64data)
    return dataframe_from_upload_bytes(filename or '', raw_bytes)


def _run_hipaa_check_from_upload(contents, filename, include_samples):
    """Decode the upload and run HIPAAComplianceChecker.check_hipaa_compliance.
    Returns the report dict, or {'error': message} if the upload couldn't be
    parsed. When include_samples is False, sample_values are stripped down
    to a sample_count via _strip_phi_samples."""
    try:
        df = _decode_upload(contents, filename)
    except Exception as exc:
        return {'error': f"Could not parse {filename}: {exc}"}

    report = HIPAAComplianceChecker().check_hipaa_compliance(df)
    if not include_samples:
        _strip_phi_samples(report)
    return report


def _run_security_audit_from_upload(contents, filename):
    """Decode the upload and run SecurityAuditor.audit_security. Returns the
    audit result dict, or {'error': message} if the upload couldn't be
    parsed."""
    try:
        df = _decode_upload(contents, filename)
    except Exception as exc:
        return {'error': f"Could not parse {filename}: {exc}"}

    return SecurityAuditor().audit_security(df)


def _run_sanitize_from_upload(contents, filename):
    """Decode the upload and run DataSanitizer.sanitize_data. Returns the
    sanitized rows as a list of dicts (same shape as the
    /api/security/sanitize endpoint's 'sanitized_data'), or
    {'error': message} if the upload couldn't be parsed."""
    try:
        df = _decode_upload(contents, filename)
    except Exception as exc:
        return {'error': f"Could not parse {filename}: {exc}"}

    sanitized = DataSanitizer().sanitize_data(df)
    return sanitized.to_dict(orient='records')


def _is_error(result) -> bool:
    return isinstance(result, dict) and 'error' in result


def _phi_detected_table_data(phi_detected):
    """Normalize phi_detected items for display: sample_values (a list) is
    rendered as a comma-joined string; sample_count (an int) is passed
    through as-is. Only one of the two is present per item, depending on
    whether the samples checkbox was checked."""
    rows = []
    for item in phi_detected:
        row = {
            'column': item.get('column'),
            'phi_type': item.get('phi_type'),
            'instances': item.get('instances'),
        }
        if 'sample_count' in item:
            row['sample_count'] = item['sample_count']
        if 'sample_values' in item:
            row['sample_values'] = ', '.join(str(v) for v in item['sample_values'])
        rows.append(row)
    return rows


def _render_hipaa_results(report):
    if _is_error(report):
        return dbc.Alert(report['error'], color='danger')

    table_data = _phi_detected_table_data(report.get('phi_detected', []))
    columns = [{'name': c, 'id': c} for c in ('column', 'phi_type', 'instances', 'sample_count', 'sample_values')
               if any(c in row for row in table_data)]

    return html.Div([
        html.P(
            f"Compliance score: {report.get('compliance_score')} | "
            f"Compliant: {report.get('compliant')} | "
            f"Total PHI instances: {report.get('total_phi_instances', 0)}"
        ),
        dash_table.DataTable(data=table_data, columns=columns),
        html.Ul([html.Li(rec) for rec in report.get('recommendations', [])]),
    ])


def _render_audit_results(result):
    if _is_error(result):
        return dbc.Alert(result['error'], color='danger')

    issues = result.get('issues', [])
    recommendations = result.get('recommendations', [])
    row_count = max(len(issues), len(recommendations))
    table_data = [
        {
            'issue': issues[i] if i < len(issues) else '',
            'recommendation': recommendations[i] if i < len(recommendations) else '',
        }
        for i in range(row_count)
    ]

    return html.Div([
        html.P(
            f"Overall status: {result.get('overall_status')} | "
            f"Security score: {result.get('security_score')}"
        ),
        dash_table.DataTable(
            data=table_data,
            columns=[
                {'name': 'Issue', 'id': 'issue'},
                {'name': 'Recommendation', 'id': 'recommendation'},
            ],
        ),
    ])


def _render_sanitize_results(sanitized, preview_rows=10):
    if _is_error(sanitized):
        return dbc.Alert(sanitized['error'], color='danger')

    preview = sanitized[:preview_rows]
    columns = [{'name': c, 'id': c} for c in (preview[0].keys() if preview else [])]

    return html.Div([
        html.P(f"Sanitized {len(sanitized)} row(s) — showing first {len(preview)}"),
        dash_table.DataTable(data=preview, columns=columns),
    ])


@callback(
    [Output('security-results', 'children'), Output('security-sanitize-store', 'data')],
    [Input('security-hipaa-btn', 'n_clicks'),
     Input('security-audit-btn', 'n_clicks'),
     Input('security-sanitize-btn', 'n_clicks')],
    [State('security-upload', 'contents'),
     State('security-upload', 'filename'),
     State('security-samples-checkbox', 'value')],
    prevent_initial_call=True,
)
def _handle_security_actions(hipaa_clicks, audit_clicks, sanitize_clicks, contents, filename, include_samples):
    triggered = dash.ctx.triggered_id

    if triggered == 'security-hipaa-btn':
        report = _run_hipaa_check_from_upload(contents, filename, bool(include_samples))
        return _render_hipaa_results(report), dash.no_update

    if triggered == 'security-audit-btn':
        result = _run_security_audit_from_upload(contents, filename)
        return _render_audit_results(result), dash.no_update

    if triggered == 'security-sanitize-btn':
        sanitized = _run_sanitize_from_upload(contents, filename)
        store_data = sanitized if not _is_error(sanitized) else dash.no_update
        return _render_sanitize_results(sanitized), store_data

    return dash.no_update, dash.no_update


@callback(
    Output('security-sanitize-download', 'data'),
    Input('security-sanitize-download-btn', 'n_clicks'),
    State('security-sanitize-store', 'data'),
    prevent_initial_call=True,
)
def _download_sanitized_csv(n_clicks, sanitized_records):
    if not sanitized_records:
        return dash.no_update
    df = pd.DataFrame(sanitized_records)
    return dcc.send_string(df.to_csv(index=False), "sanitized_data.csv")
