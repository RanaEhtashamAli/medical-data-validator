"""
Dash layout and callbacks for the Medical Data Validator Dashboard.
"""

import dash_bootstrap_components as dbc
from dash import dcc, html, Input, Output, State

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
        if contents is None:
            return "Upload a file to start validation", {}, {}, {}, {}
        # Placeholder for now
        return "Validation completed! (Dash integration coming soon)", {}, {}, {}, {} 