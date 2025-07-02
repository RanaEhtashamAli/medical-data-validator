#!/usr/bin/env python3
"""
Medical Data Validator API Server

A production-ready REST API for validating healthcare datasets.
Supports HIPAA compliance, medical code validation, and data quality checks.

Usage:
    python api.py
    python api.py --host 0.0.0.0 --port 8000 --debug
"""

import argparse
import logging
import os
import sys
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from medical_data_validator.dashboard.app import create_dashboard_app

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('api.log'),
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)

def create_api_server():
    """Create and configure the API server."""
    app = create_dashboard_app()
    
    # Production configuration
    app.config.update({
        'TESTING': False,
        'DEBUG': False,
        'JSON_SORT_KEYS': False,
        'JSONIFY_PRETTYPRINT_REGULAR': False
    })
    
    return app

def main():
    """Main entry point for the API server."""
    parser = argparse.ArgumentParser(description='Medical Data Validator API Server')
    parser.add_argument('--host', default='0.0.0.0', help='Host to bind to (default: 0.0.0.0)')
    parser.add_argument('--port', type=int, default=8000, help='Port to bind to (default: 8000)')
    parser.add_argument('--debug', action='store_true', help='Enable debug mode')
    parser.add_argument('--workers', type=int, default=4, help='Number of worker processes (default: 4)')
    
    args = parser.parse_args()
    
    # Create the application
    app = create_api_server()
    
    if args.debug:
        app.config['DEBUG'] = True
        logger.info("Starting API server in debug mode")
        app.run(host=args.host, port=args.port, debug=True)
    else:
        # Production server with Gunicorn
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
                'bind': f'{args.host}:{args.port}',
                'workers': args.workers,
                'worker_class': 'sync',
                'timeout': 120,
                'keepalive': 2,
                'max_requests': 1000,
                'max_requests_jitter': 100,
                'preload_app': True,
                'access_logfile': '-',
                'error_logfile': '-',
                'loglevel': 'info'
            }
            
            logger.info(f"Starting production API server on {args.host}:{args.port}")
            StandaloneApplication(app, options).run()
            
        except ImportError:
            logger.warning("Gunicorn not available, using development server")
            logger.info(f"Starting development API server on {args.host}:{args.port}")
            app.run(host=args.host, port=args.port, debug=False)

if __name__ == '__main__':
    main() 