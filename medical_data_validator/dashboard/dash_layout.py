"""
Dash layout and callbacks for the Medical Data Validator Dashboard.
"""

import base64

import dash_bootstrap_components as dbc
from dash import dcc, html, Input, Output, State

from .utils import dataframe_from_upload_bytes, generate_charts

def setup_dash_layout(dash_app):
    dash_app.layout = dbc.Container([
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
        ])
    ], fluid=True)

def _run_validation_for_upload(contents, filename, options, profile):
    """Parse an uploaded file, run validation, and build the 4 chart figures.
    Extracted from the Dash callback so it's directly testable without a
    running Dash app."""
    if contents is None:
        return "Upload a file to start validation", {}, {}, {}, {}

    from .routes import create_validator

    _header, b64data = contents.split(',', 1)
    raw_bytes = base64.b64decode(b64data)

    try:
        df = dataframe_from_upload_bytes(filename or '', raw_bytes)
    except Exception as exc:
        return f"Could not parse {filename}: {exc}", {}, {}, {}, {}

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
    )


def setup_dash_callbacks(dash_app):
    @dash_app.callback(
        [Output('validation-results', 'children'),
         Output('severity-chart', 'figure'),
         Output('column-chart', 'figure'),
         Output('missing-chart', 'figure'),
         Output('dtype-chart', 'figure')],
        [Input('upload-data', 'contents')],
        [State('upload-data', 'filename'),
         State('validation-options', 'value'),
         State('profile-dropdown', 'value')]
    )
    def update_output(contents, filename, options, profile):
        return _run_validation_for_upload(contents, filename, options, profile) 