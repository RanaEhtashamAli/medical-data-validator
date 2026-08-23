"""Tests for MedicalDataValidator.anonymize() (Phase 3c)."""

import pandas as pd
import pytest

from medical_data_validator.core import MedicalDataValidator


@pytest.fixture
def validator():
    return MedicalDataValidator(
        enable_compliance=False, enable_analytics=False, enable_monitoring=False
    )


@pytest.fixture
def phi_df():
    return pd.DataFrame({
        'patient_name': ['Alice Smith', 'Bob Jones'],
        'ssn': ['123-45-6789', '987-65-4321'],
        'email': ['alice@example.com', 'bob@example.com'],
        'age': [30, 45],
        'diagnosis': ['Flu', 'Cold'],
    })


class TestAnonymizeMethod:
    def test_returns_dataframe(self, validator, phi_df):
        result = validator.anonymize(phi_df)
        assert isinstance(result, pd.DataFrame)

    def test_original_unchanged(self, validator, phi_df):
        original_name = phi_df['patient_name'].iloc[0]
        validator.anonymize(phi_df)
        assert phi_df['patient_name'].iloc[0] == original_name

    def test_auto_detects_phi_columns(self, validator, phi_df):
        result = validator.anonymize(phi_df)
        # PHI columns should be changed; non-PHI should be unchanged
        assert result['patient_name'].iloc[0] != phi_df['patient_name'].iloc[0]
        assert result['diagnosis'].tolist() == phi_df['diagnosis'].tolist()

    def test_explicit_columns(self, validator, phi_df):
        result = validator.anonymize(phi_df, columns=['ssn'])
        assert result['ssn'].iloc[0] != '123-45-6789'
        assert result['email'].tolist() == phi_df['email'].tolist()

    def test_non_phi_columns_unchanged(self, validator, phi_df):
        result = validator.anonymize(phi_df)
        assert result['age'].tolist() == phi_df['age'].tolist()

    def test_hipaa_safe_harbor_method(self, validator, phi_df):
        result = validator.anonymize(phi_df, columns=['patient_name'], method='hipaa_safe_harbor')
        assert result['patient_name'].iloc[0].startswith('Patient_')

    def test_hash_method(self, validator, phi_df):
        result = validator.anonymize(phi_df, columns=['ssn'], method='hash')
        val = result['ssn'].iloc[0]
        assert val is not None
        assert val != '123-45-6789'

    def test_mask_method(self, validator, phi_df):
        result = validator.anonymize(phi_df, columns=['ssn'], method='mask')
        val = result['ssn'].iloc[0]
        assert '***' in str(val)

    def test_invalid_method_raises(self, validator, phi_df):
        with pytest.raises(ValueError, match="Unknown anonymization method"):
            validator.anonymize(phi_df, columns=['ssn'], method='magic')

    def test_accepts_dict_input(self, validator):
        data = {'name': ['Charlie'], 'score': [99]}
        result = validator.anonymize(data, columns=['name'])
        assert isinstance(result, pd.DataFrame)
        assert result['name'].iloc[0] != 'Charlie'

    def test_accepts_list_of_dicts(self, validator):
        data = [{'name': 'Dave', 'score': 88}]
        result = validator.anonymize(data, columns=['name'])
        assert isinstance(result, pd.DataFrame)

    def test_empty_columns_list_leaves_data_unchanged(self, validator, phi_df):
        result = validator.anonymize(phi_df, columns=[])
        assert result.equals(phi_df)

    def test_row_count_preserved(self, validator, phi_df):
        result = validator.anonymize(phi_df)
        assert len(result) == len(phi_df)

    def test_column_count_preserved(self, validator, phi_df):
        result = validator.anonymize(phi_df)
        assert list(result.columns) == list(phi_df.columns)

    def test_invalid_data_type_raises_value_error(self, validator):
        with pytest.raises(ValueError, match="data must be"):
            validator.anonymize(12345)  # type: ignore

    def test_raises_runtime_error_when_data_anonymizer_unavailable(
        self, validator, phi_df, monkeypatch
    ):
        import medical_data_validator.core as core_module

        monkeypatch.setattr(core_module, "DataAnonymizer", None)

        with pytest.raises(RuntimeError, match="DataAnonymizer is not available"):
            validator.anonymize(phi_df)
