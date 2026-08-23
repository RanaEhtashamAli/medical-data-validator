"""Dash page: upload a file and run validation against the real validator."""

import dash
import dash_bootstrap_components as dbc
from dash import dcc, html, Input, Output, State, callback

from medical_data_validator.dashboard.utils import (
    decode_upload_to_dataframe,
    generate_charts,
    register_page_once,
)

register_page_once(__name__, path='/', name='Validate')

layout = dbc.Container([
    dbc.Row([
        dbc.Col([
            html.H1("Medical Data Validator Dashboard", className="text-center mb-4"),
            html.P("Upload your medical dataset for comprehensive validation", className="text-center")
        ])
    ]),
    dbc.Row([
        dbc.Col([
            dcc.Upload(
                id='upload-data',
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
            dbc.Checklist(
                id='validation-options',
                options=[
                    {'label': 'Detect PHI/PII', 'value': 'phi'},
                    {'label': 'Quality Checks', 'value': 'quality'},
                ],
                value=['phi', 'quality'],
                inline=True
            )
        ])
    ]),
    dbc.Row([
        dbc.Col([
            dcc.Dropdown(
                id='profile-dropdown',
                options=[
                    {'label': 'Clinical Trials', 'value': 'clinical_trials'},
                    {'label': 'EHR', 'value': 'ehr'},
                    {'label': 'Imaging', 'value': 'imaging'},
                    {'label': 'Lab Data', 'value': 'lab'},
                ],
                placeholder='Select validation profile (optional)',
                clearable=True
            )
        ])
    ]),
    dbc.Row([
        dbc.Col([
            html.Div(id='validation-results')
        ])
    ]),
    dbc.Row([
        dbc.Col([
            dcc.Graph(id='severity-chart')
        ], width=6),
        dbc.Col([
            dcc.Graph(id='column-chart')
        ], width=6)
    ]),
    dbc.Row([
        dbc.Col([
            dcc.Graph(id='missing-chart')
        ], width=6),
        dbc.Col([
            dcc.Graph(id='dtype-chart')
        ], width=6)
    ]),
    dbc.Row([
        dbc.Col([
            dbc.Button("Download PDF Report", id='download-pdf-btn', className='me-2'),
            dbc.Button("Download CSV Report", id='download-csv-btn'),
            dcc.Download(id='download-report'),
            dcc.Store(id='last-validation-result'),
        ])
    ]),
], fluid=True)


def _run_validation_for_upload(contents, filename, options, profile):
    """Parse an uploaded file, run validation, and build the 4 chart figures.
    Extracted from the Dash callback so it's directly testable without a
    running Dash app."""
    if contents is None:
        return "Upload a file to start validation", {}, {}, {}, {}, None

    from medical_data_validator.dashboard.routes import create_validator

    try:
        df = decode_upload_to_dataframe(contents, filename)
    except Exception as exc:
        return f"Could not parse {filename}: {exc}", {}, {}, {}, {}, None

    options = options or []
    validator = create_validator(
        detect_phi='phi' in options,
        quality_checks='quality' in options,
        profile=profile,
    )
    result = validator.validate(df)
    result_dict = result.to_dict()

    summary_lines = [
        f"Valid: {result_dict['is_valid']}",
        f"Compliant: {result_dict['is_compliant']}",
        f"Total issues: {result_dict['total_issues']} "
        f"(errors: {result_dict['error_count']}, warnings: {result_dict['warning_count']}, "
        f"info: {result_dict['info_count']})",
    ]
    summary = " | ".join(summary_lines)

    charts = generate_charts(df, result)
    return (
        summary,
        charts.get('severity_distribution', {}),
        charts.get('column_issues', {}),
        charts.get('missing_values', {}),
        charts.get('data_types', {}),
        result_dict,
    )


@callback(
    [Output('validation-results', 'children'),
     Output('severity-chart', 'figure'),
     Output('column-chart', 'figure'),
     Output('missing-chart', 'figure'),
     Output('dtype-chart', 'figure'),
     Output('last-validation-result', 'data')],
    [Input('upload-data', 'contents')],
    [State('upload-data', 'filename'),
     State('validation-options', 'value'),
     State('profile-dropdown', 'value')]
)
def update_output(contents, filename, options, profile):
    return _run_validation_for_upload(contents, filename, options, profile)


@callback(
    Output('download-report', 'data'),
    [Input('download-pdf-btn', 'n_clicks'), Input('download-csv-btn', 'n_clicks')],
    State('last-validation-result', 'data'),
    prevent_initial_call=True,
)
def _download_report(pdf_clicks, csv_clicks, result_dict):
    if not result_dict:
        return dash.no_update
    from medical_data_validator.reports import generate_pdf_report, generate_csv_report
    triggered = dash.ctx.triggered_id
    if triggered == 'download-pdf-btn':
        return dcc.send_bytes(generate_pdf_report(result_dict), "validation_report.pdf")
    return dcc.send_string(generate_csv_report(result_dict), "validation_report.csv")
