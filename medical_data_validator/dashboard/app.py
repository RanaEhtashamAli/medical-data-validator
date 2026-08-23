"""
Main entry point for the Medical Data Validator Dashboard.
"""

import logging
import sys
import os

# Add the project root to Python path for direct execution
if __name__ == "__main__":
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    sys.path.insert(0, project_root)

import secrets
import traceback
from flask import Flask, jsonify, current_app
import dash
import dash_bootstrap_components as dbc
from dash._callback_context import context_value
from werkzeug.exceptions import HTTPException
from werkzeug.middleware.proxy_fix import ProxyFix

try:
    from medical_data_validator.dashboard.routes import register_routes
    from medical_data_validator.dashboard.dash_layout import setup_dash_layout
except ImportError:
    # Fallback for relative imports when used as package
    from .routes import register_routes
    from .dash_layout import setup_dash_layout

logger = logging.getLogger(__name__)


def create_dashboard_app():
    app = Flask(__name__)
    # Behind Railway's (or any) HTTPS-terminating reverse proxy, Flask would
    # otherwise see plain-HTTP requests and generate http:// redirect/absolute
    # URLs (e.g. the /docs -> /docs/ redirect), forcing an extra downgrade hop.
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)
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

        logger.exception("Unhandled Flask error: %s", e)
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc() if current_app.debug else None,
        }), 500

    # Dash's page auto-discovery (use_pages=True below) calls dash.register_page(),
    # which reads a contextvars.ContextVar that is only ever initialized in the
    # main thread (dash._callback_context sets it once at import time). A thread
    # that never touched this ContextVar sees a bare LookupError instead, which
    # would abort Dash's page registration mid-way and corrupt the global page
    # registry for the rest of the process. Ensure it's initialized in whichever
    # thread is constructing this app.
    if context_value.get(None) is None:
        context_value.set({})

    # Initialize Dash (multi-page: auto-discovers modules under dashboard/pages/)
    dash_app = dash.Dash(
        __name__,
        server=app,
        url_base_pathname='/dash/',
        external_stylesheets=[dbc.themes.BOOTSTRAP],
        use_pages=True,
    )
    setup_dash_layout(dash_app)

    return app


def create_production_app():
    """Build the dashboard app configured for production (non-debug) serving."""
    app = create_dashboard_app()
    app.config.update({
        'TESTING': False,
        'DEBUG': False,
        'JSON_SORT_KEYS': False,
        'JSONIFY_PRETTYPRINT_REGULAR': False,
    })
    return app


def run_production_server(host: str = '0.0.0.0', port: int = 8000, workers: int = 4, debug: bool = False) -> None:
    """Serve the app via Gunicorn if available, else Flask's dev server."""
    app = create_production_app()
    if debug:
        app.config['DEBUG'] = True
        app.run(host=host, port=port, debug=True)
        return
    try:
        import gunicorn.app.base

        class StandaloneApplication(gunicorn.app.base.BaseApplication):
            def __init__(self, app, options=None):
                self.options = options or {}
                self.application = app
                super().__init__()

            def load_config(self):
                for key, value in self.options.items():
                    self.cfg.set(key.lower(), value)

            def load(self):
                return self.application

        options = {
            'bind': f'{host}:{port}',
            'workers': workers,
            'worker_class': 'sync',
            'timeout': 120,
            'keepalive': 2,
            'max_requests': 1000,
            'max_requests_jitter': 100,
            'preload_app': True,
            'access_logfile': '-',
            'error_logfile': '-',
            'loglevel': 'info',
        }
        logger.info("Starting production API server on %s:%s", host, port)
        StandaloneApplication(app, options).run()
    except ImportError:
        logger.warning("Gunicorn not available, using development server")
        app.run(host=host, port=port, debug=False)


def run_dashboard():
    app = create_dashboard_app()
    app.run(host='0.0.0.0', port=5000, debug=True)


if __name__ == '__main__':
    run_dashboard()
