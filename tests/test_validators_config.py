"""Tests for create_validator()'s new validators_config parameter."""

import pandas as pd
from medical_data_validator.dashboard.routes import create_validator


def test_no_config_is_unchanged():
    validator = create_validator(detect_phi=False, quality_checks=False, profile='')
    rule_names = [r.name for r in validator.rules]
    assert 'SchemaValidator' not in rule_names
    assert 'RangeValidator' not in rule_names
    assert 'DateValidator' not in rule_names
    assert 'MedicalCodeValidator' not in rule_names


def test_required_columns_adds_schema_validator():
    validator = create_validator(
        detect_phi=False, quality_checks=False, profile='',
        validators_config={'required_columns': ['patient_id']},
    )
    df = pd.DataFrame({'other_column': [1, 2]})
    result = validator.validate(df)
    assert any('patient_id' in i.message for i in result.issues)


def test_ranges_adds_range_validator():
    validator = create_validator(
        detect_phi=False, quality_checks=False, profile='',
        validators_config={'ranges': {'age': {'min': 0, 'max': 120}}},
    )
    df = pd.DataFrame({'age': [150]})
    result = validator.validate(df)
    assert any('above maximum' in i.message for i in result.issues)


def test_date_columns_with_min_max_adds_date_validator():
    validator = create_validator(
        detect_phi=False, quality_checks=False, profile='',
        validators_config={
            'date_columns': ['visit_date'],
            'min_date': '2020-01-01',
            'max_date': '2020-12-31',
        },
    )
    df = pd.DataFrame({'visit_date': ['2025-06-01']})
    result = validator.validate(df)
    assert any('after' in i.message for i in result.issues)


def test_code_columns_adds_medical_code_validator():
    validator = create_validator(
        detect_phi=False, quality_checks=False, profile='',
        validators_config={'code_columns': {'diagnosis_code': 'icd10'}},
    )
    rule_names = [r.name for r in validator.rules]
    assert 'MedicalCodeValidator' in rule_names


import json as _json
from medical_data_validator.dashboard.app import create_dashboard_app


def test_api_validate_data_accepts_validators_query_param():
    app = create_dashboard_app()
    app.config['TESTING'] = True
    with app.test_client() as client:
        validators = _json.dumps({'required_columns': ['patient_id']})
        resp = client.post(
            f'/api/validate/data?validators={validators}',
            json={'other_column': [1, 2]},
        )
        assert resp.status_code == 200
        body = resp.get_json()
        assert any('patient_id' in i['message'] for i in body['issues'])


def test_api_validate_data_rejects_malformed_validators_json():
    app = create_dashboard_app()
    app.config['TESTING'] = True
    with app.test_client() as client:
        resp = client.post('/api/validate/data?validators=not-json', json={'a': [1]})
        assert resp.status_code == 400


def test_profile_with_validators_config_still_applies_validators_config():
    """Regression test: a resolved profile must not silently discard
    validators_config (Fix 3). detect_phi/quality_checks staying discarded
    under a profile is pre-existing/out-of-scope, so they're set to False
    here to isolate the assertion to validators_config only."""
    validator = create_validator(
        detect_phi=False, quality_checks=False, profile='ehr',
        validators_config={'ranges': {'age': {'min': 0, 'max': 120}}},
    )
    rule_names = [r.name for r in validator.rules]
    assert 'RangeValidator' in rule_names
