#!/usr/bin/env python3
"""
Medical Data Validator - Main Entry Point

Thin shim for running the CLI directly from a repo checkout
(`python medical_data_validator_cli.py ...`). The real implementation
lives in medical_data_validator/cli.py so it ships in the installed
package and backs the `medical-validator` console script.
"""

from medical_data_validator.cli import main

if __name__ == "__main__":
    main()
