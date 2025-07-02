"""
Tests for the CLI module.

This module tests command-line interface functionality.
"""

import pytest
import pandas as pd
import tempfile
import os
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
            with patch('sys.argv', ['medical-validator', temp_file]):
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
        with patch('sys.argv', ['medical-validator', 'nonexistent.csv']):
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
        with patch('sys.argv', ['medical-validator', 'invalid.txt']):
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
            with patch('sys.argv', ['medical-validator', temp_file, '--output', 'output.txt']):
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
            with patch('sys.argv', ['medical-validator', temp_file, '--format', 'json']):
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


if __name__ == "__main__":
    pytest.main([__file__]) 