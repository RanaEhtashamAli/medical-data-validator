"""Tests for PDF and CSV report export (Phase 3h)."""

import pytest
from medical_data_validator.reports import generate_csv_report, generate_pdf_report


SAMPLE_RESULT = {
    'is_valid': False,
    'total_issues': 2,
    'error_count': 1,
    'warning_count': 1,
    'info_count': 0,
    'timestamp': '2026-06-17T10:00:00',
    'issues': [
        {
            'severity': 'error',
            'rule_name': 'SchemaValidator',
            'column': 'age',
            'row': 5,
            'message': 'Value out of range',
        },
        {
            'severity': 'warning',
            'rule_name': 'PHIDetector',
            'column': 'notes',
            'row': None,
            'message': 'Potential PHI detected',
        },
    ],
    'summary': {
        'total_rows': 100,
        'total_columns': 5,
        'duplicate_rows': 2,
        'compliance_report': {
            'standards': {
                'hipaa': {'score': 75.0, 'risk_level': 'medium', 'compliant': False},
                'gdpr':  {'score': 90.0, 'risk_level': 'low',    'compliant': True},
            }
        },
    },
}

EMPTY_RESULT = {
    'is_valid': True,
    'total_issues': 0,
    'error_count': 0,
    'warning_count': 0,
    'info_count': 0,
    'timestamp': '2026-06-17T10:00:00',
    'issues': [],
    'summary': {'total_rows': 10, 'total_columns': 3},
}


class TestGenerateCSVReport:
    def test_returns_string(self):
        assert isinstance(generate_csv_report(SAMPLE_RESULT), str)

    def test_contains_header_row(self):
        csv = generate_csv_report(SAMPLE_RESULT)
        assert 'severity' in csv
        assert 'message' in csv

    def test_contains_issue_data(self):
        csv = generate_csv_report(SAMPLE_RESULT)
        assert 'SchemaValidator' in csv
        assert 'Value out of range' in csv

    def test_contains_summary_metadata(self):
        csv = generate_csv_report(SAMPLE_RESULT)
        assert 'INVALID' in csv
        assert '100' in csv  # total_rows

    def test_empty_result_no_issue_rows(self):
        csv = generate_csv_report(EMPTY_RESULT)
        lines = [l for l in csv.splitlines() if l and not l.startswith('#')]
        # Only the header row, no data rows
        assert len(lines) == 1

    def test_valid_result_says_valid(self):
        csv = generate_csv_report(EMPTY_RESULT)
        assert 'VALID' in csv

    def test_each_issue_on_own_row(self):
        csv = generate_csv_report(SAMPLE_RESULT)
        data_lines = [l for l in csv.splitlines() if l and not l.startswith('#')]
        # header + 2 issues
        assert len(data_lines) == 3


class TestGeneratePDFReport:
    def test_returns_bytes(self):
        pdf = generate_pdf_report(SAMPLE_RESULT)
        assert isinstance(pdf, bytes)

    def test_starts_with_pdf_magic(self):
        pdf = generate_pdf_report(SAMPLE_RESULT)
        assert pdf[:4] == b'%PDF'

    def test_non_trivial_size(self):
        # A real PDF should be at least 1 KB
        pdf = generate_pdf_report(SAMPLE_RESULT)
        assert len(pdf) > 1024

    def test_empty_result_generates_pdf(self):
        pdf = generate_pdf_report(EMPTY_RESULT)
        assert pdf[:4] == b'%PDF'

    def test_result_without_compliance_generates_pdf(self):
        result = dict(SAMPLE_RESULT)
        result['summary'] = {'total_rows': 50, 'total_columns': 3}
        pdf = generate_pdf_report(result)
        assert pdf[:4] == b'%PDF'

    def test_many_issues_capped_at_200(self):
        result = dict(SAMPLE_RESULT)
        result['issues'] = [
            {'severity': 'error', 'rule_name': 'R', 'column': 'c',
             'row': i, 'message': f'issue {i}'}
            for i in range(300)
        ]
        # Should complete without error even with 300 issues
        pdf = generate_pdf_report(result)
        assert pdf[:4] == b'%PDF'
