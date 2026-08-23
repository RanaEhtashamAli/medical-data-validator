"""Dash page: anonymize PHI/PII columns in an uploaded dataset.

Follows dashboard/pages/security.py's shape — dcc.Upload + base64 decode,
a run button driving one callback that stores its result in a dcc.Store,
and a separate download callback reading from that store — since anonymize
is the same "upload, act, preview, download" flow with a single action.
"""

import dash
import dash_bootstrap_components as dbc
import pandas as pd
from dash import dcc, html, dash_table, Input, Output, State, callback

from medical_data_validator.dashboard.routes import anonymize_dataframe
from medical_data_validator.dashboard.utils import (
    decode_upload_to_dataframe,
    register_page_once,
)

register_page_once(__name__, path='/anonymize', name='Anonymize')

METHOD_OPTIONS = [
    {'label': 'HIPAA Safe Harbor', 'value': 'hipaa_safe_harbor'},
    {'label': 'Hash', 'value': 'hash'},
    {'label': 'Mask', 'value': 'mask'},
]
VALID_METHODS = {opt['value'] for opt in METHOD_OPTIONS}

layout = dbc.Container([
    dbc.Row([
        dbc.Col([
            html.H1("Anonymize", className="text-center mb-4"),
            html.P(
                "Upload a dataset and anonymize PHI/PII columns",
                className="text-center"
            )
        ])
    ]),
    dbc.Row([
        dbc.Col([
            dcc.Upload(
                id='anon-upload',
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
            dcc.Dropdown(
                id='anon-method-dropdown',
                options=METHOD_OPTIONS,
                value='hipaa_safe_harbor',
                clearable=False,
            )
        ], width=4),
        dbc.Col([
            dbc.Input(
                id='anon-columns-input',
                placeholder='Columns, comma-separated (blank = auto-detect PHI-like columns)',
            )
        ], width=8),
    ], className='mb-3'),
    dbc.Row([
        dbc.Col([
            dbc.Button('Anonymize', id='anon-run-btn', color='primary'),
        ])
    ], className='mb-3'),
    dbc.Row([
        dbc.Col([
            html.Div(id='anon-results')
        ])
    ]),
    dbc.Row([
        dbc.Col([
            dash_table.DataTable(id='anon-preview-table')
        ])
    ]),
    dbc.Row([
        dbc.Col([
            dbc.Button('Download CSV', id='anon-download-btn', className='mt-3'),
            dcc.Download(id='anon-download'),
            dcc.Store(id='anon-last-result-store'),
        ])
    ]),
], fluid=True)


def _run_anonymize_from_upload(contents, filename, method, columns_csv):
    """Decode the upload, anonymize it, and return (success, message, records).

    `columns_csv` is split into a list on comma; a blank, empty, or
    whitespace-only value becomes None, matching
    anonymize_dataframe()'s auto-detect-when-None contract (a stray space
    in the text box must not silently downgrade to an empty column list —
    that would report success while leaving PHI unmasked).
    An unrecognized `method` is rejected up front (mirroring /api/anonymize's
    validation) so it never reaches MedicalDataValidator.anonymize() — which
    would otherwise raise a raw ValueError from DataAnonymizer.
    """
    if method not in VALID_METHODS:
        return False, f"Unknown method '{method}'. Use hipaa_safe_harbor, hash, or mask.", None

    try:
        df = decode_upload_to_dataframe(contents, filename)
    except Exception as exc:
        return False, f"Could not parse {filename}: {exc}", None

    parsed_columns = [c.strip() for c in columns_csv.split(',') if c.strip()] if columns_csv else []
    columns = parsed_columns or None

    try:
        result_df = anonymize_dataframe(df, columns, method)
    except Exception as exc:
        return False, str(exc), None

    return True, f"Anonymized {len(result_df)} row(s)", result_df.to_dict(orient='records')


def _render_results(success, message):
    color = 'success' if success else 'danger'
    return dbc.Alert(message, color=color)


@callback(
    [Output('anon-results', 'children'),
     Output('anon-preview-table', 'data'),
     Output('anon-preview-table', 'columns'),
     Output('anon-last-result-store', 'data')],
    Input('anon-run-btn', 'n_clicks'),
    [State('anon-upload', 'contents'),
     State('anon-upload', 'filename'),
     State('anon-method-dropdown', 'value'),
     State('anon-columns-input', 'value')],
    prevent_initial_call=True,
)
def _handle_anonymize(n_clicks, contents, filename, method, columns_csv):
    success, message, records = _run_anonymize_from_upload(contents, filename, method, columns_csv)

    if not success:
        # Clear the store on failure: the results shown on screen reflect a
        # failure, so any prior successful run's data must not remain
        # downloadable via a stale store value.
        return _render_results(False, message), [], [], None

    preview = records[:20]
    columns = [{'name': c, 'id': c} for c in (preview[0].keys() if preview else [])]
    return _render_results(True, message), preview, columns, records


@callback(
    Output('anon-download', 'data'),
    Input('anon-download-btn', 'n_clicks'),
    State('anon-last-result-store', 'data'),
    prevent_initial_call=True,
)
def _download_anonymized_csv(n_clicks, records):
    if not records:
        return dash.no_update
    df = pd.DataFrame(records)
    return dcc.send_string(df.to_csv(index=False), "anonymized.csv")
