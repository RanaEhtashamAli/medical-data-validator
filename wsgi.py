#!/usr/bin/env python3
"""
WSGI entry point for the Medical Data Validator Dashboard.
This file is used by Gunicorn to serve the Flask application.
"""

import sys
import os

# Add the project root to Python path
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

from medical_data_validator.dashboard.app import create_dashboard_app

# Create the Flask application
app = create_dashboard_app()

if __name__ == "__main__":
    app.run() 