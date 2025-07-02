"""
Medical Data Validator Dashboard

A web-based interface for validating medical datasets with interactive visualizations.
"""

import os
import tempfile
import traceback
from pathlib import Path
from typing import Dict, Any, Optional
import json

import pandas as pd
import plotly.graph_objs as go
import plotly.express as px
from plotly.subplots import make_subplots
from flask import Flask, render_template, request, jsonify, send_file
from werkzeug.utils import secure_filename
import dash
from dash import dcc, html, Input, Output, State
import dash_bootstrap_components as dbc

from .core import MedicalDataValidator, ValidationResult
from .validators import (
    SchemaValidator, PHIDetector, DataQualityChecker,
    MedicalCodeValidator, RangeValidator, DateValidator
)
from .extensions import get_profile


class ValidationDashboard:
    """Web dashboard for medical data validation."""
    
    def __init__(self, debug: bool = False):
        self.app = Flask(__name__)
        self.app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key')
        self.app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size
        
        # Allowed file extensions
        self.allowed_extensions = {'csv', 'xlsx', 'xls', 'json', 'parquet'}
        
        # Setup routes
        self.setup_routes()
        
        # Initialize Dash app
        self.dash_app = dash.Dash(
            __name__,
            server=self.app,
            url_base_pathname='/dash/',
            external_stylesheets=[dbc.themes.BOOTSTRAP]
        )
        self.setup_dash_layout()
        self.setup_dash_callbacks()
    
    def allowed_file(self, filename: str) -> bool:
        """Check if file extension is allowed."""
        return '.' in filename and \
               filename.rsplit('.', 1)[1].lower() in self.allowed_extensions
    
    def setup_routes(self):
        """Setup Flask routes."""
        
        @self.app.route('/')
        def index():
            """Main dashboard page."""
            return render_template('index.html')
        
        @self.app.route('/upload', methods=['POST'])
        def upload_file():
            """Handle file upload and validation."""
            try:
                if 'file' not in request.files:
                    return jsonify({'error': 'No file provided'}), 400
                
                file = request.files['file']
                if file.filename == '':
                    return jsonify({'error': 'No file selected'}), 400
                
                if not self.allowed_file(file.filename):
                    return jsonify({'error': 'File type not allowed'}), 400
                
                # Get validation options
                detect_phi = request.form.get('detect_phi', 'false').lower() == 'true'
                quality_checks = request.form.get('quality_checks', 'false').lower() == 'true'
                profile = request.form.get('profile', '')
                
                # Save uploaded file temporarily
                with tempfile.NamedTemporaryFile(delete=False, suffix=f".{file.filename.rsplit('.', 1)[1]}") as tmp_file:
                    file.save(tmp_file.name)
                    tmp_path = tmp_file.name
                
                # Load data
                data = self.load_data(tmp_path)
                
                # Create validator
                validator = self.create_validator(detect_phi, quality_checks, profile)
                
                # Run validation
                result = validator.validate(data)
                
                # Generate visualizations
                charts = self.generate_charts(data, result)
                
                # Clean up
                os.unlink(tmp_path)
                
                return jsonify({
                    'success': True,
                    'result': result.to_dict(),
                    'charts': charts,
                    'summary': {
                        'total_rows': len(data),
                        'total_columns': len(data.columns),
                        'is_valid': result.is_valid,
                        'total_issues': len(result.issues),
                        'error_count': len([i for i in result.issues if i.severity == 'error']),
                        'warning_count': len([i for i in result.issues if i.severity == 'warning']),
                        'info_count': len([i for i in result.issues if i.severity == 'info'])
                    }
                })
                
            except Exception as e:
                return jsonify({
                    'error': f'Validation failed: {str(e)}',
                    'traceback': traceback.format_exc() if self.app.debug else None
                }), 500
        
        @self.app.route('/profiles')
        def get_profiles():
            """Get available validation profiles."""
            profiles = {
                'clinical_trials': 'Clinical trial data validation',
                'ehr': 'Electronic health records validation',
                'imaging': 'Medical imaging metadata validation',
                'lab': 'Laboratory data validation'
            }
            return jsonify(profiles)
    
    def load_data(self, file_path: str) -> pd.DataFrame:
        """Load data from file."""
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
    
    def create_validator(self, detect_phi: bool, quality_checks: bool, profile: str) -> MedicalDataValidator:
        """Create validator based on options."""
        if profile:
            profile_validator = get_profile(profile)
            if profile_validator:
                return profile_validator.create_validator()
        
        validator = MedicalDataValidator()
        
        if detect_phi:
            validator.add_rule(PHIDetector())
        
        if quality_checks:
            validator.add_rule(DataQualityChecker())
        
        return validator
    
    def generate_charts(self, data: pd.DataFrame, result: ValidationResult) -> Dict[str, Any]:
        """Generate interactive charts for validation results."""
        charts = {}
        
        # Issue severity distribution
        severity_counts = {
            'Error': len([i for i in result.issues if i.severity == 'error']),
            'Warning': len([i for i in result.issues if i.severity == 'warning']),
            'Info': len([i for i in result.issues if i.severity == 'info'])
        }
        
        fig_severity = px.pie(
            values=list(severity_counts.values()),
            names=list(severity_counts.keys()),
            title='Validation Issues by Severity',
            color_discrete_map={'Error': '#d62728', 'Warning': '#ff7f0e', 'Info': '#1f77b4'}
        )
        charts['severity_distribution'] = fig_severity.to_dict()
        
        # Issues by column
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
        
        # Data quality overview
        missing_data = data.isnull().sum()
        if missing_data.sum() > 0:
            fig_missing = px.bar(
                x=missing_data.index,
                y=missing_data.values,
                title='Missing Values by Column',
                labels={'x': 'Column', 'y': 'Missing Count'}
            )
            charts['missing_values'] = fig_missing.to_dict()
        
        # Data types distribution
        dtype_counts = data.dtypes.value_counts()
        fig_dtypes = px.pie(
            values=dtype_counts.values,
            names=dtype_counts.index.astype(str),
            title='Data Types Distribution'
        )
        charts['data_types'] = fig_dtypes.to_dict()
        
        return charts
    
    def setup_dash_layout(self):
        """Setup Dash app layout."""
        self.dash_app.layout = dbc.Container([
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
    
    def setup_dash_callbacks(self):
        """Setup Dash callbacks."""
        
        @self.dash_app.callback(
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
            
            # This would integrate with the Flask backend
            # For now, return placeholder
            return "Validation completed!", {}, {}, {}, {}
    
    def run(self, host: str = '0.0.0.0', port: int = 5000, debug: bool = False):
        """Run the dashboard."""
        self.app.run(host=host, port=port, debug=debug)


def run_dashboard():
    """Entry point for the dashboard."""
    dashboard = ValidationDashboard()
    dashboard.run()


if __name__ == '__main__':
    run_dashboard() 