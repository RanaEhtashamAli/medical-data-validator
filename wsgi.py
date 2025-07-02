#!/usr/bin/env python3
"""
WSGI entry point for Medical Data Validator Dashboard.
Use this file for production deployment with Gunicorn or uWSGI.
"""

import os
import sys

# Add the project root to the Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from medical_data_validator.dashboard.app import create_dashboard_app

# Create the Flask application
app = create_dashboard_app()

if __name__ == "__main__":
    # For development
    app.run(host='0.0.0.0', port=5000, debug=False) 