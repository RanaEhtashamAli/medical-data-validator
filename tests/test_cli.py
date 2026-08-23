"""
Tests for the CLI module.

This module tests command-line interface functionality.
"""

import pytest
import pandas as pd
import tempfile
import os
import json
from unittest.mock import patch, mock_open

from medical_data_validator.cli import (
    load_data,
    create_validator_from_args,
    main,
)


class TestLoadData:
    """Test load_data function."""
    
    def test_load_csv_file(self):
        """Test loading a CSV file."""
        # Create a temporary CSV file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            f.write("patient_id,age,diagnosis\n")
            f.write("001,30,A01.1\n")
            f.write("002,45,B02.2\n")
            temp_file = f.name
        
        try:
            df = load_data(temp_file)
            
            assert isinstance(df, pd.DataFrame)
            assert len(df) == 2
            assert list(df.columns) == ["patient_id", "age", "diagnosis"]
        finally:
            os.unlink(temp_file)
    
    def test_load_excel_file(self):
        """Test loading an Excel file."""
        # Skip if openpyxl is not available
        try:
            import openpyxl
        except ImportError:
            pytest.skip("openpyxl not available")
        
        # Create a temporary Excel file
        df_original = pd.DataFrame({
            "patient_id": ["001", "002"],
            "age": [30, 45],
            "diagnosis": ["A01.1", "B02.2"]
        })
        
        with tempfile.NamedTemporaryFile(suffix='.xlsx', delete=False) as f:
            df_original.to_excel(f.name, index=False)
            temp_file = f.name
        
        try:
            df = load_data(temp_file)
            
            assert isinstance(df, pd.DataFrame)
            assert len(df) == 2
            assert list(df.columns) == ["patient_id", "age", "diagnosis"]
        finally:
            os.unlink(temp_file)
    
    def test_load_nonexistent_file(self):
        """Test loading a non-existent file."""
        with pytest.raises(FileNotFoundError):
            load_data("nonexistent_file.csv")
    
    def test_load_unsupported_format(self):
        """Test loading an unsupported file format."""
        with tempfile.NamedTemporaryFile(suffix='.txt', delete=False) as f:
            f.write(b"test data")
            temp_file = f.name

        try:
            with pytest.raises(ValueError, match="Unsupported file format"):
                load_data(temp_file)
        finally:
            os.unlink(temp_file)

    def test_load_json_file(self, tmp_path):
        """Test loading a JSON file (records-oriented, pandas' default read_json shape)."""
        json_path = tmp_path / "data.json"
        json_path.write_text(
            '[{"patient_id": "001", "age": 30, "diagnosis": "A01.1"},'
            ' {"patient_id": "002", "age": 45, "diagnosis": "B02.2"}]'
        )

        df = load_data(str(json_path))

        assert isinstance(df, pd.DataFrame)
        assert len(df) == 2
        assert list(df.columns) == ["patient_id", "age", "diagnosis"]
        assert df["age"].tolist() == [30, 45]

    @staticmethod
    def _parquet_engine_available():
        try:
            import pyarrow  # noqa: F401
            return True
        except ImportError:
            pass
        try:
            import fastparquet  # noqa: F401
            return True
        except ImportError:
            return False

    def test_load_parquet_file_without_engine_raises_import_error(self, tmp_path):
        """Exercises load_data's '.parquet' branch (calls pd.read_parquet).

        This project declares no parquet engine dependency (pyproject.toml has
        no pyarrow/fastparquet, and .venv has neither installed) -- consistent
        with the gap Task 4 documented for the /api endpoints. Calling
        pd.read_parquet() still executes the branch line even though no engine
        is present, so it raises ImportError before ever touching the
        (nonexistent/invalid) file contents. If a parquet engine is ever added
        to the environment, this test is skipped rather than failing, since
        the ImportError would no longer occur.
        """
        if self._parquet_engine_available():
            pytest.skip("a parquet engine is installed; pd.read_parquet won't raise ImportError")

        parquet_path = tmp_path / "data.parquet"
        parquet_path.write_bytes(b"not a real parquet file")

        with pytest.raises(ImportError):
            load_data(str(parquet_path))


class TestCreateValidatorFromArgs:
    """Test create_validator_from_args function."""
    
    def test_create_basic_validator(self):
        """Test creating a basic validator."""
        # Mock args object
        class MockArgs:
            required_columns = None
            column_types = None
            detect_phi = False
            quality_checks = False
            profile = None
        
        args = MockArgs()
        validator = create_validator_from_args(args)
        
        assert validator is not None
        assert len(validator.rules) == 0
    
    def test_create_validator_with_phi_detection(self):
        """Test creating validator with PHI detection."""
        class MockArgs:
            required_columns = None
            column_types = None
            detect_phi = True
            quality_checks = False
            profile = None
        
        args = MockArgs()
        validator = create_validator_from_args(args)
        
        assert len(validator.rules) == 1
        assert validator.rules[0].__class__.__name__ == "PHIDetector"
    
    def test_create_validator_with_quality_checks(self):
        """Test creating validator with quality checks."""
        class MockArgs:
            required_columns = None
            column_types = None
            detect_phi = False
            quality_checks = True
            profile = None
        
        args = MockArgs()
        validator = create_validator_from_args(args)
        
        assert len(validator.rules) == 1
        assert validator.rules[0].__class__.__name__ == "DataQualityChecker"
    
    def test_create_validator_with_schema_validation(self):
        """Test creating validator with schema validation."""
        class MockArgs:
            required_columns = "patient_id,age"
            column_types = '{"age": "int"}'
            detect_phi = False
            quality_checks = False
            profile = None
        
        args = MockArgs()
        validator = create_validator_from_args(args)
        
        assert len(validator.rules) == 1
        assert validator.rules[0].__class__.__name__ == "SchemaValidator"
    
    def test_create_validator_with_profile(self):
        """Test creating validator with profile."""
        class MockArgs:
            required_columns = None
            column_types = None
            detect_phi = False
            quality_checks = False
            profile = "clinical_trials"
        
        args = MockArgs()
        validator = create_validator_from_args(args)
        
        # Should return profile validator
        assert validator is not None
        assert len(validator.rules) > 0
    
    def test_create_validator_with_nonexistent_profile(self):
        """Test creating validator with non-existent profile."""
        class MockArgs:
            required_columns = None
            column_types = None
            detect_phi = False
            quality_checks = False
            profile = "nonexistent"
        
        args = MockArgs()
        validator = create_validator_from_args(args)
        
        # Should return basic validator with warning
        assert validator is not None
        assert len(validator.rules) == 0


class TestMain:
    """Test main function."""
    
    @patch('medical_data_validator.cli.load_data')
    @patch('medical_data_validator.cli.create_validator_from_args')
    @patch('builtins.print')
    def test_main_success(self, mock_print, mock_create_validator, mock_load_data):
        """Test successful main execution."""
        from medical_data_validator.core import ValidationResult
        
        # Mock the data loading
        mock_df = pd.DataFrame({"col1": [1, 2, 3]})
        mock_load_data.return_value = mock_df
        
        # Mock the validator creation
        mock_validator = mock_create_validator.return_value
        mock_result = ValidationResult(is_valid=True)
        mock_validator.validate.return_value = mock_result
        
        # Create a temporary CSV file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            f.write("col1\n1\n2\n3\n")
            temp_file = f.name
        
        try:
            # Test main function
            with patch('sys.argv', ['medical-validator', 'validate', temp_file]):
                with pytest.raises(SystemExit) as exc_info:
                    main()
                # Should exit with success code (0)
                assert exc_info.value.code == 0

            # Verify function calls
            mock_load_data.assert_called_once_with(temp_file)
            mock_create_validator.assert_called_once()
            mock_validator.validate.assert_called_once_with(mock_df)
        finally:
            os.unlink(temp_file)
    
    @patch('medical_data_validator.cli.load_data')
    @patch('builtins.print')
    def test_main_file_not_found(self, mock_print, mock_load_data):
        """Test main execution with file not found."""
        # Mock file not found error
        mock_load_data.side_effect = FileNotFoundError("File not found")
        
        # Test main function
        with patch('sys.argv', ['medical-validator', 'validate', 'nonexistent.csv']):
            with pytest.raises(SystemExit) as exc_info:
                main()
            
            assert exc_info.value.code == 1
    
    @patch('medical_data_validator.cli.load_data')
    @patch('builtins.print')
    def test_main_value_error(self, mock_print, mock_load_data):
        """Test main execution with value error."""
        # Mock value error
        mock_load_data.side_effect = ValueError("Invalid format")
        
        # Test main function
        with patch('sys.argv', ['medical-validator', 'validate', 'invalid.txt']):
            with pytest.raises(SystemExit) as exc_info:
                main()
            
            assert exc_info.value.code == 1
    
    @patch('medical_data_validator.cli.load_data')
    @patch('medical_data_validator.cli.create_validator_from_args')
    @patch('builtins.open', new_callable=mock_open)
    def test_main_with_output_file(self, mock_file, mock_create_validator, mock_load_data):
        """Test main execution with output file."""
        from medical_data_validator.core import ValidationResult
        
        # Mock the data loading
        mock_df = pd.DataFrame({"col1": [1, 2, 3]})
        mock_load_data.return_value = mock_df
        
        # Mock the validator creation
        mock_validator = mock_create_validator.return_value
        mock_result = ValidationResult(is_valid=True)
        mock_validator.validate.return_value = mock_result
        
        # Create a temporary CSV file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            f.write("col1\n1\n2\n3\n")
            temp_file = f.name
        
        try:
            # Test main function with output file
            with patch('sys.argv', ['medical-validator', 'validate', temp_file, '--output', 'output.txt']):
                with pytest.raises(SystemExit) as exc_info:
                    main()
                # Should exit with success code (0)
                assert exc_info.value.code == 0
            
            # Verify file was opened for writing (allow for any kwargs)
            found = False
            for call in mock_file.call_args_list:
                # Check if this call opens output.txt for writing
                if hasattr(call, 'args') and len(call.args) >= 2:
                    # Handle both string and Path objects
                    first_arg = str(call.args[0])
                    if 'output.txt' in first_arg and call.args[1] == 'w':
                        found = True
                        break
                elif len(call[0]) >= 2:
                    # Handle both string and Path objects
                    first_arg = str(call[0][0])
                    if 'output.txt' in first_arg and call[0][1] == 'w':
                        found = True
                        break
            
            # If not found, let's check what calls were actually made
            if not found:
                print(f"Mock calls made: {mock_file.call_args_list}")
                # Check if any call contains 'output.txt'
                for call in mock_file.call_args_list:
                    if hasattr(call, 'args') and 'output.txt' in str(call.args):
                        print(f"Found call with output.txt in args: {call}")
                    elif 'output.txt' in str(call[0]):
                        print(f"Found call with output.txt in positional args: {call}")
            
            assert found, 'output.txt was not opened for writing'
        finally:
            os.unlink(temp_file)
    
    @patch('medical_data_validator.cli.load_data')
    @patch('medical_data_validator.cli.create_validator_from_args')
    @patch('builtins.print')
    def test_main_json_output(self, mock_print, mock_create_validator, mock_load_data):
        """Test main execution with JSON output."""
        from medical_data_validator.core import ValidationResult
        
        # Mock the data loading
        mock_df = pd.DataFrame({"col1": [1, 2, 3]})
        mock_load_data.return_value = mock_df
        
        # Mock the validator creation
        mock_validator = mock_create_validator.return_value
        mock_result = ValidationResult(is_valid=True)
        mock_validator.validate.return_value = mock_result
        
        # Create a temporary CSV file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            f.write("col1\n1\n2\n3\n")
            temp_file = f.name
        
        try:
            # Test main function with JSON output
            with patch('sys.argv', ['medical-validator', 'validate', temp_file, '--format', 'json']):
                with pytest.raises(SystemExit) as exc_info:
                    main()
                # Should exit with success code (0)
                assert exc_info.value.code == 0
            
            # Should print JSON output
            mock_print.assert_called()
        finally:
            os.unlink(temp_file)
    
    def test_main_no_arguments(self):
        """Test main execution with no arguments."""
        with patch('sys.argv', ['medical-validator']):
            with pytest.raises(SystemExit) as exc_info:
                main()
            
            # Should exit with error code (2 for argument parsing error)
            assert exc_info.value.code == 2


class TestCLIIntegration:
    """Test CLI integration scenarios."""
    
    def test_cli_with_problematic_data(self):
        """Test CLI with data that has validation issues."""
        # Create a temporary CSV file with problematic data
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            f.write("patient_name,ssn,age\n")  # PHI columns
            f.write("John Doe,123-45-6789,30\n")  # Contains SSN
            f.write("Jane Smith,987-65-4321,45\n")  # Contains SSN
            temp_file = f.name
        
        try:
            # Load data
            df = load_data(temp_file)
            
            # Create validator with PHI detection
            class MockArgs:
                required_columns = None
                column_types = None
                detect_phi = True
                quality_checks = False
                profile = None
            
            args = MockArgs()
            validator = create_validator_from_args(args)
            
            # Run validation
            result = validator.validate(df)
            
            # Should have PHI detection issues
            assert len(result.issues) > 0
            phi_issues = [issue for issue in result.issues if "PHI" in issue.message or "SSN" in issue.message]
            assert len(phi_issues) > 0
        finally:
            os.unlink(temp_file)
    
    def test_cli_with_valid_data(self):
        """Test CLI with valid data."""
        # Create a temporary CSV file with valid clinical trial data
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            f.write("subject_id,visit_date,treatment_group,age,bmi\n")
            f.write("001,2020-01-01,A,25,22.5\n")
            f.write("002,2020-01-02,B,30,24.0\n")
            temp_file = f.name
        
        try:
            # Load data
            df = load_data(temp_file)
            
            # Convert visit_date to datetime and subject_id to string
            df["visit_date"] = pd.to_datetime(df["visit_date"])
            df["subject_id"] = df["subject_id"].astype(str)
            
            # Create validator with clinical trials profile
            class MockArgs:
                required_columns = None
                column_types = None
                detect_phi = False
                quality_checks = False
                profile = "clinical_trials"
            
            args = MockArgs()
            validator = create_validator_from_args(args)
            
            # Run validation
            result = validator.validate(df)
            
            # Should be valid since data matches profile requirements
            # Check that there are no errors (only warnings/info are acceptable)
            error_issues = [issue for issue in result.issues if issue.severity == "error"]
            assert len(error_issues) == 0, f"Found errors: {error_issues}"
        finally:
            os.unlink(temp_file)


class TestConsolidatedCLI:
    """Regression tests for the Phase A CLI consolidation/packaging fix."""

    def test_console_script_module_imports_cleanly(self):
        """The entry point pyproject.toml declares must actually be
        importable — this is exactly the gap that let a broken console
        script ship undetected."""
        import importlib
        module = importlib.import_module("medical_data_validator.cli")
        assert hasattr(module, "main")

    def test_cli_has_all_six_subcommands(self, capsys):
        from medical_data_validator.cli import main
        import sys
        old_argv = sys.argv
        try:
            sys.argv = ["medical-validator", "--help"]
            try:
                main()
            except SystemExit:
                pass
        finally:
            sys.argv = old_argv
        out = capsys.readouterr().out
        for cmd in ("validate", "dashboard", "api", "benchmark", "compliance", "demo"):
            assert cmd in out

    def test_compliance_subcommand_builds_code_validator_without_error(self, tmp_path):
        """The old code called MedicalCodeValidator.add_code_type(), which
        doesn't exist. This must not raise for the default --standards."""
        from medical_data_validator.cli import run_compliance_check
        import argparse

        csv_path = tmp_path / "data.csv"
        pd.DataFrame({"diagnosis_code": ["A00.0"], "test_code": ["1234-5"]}).to_csv(csv_path, index=False)

        args = argparse.Namespace(
            file=str(csv_path),
            standards=["hipaa", "icd10", "loinc"],
            output=None,
        )
        run_compliance_check(args)  # must not raise

    def test_dashboard_subcommand_imports_real_symbol(self):
        """The old code imported a module-level `app` that doesn't exist in
        dashboard.app. Must import create_dashboard_app instead."""
        from medical_data_validator.dashboard.app import create_dashboard_app
        app = create_dashboard_app()
        assert app is not None

    def test_benchmark_subcommand_imports_real_module(self):
        """The old code imported run_enhanced_benchmarks/run_real_benchmarks,
        neither of which exist anywhere in the repo."""
        from benchmarks.run_benchmarks import main as benchmark_main
        assert callable(benchmark_main)


class TestValidatorConfigFlags:
    def test_range_flag_adds_range_validator(self):
        from medical_data_validator.cli import create_validator_from_args
        import argparse
        args = argparse.Namespace(
            required_columns=None, column_types=None, detect_phi=False,
            quality_checks=False, profile=None,
            range=['age:0:120'], date_column=None, min_date=None, max_date=None,
            code_column=None,
        )
        validator = create_validator_from_args(args)
        rule_names = [r.name for r in validator.rules]
        assert 'RangeValidator' in rule_names

    def test_date_column_flag_adds_date_validator(self):
        from medical_data_validator.cli import create_validator_from_args
        import argparse
        args = argparse.Namespace(
            required_columns=None, column_types=None, detect_phi=False,
            quality_checks=False, profile=None,
            range=None, date_column=['visit_date'], min_date='2020-01-01', max_date='2020-12-31',
            code_column=None,
        )
        validator = create_validator_from_args(args)
        rule_names = [r.name for r in validator.rules]
        assert 'DateValidator' in rule_names

    def test_code_column_flag_adds_medical_code_validator(self):
        from medical_data_validator.cli import create_validator_from_args
        import argparse
        args = argparse.Namespace(
            required_columns=None, column_types=None, detect_phi=False,
            quality_checks=False, profile=None,
            range=None, date_column=None, min_date=None, max_date=None,
            code_column=['diagnosis_code:icd10'],
        )
        validator = create_validator_from_args(args)
        rule_names = [r.name for r in validator.rules]
        assert 'MedicalCodeValidator' in rule_names

    def test_profile_with_range_flag_still_applies_range_flag(self):
        """Regression test: a resolved --profile must not silently discard
        --range/--date-column/--code-column flags (Fix 3). Pre-existing
        discard of --required-columns/--column-types/--detect-phi/
        --quality-checks under --profile is out of scope."""
        from medical_data_validator.cli import create_validator_from_args
        import argparse
        args = argparse.Namespace(
            required_columns=None, column_types=None, detect_phi=False,
            quality_checks=False, profile='ehr',
            range=['age:0:120'], date_column=None, min_date=None, max_date=None,
            code_column=None,
        )
        validator = create_validator_from_args(args)
        rule_names = [r.name for r in validator.rules]
        assert 'RangeValidator' in rule_names

    def test_validate_subcommand_accepts_new_flags(self, tmp_path):
        import subprocess, sys
        csv_path = tmp_path / "data.csv"
        csv_path.write_text("age,diagnosis_code\n150,E11.9\n")
        result = subprocess.run(
            [sys.executable, "-m", "medical_data_validator.cli", "validate", str(csv_path),
             "--range", "age:0:120", "--code-column", "diagnosis_code:icd10", "--format", "summary"],
            capture_output=True, text=True,
        )
        assert "Total Issues" in result.stdout


class TestRunValidateOutputBranches:
    """Direct (non-subprocess) tests for run_validate's --verbose and
    --output branches, so coverage.py can credit them (subprocess-executed
    code, like TestConsolidatedCLI's tests, isn't traced)."""

    @staticmethod
    def _base_args(file, **overrides):
        import argparse
        defaults = dict(
            file=file, profile=None, required_columns=None, column_types=None,
            range=None, date_column=None, min_date=None, max_date=None,
            code_column=None, detect_phi=False, quality_checks=False,
            output=None, format="text", verbose=False,
        )
        defaults.update(overrides)
        return argparse.Namespace(**defaults)

    def test_verbose_prints_loading_row_count_and_rule_count(self, tmp_path, capsys):
        from medical_data_validator.cli import run_validate
        csv_path = tmp_path / "data.csv"
        csv_path.write_text("age,diagnosis_code\n30,A01.1\n45,B02.2\n")
        args = self._base_args(str(csv_path), verbose=True, detect_phi=True)

        with pytest.raises(SystemExit):
            run_validate(args)

        out = capsys.readouterr().out
        assert f"Loading data from {csv_path}..." in out
        assert "Loaded 2 rows and 2 columns" in out
        assert "Running validation with 1 rules..." in out

    def test_non_verbose_does_not_print_progress_lines(self, tmp_path, capsys):
        """Sanity check that the verbose branches are actually gated."""
        from medical_data_validator.cli import run_validate
        csv_path = tmp_path / "data.csv"
        csv_path.write_text("age\n30\n")
        args = self._base_args(str(csv_path), verbose=False)

        with pytest.raises(SystemExit):
            run_validate(args)

        out = capsys.readouterr().out
        assert "Loading data from" not in out
        assert "Loaded" not in out
        assert "Running validation with" not in out

    def test_output_json_writes_file_and_prints_confirmation(self, tmp_path, capsys):
        from medical_data_validator.cli import run_validate
        csv_path = tmp_path / "data.csv"
        csv_path.write_text("age\n30\n45\n")
        out_path = tmp_path / "results.json"
        args = self._base_args(str(csv_path), output=str(out_path), format="json")

        with pytest.raises(SystemExit) as exc_info:
            run_validate(args)
        assert exc_info.value.code == 0

        assert out_path.exists()
        saved = json.loads(out_path.read_text())
        assert saved["is_valid"] is True
        assert saved["total_issues"] == 0
        assert "summary" in saved

        out = capsys.readouterr().out
        assert f"Results saved to {out_path}" in out

    def test_output_text_format_writes_report_file(self, tmp_path, capsys):
        """The --output branch for non-JSON formats (get_report to file)."""
        from medical_data_validator.cli import run_validate
        csv_path = tmp_path / "data.csv"
        csv_path.write_text("age\n30\n45\n")
        out_path = tmp_path / "report.txt"
        args = self._base_args(str(csv_path), output=str(out_path), format="text")

        with pytest.raises(SystemExit):
            run_validate(args)

        assert out_path.exists()
        content = out_path.read_text()
        assert len(content) > 0

        out = capsys.readouterr().out
        assert f"Report saved to {out_path}" in out

    def test_summary_format_prints_all_fields(self, tmp_path, capsys):
        """Optional direct unit test for the summary-format print block
        (lines ~145-152). Already has real behavioral coverage via
        TestConsolidatedCLI's subprocess-based test; this is only to make
        coverage.py credit it directly, per the task brief's suggestion."""
        from medical_data_validator.cli import run_validate
        csv_path = tmp_path / "data.csv"
        csv_path.write_text("age\n30\n45\n")
        args = self._base_args(str(csv_path), format="summary")

        with pytest.raises(SystemExit) as exc_info:
            run_validate(args)
        assert exc_info.value.code == 0

        out = capsys.readouterr().out
        assert "Validation Summary:" in out
        assert "Valid: True" in out
        assert "Compliant:" in out
        assert "Total Issues: 0" in out
        assert "Errors: 0" in out
        assert "Warnings: 0" in out
        assert "Info: 0" in out


class TestRunComplianceCheckBranches:
    """Direct tests for run_compliance_check's CPT branch and --output branch."""

    def test_cpt_standard_reports_invalid_codes(self, tmp_path, capsys):
        from medical_data_validator.cli import run_compliance_check
        import argparse

        csv_path = tmp_path / "data.csv"
        pd.DataFrame({"procedure_code": ["not-a-cpt-code"]}).to_csv(csv_path, index=False)

        args = argparse.Namespace(
            file=str(csv_path),
            standards=["cpt"],
            output=None,
        )
        run_compliance_check(args)

        out = capsys.readouterr().out
        assert "Checking compliance with standards: cpt" in out
        assert "CPT:" in out
        assert "Non-compliant" in out
        assert "invalid codes" in out

    def test_cpt_standard_compliant_when_codes_valid(self, tmp_path, capsys):
        from medical_data_validator.cli import run_compliance_check
        import argparse

        csv_path = tmp_path / "data.csv"
        # MedicalCodeValidator's "cpt" pattern accepts a real 5-digit
        # Category I code (e.g. "99213") or a 4-digit Category II/III code
        # suffixed with F or T. A bare 4-digit code with no letter (e.g.
        # "1234") is NOT valid -- see test_cpt_four_digit_only_code_is_non_compliant.
        pd.DataFrame({"procedure_code": ["99213"]}).to_csv(csv_path, index=False)

        args = argparse.Namespace(
            file=str(csv_path),
            standards=["cpt"],
            output=None,
        )
        run_compliance_check(args)

        out = capsys.readouterr().out
        assert "CPT: Compliant (0 invalid codes)" in out

    def test_cpt_four_digit_only_code_is_non_compliant(self, tmp_path, capsys):
        """A bare 4-digit code with no F/T letter suffix (e.g. "1234") does
        not match the fixed CPT regex and must be reported non-compliant --
        this was wrongly reported compliant before the regex fix."""
        from medical_data_validator.cli import run_compliance_check
        import argparse

        csv_path = tmp_path / "data.csv"
        pd.DataFrame({"procedure_code": ["1234"]}).to_csv(csv_path, index=False)

        args = argparse.Namespace(
            file=str(csv_path),
            standards=["cpt"],
            output=None,
        )
        run_compliance_check(args)

        out = capsys.readouterr().out
        assert "CPT: Non-compliant" in out
        assert "invalid codes" in out

    def test_output_writes_compliance_report_file(self, tmp_path, capsys):
        from medical_data_validator.cli import run_compliance_check
        import argparse

        csv_path = tmp_path / "data.csv"
        pd.DataFrame({"diagnosis_code": ["A00.0"]}).to_csv(csv_path, index=False)
        out_path = tmp_path / "compliance.json"

        args = argparse.Namespace(
            file=str(csv_path),
            standards=["icd10"],
            output=str(out_path),
        )
        run_compliance_check(args)

        assert out_path.exists()
        saved = json.loads(out_path.read_text())
        assert saved["standards_checked"] == ["icd10"]
        assert "overall_compliant" in saved
        assert "total_issues" in saved
        assert "compliance_details" in saved
        assert "is_valid" in saved["compliance_details"]

        out = capsys.readouterr().out
        assert f"Compliance report saved to: {out_path}" in out


class TestMainDispatchAndExceptionHandling:
    """Tests for main()'s command dispatch and top-level exception handling."""

    def test_main_dispatches_compliance_command(self, tmp_path, capsys):
        """Exercises the 'compliance' branch of main()'s dispatch chain
        end-to-end (real argv parsing, real file, real validation)."""
        csv_path = tmp_path / "data.csv"
        pd.DataFrame({"diagnosis_code": ["A00.0"]}).to_csv(csv_path, index=False)

        with patch('sys.argv', ['medical-validator', 'compliance', str(csv_path), '--standards', 'icd10']):
            # run_compliance_check doesn't call sys.exit, so main() should
            # return normally rather than raise SystemExit.
            main()

        out = capsys.readouterr().out
        assert "Checking compliance with standards: icd10" in out
        assert "Compliance Report:" in out

    def test_main_dispatches_demo_command_not_found_fallback(self, capsys):
        """Exercises the 'demo' branch of main()'s dispatch chain. demo.py
        exists at this repo's root, so running the real demo would have
        real side effects (out of scope per the task brief); Path.exists is
        patched to force the cheap 'not found' fallback instead, which is
        the only demo behavior worth testing directly here."""
        from pathlib import Path

        with patch('sys.argv', ['medical-validator', 'demo']):
            with patch.object(Path, 'exists', return_value=False):
                with pytest.raises(SystemExit) as exc_info:
                    main()

        assert exc_info.value.code == 1
        out = capsys.readouterr().out
        assert "Demo requires running from the repo root" in out

    def test_main_real_file_not_found(self, tmp_path, capsys):
        """Real (non-mocked) FileNotFoundError: load_data() itself raises it
        because the file genuinely doesn't exist."""
        missing = tmp_path / "does_not_exist.csv"

        with patch('sys.argv', ['medical-validator', 'validate', str(missing)]):
            with pytest.raises(SystemExit) as exc_info:
                main()

        assert exc_info.value.code == 1
        err = capsys.readouterr().err
        assert f"Error: File '{missing}' not found." in err

    def test_main_real_malformed_range_spec_raises_value_error(self, tmp_path, capsys):
        """Real (non-mocked) ValueError: a --range spec without the
        required COLUMN:MIN:MAX shape fails to unpack in
        _apply_range_date_code_flags."""
        csv_path = tmp_path / "data.csv"
        csv_path.write_text("age\n30\n")

        with patch('sys.argv', ['medical-validator', 'validate', str(csv_path), '--range', 'not-a-valid-spec']):
            with pytest.raises(SystemExit) as exc_info:
                main()

        assert exc_info.value.code == 1
        err = capsys.readouterr().err
        assert err.startswith("Error:")

    def test_main_keyboard_interrupt_exits_zero(self, capsys):
        """KeyboardInterrupt during a command must exit cleanly (code 0)
        with a friendly cancellation message, not propagate as a crash."""
        with patch('medical_data_validator.cli.load_data', side_effect=KeyboardInterrupt()):
            with patch('sys.argv', ['medical-validator', 'validate', 'whatever.csv']):
                with pytest.raises(SystemExit) as exc_info:
                    main()

        assert exc_info.value.code == 0
        out = capsys.readouterr().out
        assert "Operation cancelled by user." in out

    def test_main_generic_exception_prints_unexpected_error(self, capsys):
        """A non-FileNotFoundError, non-ValueError exception must fall
        through to the generic handler and exit 1."""
        with patch('medical_data_validator.cli.load_data', side_effect=RuntimeError("boom")):
            with patch('sys.argv', ['medical-validator', 'validate', 'whatever.csv']):
                with pytest.raises(SystemExit) as exc_info:
                    main()

        assert exc_info.value.code == 1
        err = capsys.readouterr().err
        assert "Unexpected error: boom" in err

    def test_main_generic_exception_verbose_prints_traceback(self, capsys):
        """With --verbose, the generic exception handler must also print a
        full traceback (not just the one-line message)."""
        with patch('medical_data_validator.cli.load_data', side_effect=RuntimeError("boom")):
            with patch('sys.argv', ['medical-validator', 'validate', 'whatever.csv', '--verbose']):
                with pytest.raises(SystemExit) as exc_info:
                    main()

        assert exc_info.value.code == 1
        err = capsys.readouterr().err
        assert "Unexpected error: boom" in err
        assert "Traceback (most recent call last)" in err
        assert "RuntimeError: boom" in err


if __name__ == "__main__":
    pytest.main([__file__])