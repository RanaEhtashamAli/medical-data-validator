"""
Main entry point for the Medical Data Validator Dashboard.
"""

import sys
import os

# Add the project root to Python path for direct execution
if __name__ == "__main__":
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    sys.path.insert(0, project_root)

import secrets
from flask import Flask, jsonify
import dash
import dash_bootstrap_components as dbc
from werkzeug.exceptions import HTTPException

try:
    from medical_data_validator.dashboard.routes import register_routes
    from medical_data_validator.dashboard.dash_layout import setup_dash_layout, setup_dash_callbacks
except ImportError:
    # Fallback for relative imports when used as package
    from .routes import register_routes
    from .dash_layout import setup_dash_layout, setup_dash_callbacks


def create_dashboard_app():
    app = Flask(__name__)
    secret_key = os.environ.get('SECRET_KEY')
    if not secret_key:
        if os.environ.get('FLASK_ENV') == 'production':
            raise RuntimeError(
                "SECRET_KEY environment variable must be set in production. "
                "Generate one with: python -c \"import secrets; print(secrets.token_hex(32))\""
            )
        secret_key = secrets.token_hex(32)
    app.config['SECRET_KEY'] = secret_key
    app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

    # Register Flask routes
    register_routes(app)

    @app.errorhandler(Exception)
    def handle_exception(e):
        # Don't handle HTTP exceptions (like 404, 405, etc.)
        if isinstance(e, HTTPException):
            return e
        
        import traceback
        print("GLOBAL FLASK ERROR:", e)
        print(traceback.format_exc())
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500

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