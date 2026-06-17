"""Tests for the pluggable compliance engine, built-in FHIR/SNOMED plugins, and
plugin discovery SDK (Phases 3e and 3f)."""

import pytest
import pandas as pd

from medical_data_validator.compliance import ComplianceEngine, ComplianceStandard, ComplianceViolation
from medical_data_validator.plugins import (
    FHIRCompliancePlugin,
    SNOMEDCompliancePlugin,
    discover_plugins,
    load_compliance_plugins,
)


# ── ComplianceStandard ABC ────────────────────────────────────────────────────

class TestComplianceStandardABC:
    def test_cannot_instantiate_abstract_class(self):
        with pytest.raises(TypeError):
            ComplianceStandard()  # type: ignore

    def test_concrete_subclass_works(self):
        class DummyPlugin(ComplianceStandard):
            @property
            def name(self):
                return 'dummy'
            def validate(self, df):
                return []

        plugin = DummyPlugin()
        assert plugin.name == 'dummy'
        assert plugin.validate(pd.DataFrame()) == []


# ── ComplianceEngine plugin management ───────────────────────────────────────

class TestPluginRegistration:
    def test_register_plugin(self):
        engine = ComplianceEngine()
        engine.register_plugin(FHIRCompliancePlugin())
        assert 'fhir_r4' in engine.list_plugins()

    def test_unregister_plugin(self):
        engine = ComplianceEngine()
        engine.register_plugin(FHIRCompliancePlugin())
        assert engine.unregister_plugin('fhir_r4') is True
        assert 'fhir_r4' not in engine.list_plugins()

    def test_unregister_nonexistent_returns_false(self):
        engine = ComplianceEngine()
        assert engine.unregister_plugin('does_not_exist') is False

    def test_duplicate_registration_replaces(self):
        engine = ComplianceEngine()
        engine.register_plugin(FHIRCompliancePlugin())
        engine.register_plugin(FHIRCompliancePlugin())
        assert engine.list_plugins().count('fhir_r4') == 1

    def test_plugin_results_appear_in_report(self):
        engine = ComplianceEngine()
        engine.register_plugin(FHIRCompliancePlugin())
        df = pd.DataFrame({'patient_id': [1, 2]})
        report = engine.comprehensive_compliance_validation(df)
        assert 'fhir_r4' in report['standards']


# ── FHIRCompliancePlugin ──────────────────────────────────────────────────────

@pytest.fixture
def fhir():
    return FHIRCompliancePlugin()


class TestFHIRPlugin:
    def test_name(self, fhir):
        assert fhir.name == 'fhir_r4'

    def test_valid_resource_type_no_violations(self, fhir):
        df = pd.DataFrame({'resourceType': ['Patient', 'Observation']})
        assert fhir.validate(df) == []

    def test_invalid_resource_type_flagged(self, fhir):
        df = pd.DataFrame({'resourceType': ['Patient', 'NotAResource']})
        violations = fhir.validate(df)
        assert any(v.rule_id == 'FHIR_INVALID_RESOURCE_TYPE' for v in violations)

    def test_valid_id_no_violations(self, fhir):
        df = pd.DataFrame({'id': ['abc-123', 'XYZ.456']})
        assert fhir.validate(df) == []

    def test_invalid_id_flagged(self, fhir):
        df = pd.DataFrame({'id': ['valid', 'too long ' + 'x' * 65]})
        violations = fhir.validate(df)
        assert any(v.rule_id == 'FHIR_INVALID_ID' for v in violations)

    def test_invalid_date_format_flagged(self, fhir):
        df = pd.DataFrame({'date': ['2024-01-15', '15/01/2024', 'not-a-date']})
        violations = fhir.validate(df)
        assert any(v.rule_id == 'FHIR_INVALID_DATE_FORMAT' for v in violations)

    def test_valid_fhir_dates_no_violations(self, fhir):
        df = pd.DataFrame({'date': ['2024', '2024-01', '2024-01-15', '2024-01-15T10:30:00Z']})
        violations = fhir.validate(df)
        date_violations = [v for v in violations if v.rule_id == 'FHIR_INVALID_DATE_FORMAT']
        assert date_violations == []

    def test_empty_df_no_violations(self, fhir):
        assert fhir.validate(pd.DataFrame()) == []

    def test_violations_are_compliance_violation_instances(self, fhir):
        df = pd.DataFrame({'resourceType': ['BadType']})
        violations = fhir.validate(df)
        assert all(isinstance(v, ComplianceViolation) for v in violations)


# ── SNOMEDCompliancePlugin ────────────────────────────────────────────────────

@pytest.fixture
def snomed():
    return SNOMEDCompliancePlugin()


class TestSNOMEDPlugin:
    def test_name(self, snomed):
        assert snomed.name == 'snomed_ct'

    def test_valid_snomed_codes_no_violations(self, snomed):
        df = pd.DataFrame({'snomed_code': ['73211009', '44054006', '38341003']})
        assert snomed.validate(df) == []

    def test_invalid_snomed_code_flagged(self, snomed):
        df = pd.DataFrame({'snomed_code': ['73211009', 'Diabetes mellitus', '123']})
        violations = snomed.validate(df)
        assert any(v.rule_id == 'SNOMED_INVALID_CONCEPT_ID' for v in violations)

    def test_non_snomed_column_ignored(self, snomed):
        df = pd.DataFrame({'diagnosis_text': ['Flu', 'Cold']})
        assert snomed.validate(df) == []

    def test_concept_id_column_detected(self, snomed):
        df = pd.DataFrame({'concept_id': ['abc', 'def']})
        violations = snomed.validate(df)
        assert any(v.rule_id == 'SNOMED_INVALID_CONCEPT_ID' for v in violations)

    def test_empty_column_no_violations(self, snomed):
        df = pd.DataFrame({'snomed_code': [None, None]})
        assert snomed.validate(df) == []

    def test_violations_carry_field_name(self, snomed):
        df = pd.DataFrame({'snomedct': ['not-a-code']})
        violations = snomed.validate(df)
        assert violations[0].field == 'snomedct'


# ── Plugin discovery SDK ──────────────────────────────────────────────────────

class TestDiscoverPlugins:
    def test_discover_returns_list(self):
        plugins = discover_plugins()
        assert isinstance(plugins, list)

    def test_builtin_plugins_discovered(self):
        plugins = discover_plugins(include_builtin=True)
        names = {p.name for p in plugins}
        assert 'fhir_r4' in names
        assert 'snomed_ct' in names

    def test_exclude_builtins(self):
        plugins = discover_plugins(include_builtin=False)
        names = {p.name for p in plugins}
        assert 'fhir_r4' not in names
        assert 'snomed_ct' not in names

    def test_load_compliance_plugins_returns_engine(self):
        engine = load_compliance_plugins()
        from medical_data_validator.compliance import ComplianceEngine
        assert isinstance(engine, ComplianceEngine)

    def test_load_compliance_plugins_populates_engine(self):
        engine = load_compliance_plugins()
        assert 'fhir_r4' in engine.list_plugins()
        assert 'snomed_ct' in engine.list_plugins()

    def test_load_compliance_plugins_accepts_existing_engine(self):
        existing = ComplianceEngine()
        returned = load_compliance_plugins(engine=existing)
        assert returned is existing
        assert 'fhir_r4' in existing.list_plugins()


# ── Integration: both plugins in engine ──────────────────────────────────────

class TestMultiPluginIntegration:
    def test_both_plugins_in_standards(self):
        engine = ComplianceEngine()
        engine.register_plugin(FHIRCompliancePlugin())
        engine.register_plugin(SNOMEDCompliancePlugin())
        df = pd.DataFrame({'patient_id': [1]})
        report = engine.comprehensive_compliance_validation(df)
        assert 'fhir_r4' in report['standards']
        assert 'snomed_ct' in report['standards']

    def test_plugin_violations_in_all_violations(self):
        engine = ComplianceEngine()
        engine.register_plugin(FHIRCompliancePlugin())
        df = pd.DataFrame({'resourceType': ['NotValid']})
        report = engine.comprehensive_compliance_validation(df)
        fhir_ids = {v['rule_id'] for v in report['all_violations'] if isinstance(v, dict)}
        assert 'FHIR_INVALID_RESOURCE_TYPE' in fhir_ids

    def test_builtin_standards_still_present(self):
        engine = ComplianceEngine()
        engine.register_plugin(SNOMEDCompliancePlugin())
        df = pd.DataFrame({'col': ['val']})
        report = engine.comprehensive_compliance_validation(df)
        for standard in ('hipaa', 'gdpr', 'fda', 'medical_coding'):
            assert standard in report['standards']
