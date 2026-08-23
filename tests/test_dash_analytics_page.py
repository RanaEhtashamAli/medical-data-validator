"""Tests for the Dash Analytics page's extracted callback logic."""

import base64
import json

# dashboard.pages.analytics calls dash.register_page() at import time, which
# requires dash.Dash(use_pages=True) to have already run at least once in
# this process (it populates Dash's internal page-registry config). Building
# the dashboard app here — before importing the page module directly below —
# lets this test file pass in isolation, not just as part of the full suite.
# (Same pattern as tests/test_dash_security_page.py and
# tests/test_dash_anonymize_page.py.)
from medical_data_validator.dashboard.app import create_dashboard_app
create_dashboard_app()


def _make_upload_contents(raw_bytes: bytes, mime: str = 'text/csv') -> str:
    """Build a dcc.Upload-style 'contents' string: 'data:<mime>;base64,<b64>'."""
    encoded = base64.b64encode(raw_bytes).decode()
    return f"data:{mime};base64,{encoded}"


NUMERIC_CSV = b"""patient_id,age,weight,visit_date
1,45,70.5,2023-01-01
2,52,80.2,2023-02-01
3,38,65.0,2023-03-01
4,60,90.1,2023-04-01
5,29,55.3,2023-05-01
"""


def test_run_analytics_from_upload_returns_full_report():
    from medical_data_validator.dashboard.pages.analytics import _run_analytics_from_upload
    contents = _make_upload_contents(NUMERIC_CSV)

    result = _run_analytics_from_upload(contents, 'patients.csv', '')

    assert 'error' not in result
    assert 'overall_quality_score' in result
    assert 'quality_metrics' in result
    assert 'anomalies' in result
    assert 'statistical_summary' in result
    assert 'trends' in result
    # No raw numpy types survive — must be plain JSON-serializable.
    json.dumps(result)


def test_run_analytics_from_upload_with_time_column():
    from medical_data_validator.dashboard.pages.analytics import _run_analytics_from_upload
    contents = _make_upload_contents(NUMERIC_CSV)

    result = _run_analytics_from_upload(contents, 'patients.csv', 'visit_date')

    assert 'error' not in result
    json.dumps(result)


def test_run_analytics_from_upload_without_time_column_does_not_crash():
    """time_column=None (or blank) must be tolerated — comprehensive_analysis
    auto-detects a datetime column or returns an empty trends list, it never
    raises for time_column=None."""
    from medical_data_validator.dashboard.pages.analytics import _run_analytics_from_upload
    contents = _make_upload_contents(NUMERIC_CSV)

    result = _run_analytics_from_upload(contents, 'patients.csv', None)

    assert 'error' not in result
    assert isinstance(result['trends'], list)
    json.dumps(result)


def test_run_analytics_from_upload_no_file_returns_error():
    from medical_data_validator.dashboard.pages.analytics import _run_analytics_from_upload
    result = _run_analytics_from_upload(None, None, '')
    assert 'error' in result


def test_run_analytics_from_upload_unparseable_file_returns_error():
    from medical_data_validator.dashboard.pages.analytics import _run_analytics_from_upload
    contents = _make_upload_contents(b"not,a,real,csv\nbut-still-parsed-as-one", mime='text/plain')
    result = _run_analytics_from_upload(contents, 'notes.txt', '')
    assert 'error' in result


def test_metrics_table_data_shape():
    from medical_data_validator.dashboard.pages.analytics import _metrics_table_data
    quality_metrics = {
        'completeness': {'value': 0.95, 'unit': 'percentage', 'description': 'desc', 'severity': 'excellent'},
    }
    rows = _metrics_table_data(quality_metrics)
    assert rows == [
        {'name': 'completeness', 'value': 0.95, 'severity': 'excellent', 'description': 'desc'}
    ]


def test_render_trends_empty_returns_no_trends_text():
    from medical_data_validator.dashboard.pages.analytics import _render_trends
    assert _render_trends([]) == "No trends"
    assert _render_trends(None) == "No trends"


def test_render_trends_nonempty_returns_data_table():
    from dash import dash_table
    from medical_data_validator.dashboard.pages.analytics import _render_trends
    trends = [{'metric': 'age', 'trend': 'increasing', 'confidence': 0.8,
               'period': '2023-01-01 to 2023-05-01', 'description': 'age shows increasing trend'}]
    component = _render_trends(trends)
    assert isinstance(component, dash_table.DataTable)
    assert component.data == trends


def test_update_analytics_callback_end_to_end():
    from medical_data_validator.dashboard.pages.analytics import _update_analytics
    contents = _make_upload_contents(NUMERIC_CSV)

    quality_score, metrics_data, anomalies_data, trends_children, summary_text = _update_analytics(
        1, contents, 'patients.csv', ''
    )

    assert 'Overall quality score' in quality_score
    assert isinstance(metrics_data, list) and len(metrics_data) > 0
    assert isinstance(anomalies_data, list)
    # summary_text must be valid JSON text (json.dumps output).
    json.loads(summary_text)


def test_update_analytics_callback_no_upload_shows_error_message():
    from medical_data_validator.dashboard.pages.analytics import _update_analytics

    quality_score, metrics_data, anomalies_data, trends_children, summary_text = _update_analytics(
        1, None, None, ''
    )

    assert metrics_data == []
    assert anomalies_data == []
    assert trends_children == ""
    assert summary_text == ""
