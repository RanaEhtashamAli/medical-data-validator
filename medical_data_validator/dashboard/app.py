"""
Main entry point for the Medical Data Validator Dashboard.
"""

import sys
import os

# Add the project root to Python path for direct execution
if __name__ == "__main__":
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    sys.path.insert(0, project_root)

from flask import Flask
import dash
import dash_bootstrap_components as dbc

try:
    from medical_data_validator.dashboard.routes import register_routes
    from medical_data_validator.dashboard.dash_layout import setup_dash_layout, setup_dash_callbacks
except ImportError:
    # Fallback for relative imports when used as package
    from .routes import register_routes
    from .dash_layout import setup_dash_layout, setup_dash_callbacks


def create_dashboard_app():
    app = Flask(__name__)
    app.config['SECRET_KEY'] = 'dev-secret-key'
    app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

    # Register Flask routes
    register_routes(app)

    # Initialize Dash
    dash_app = dash.Dash(
        __name__,
        server=app,
        url_base_pathname='/dash/',
        external_stylesheets=[dbc.themes.BOOTSTRAP]
    )
    setup_dash_layout(dash_app)
    setup_dash_callbacks(dash_app)

    return app


def run_dashboard():
    app = create_dashboard_app()
    app.run(host='0.0.0.0', port=5000, debug=True)


if __name__ == '__main__':
    run_dashboard() 