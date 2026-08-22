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

from medical_data_validator.dashboard.app import run_production_server

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('api.log'),
        logging.StreamHandler(sys.stdout)
    ]
)


def main():
    """Main entry point for the API server."""
    parser = argparse.ArgumentParser(description='Medical Data Validator API Server')
    parser.add_argument('--host', default='0.0.0.0', help='Host to bind to (default: 0.0.0.0)')
    parser.add_argument('--port', type=int, default=8000, help='Port to bind to (default: 8000)')
    parser.add_argument('--debug', action='store_true', help='Enable debug mode')
    parser.add_argument('--workers', type=int, default=4, help='Number of worker processes (default: 4)')

    args = parser.parse_args()
    run_production_server(host=args.host, port=args.port, workers=args.workers, debug=args.debug)


if __name__ == '__main__':
    main()
