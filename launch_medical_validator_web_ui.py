#!/usr/bin/env python3
"""
Standalone entry point for the Medical Data Validator Dashboard.
This script can be run directly to start the web application.
"""

import sys
import os

# Add the project root to the Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from medical_data_validator.dashboard.app import run_dashboard

if __name__ == '__main__':
    print("Starting Medical Data Validator Dashboard...")
    print("Access the application at: http://localhost:5000")
    print("About page: http://localhost:5000/about")
    print("Press Ctrl+C to stop the server")
    run_dashboard() 