"""Tests for the Dash Monitoring page's extracted callback logic."""

import pytest
from medical_data_validator.monitoring import RealTimeMonitor

# dashboard.pages.monitoring calls dash.register_page() at import time, which
# requires dash.Dash(use_pages=True) to have already run at least once in
# this process (it populates Dash's internal page-registry config). Building
# the dashboard app here — before importing the page module directly below —
# lets this test file pass in isolation, not just as part of the full suite.
# (Same pattern as tests/test_dash_layout.py and test_dash_registry_page.py.)
from medical_data_validator.dashboard.app import create_dashboard_app
create_dashboard_app()

import medical_data_validator.dashboard.pages.monitoring as monitoring_page
from tests.conftest import _set_triggered


@pytest.fixture(autouse=True)
def _isolated_monitor(monkeypatch):
    # medical_data_validator.monitoring.monitor is a module-level singleton
    # shared across the whole test session (see tests/test_v1_2_monitoring.py,
    # which avoids it by constructing its own RealTimeMonitor() rather than
    # importing the shared instance). To keep this test file from leaking
    # alerts/stats into other test files that might also touch the shared
    # `monitor`, patch this page module's `monitor` reference to a fresh
    # RealTimeMonitor() instance for the duration of each test.
    fresh_monitor = RealTimeMonitor()
    monkeypatch.setattr(monitoring_page, 'monitor', fresh_monitor)
    yield fresh_monitor


# --- Stats -------------------------------------------------------------

def test_stats_table_data_does_not_crash_on_all_zero_stats():
    rows = monitoring_page._stats_table_data()
    assert isinstance(rows, list)
    assert any(r['stat'] == 'total_validations' and r['value'] == '0' for r in rows)


def test_handle_stats_refresh_returns_rows_on_initial_call():
    rows = monitoring_page._handle_stats_refresh(None)
    assert isinstance(rows, list)
    assert len(rows) > 0


# --- Alerts --------------------------------------------------------------

def test_alerts_table_data_empty_initially():
    assert monitoring_page._alerts_table_data() == []


def test_acknowledge_alert_by_id_requires_id():
    ok, message = monitoring_page._acknowledge_alert_by_id('')
    assert ok is False
    assert 'required' in message.lower()


def test_acknowledge_alert_by_id_not_found():
    ok, message = monitoring_page._acknowledge_alert_by_id('nonexistent-id')
    assert ok is False
    assert 'not found' in message.lower()


def test_resolve_alert_by_id_not_found():
    ok, message = monitoring_page._resolve_alert_by_id('nonexistent-id')
    assert ok is False
    assert 'not found' in message.lower()


def test_handle_alert_actions_ack_does_not_also_resolve_a_different_alert(_isolated_monitor):
    import dash_bootstrap_components as dbc
    monitor = _isolated_monitor
    monitor._create_alert('anomaly_detected', 'high', 'first alert', {})
    monitor._create_alert('anomaly_detected', 'high', 'second alert', {})
    first_id, second_id = monitor.alerts[0].id, monitor.alerts[1].id

    _set_triggered('monitoring-ack-btn')
    rows, message = monitoring_page._handle_alert_actions(1, None, None, first_id)

    # I3: the message is now a dbc.Alert (color-coded), not a bare string.
    assert isinstance(message, dbc.Alert)
    assert message.color == 'success'
    assert 'acknowledged' in message.children.lower()
    assert first_id in message.children
    # Both alerts remain active (unresolved) since ack never resolves.
    assert {r['id'] for r in rows} == {first_id, second_id}
    row_by_id = {r['id']: r for r in rows}
    assert row_by_id[first_id]['acknowledged'] is True
    assert row_by_id[second_id]['acknowledged'] is False
    # The underlying alert objects reflect the same: only the targeted one changed.
    assert next(a for a in monitor.alerts if a.id == first_id).acknowledged is True
    assert next(a for a in monitor.alerts if a.id == second_id).acknowledged is False


def test_handle_alert_actions_resolve_does_not_also_resolve_a_different_alert(_isolated_monitor):
    import dash_bootstrap_components as dbc
    monitor = _isolated_monitor
    monitor._create_alert('anomaly_detected', 'high', 'first alert', {})
    monitor._create_alert('anomaly_detected', 'high', 'second alert', {})
    first_id, second_id = monitor.alerts[0].id, monitor.alerts[1].id

    _set_triggered('monitoring-resolve-btn')
    rows, message = monitoring_page._handle_alert_actions(None, 1, None, first_id)

    assert isinstance(message, dbc.Alert)
    assert message.color == 'success'
    assert 'resolved' in message.children.lower()
    assert first_id in message.children
    # Resolved alerts drop out of get_active_alerts(); only the targeted one is gone.
    remaining_ids = {r['id'] for r in rows}
    assert remaining_ids == {second_id}
    assert next(a for a in monitor.alerts if a.id == first_id).resolved is True
    assert next(a for a in monitor.alerts if a.id == second_id).resolved is False


def test_handle_alert_actions_ack_not_found_renders_danger_alert(_isolated_monitor):
    """I3: an actual error (alert not found) must be visually distinct from
    a success message."""
    import dash_bootstrap_components as dbc

    _set_triggered('monitoring-ack-btn')
    rows, message = monitoring_page._handle_alert_actions(1, None, None, 'nonexistent-id')

    assert isinstance(message, dbc.Alert)
    assert message.color == 'danger'
    assert 'not found' in message.children.lower()


def test_handle_alert_actions_refresh_does_not_change_any_alert(_isolated_monitor):
    monitor = _isolated_monitor
    monitor._create_alert('anomaly_detected', 'high', 'first alert', {})
    alert_id = monitor.alerts[0].id

    _set_triggered('monitoring-alerts-refresh-btn')
    rows, message = monitoring_page._handle_alert_actions(None, None, 1, None)

    assert message == ""
    assert len(rows) == 1
    assert monitor.alerts[0].acknowledged is False
    assert monitor.alerts[0].resolved is False
    assert alert_id == rows[0]['id']


# --- Trends --------------------------------------------------------------

def test_quality_trends_rows_no_data_does_not_crash():
    ok, message, rows = monitoring_page._quality_trends_rows('completeness', 24)
    assert ok is True
    assert rows == []
    assert 'no trend data' in message.lower()


def test_quality_trends_rows_requires_metric_name():
    ok, message, rows = monitoring_page._quality_trends_rows('', 24)
    assert ok is False
    assert rows == []
    assert 'required' in message.lower()


def test_quality_trends_rows_handles_invalid_hours_gracefully():
    ok, message, rows = monitoring_page._quality_trends_rows('completeness', 'not-a-number')
    assert ok is True
    assert rows == []


def test_handle_trends_query_no_data_returns_message_not_exception():
    import dash_bootstrap_components as dbc
    result = monitoring_page._handle_trends_query(1, 'completeness', 24)
    # I3: a neutral "no data" status renders as an info-colored Alert, not a
    # bare string and not danger (it isn't an error).
    assert isinstance(result, dbc.Alert)
    assert result.color == 'info'
    assert 'no trend data' in result.children.lower()


def test_handle_trends_query_validation_error_renders_danger_alert():
    """I3: an actual validation error (missing metric name) must render as
    a danger-colored Alert, distinct from the neutral 'no data' status."""
    import dash_bootstrap_components as dbc
    result = monitoring_page._handle_trends_query(1, '', 24)
    assert isinstance(result, dbc.Alert)
    assert result.color == 'danger'
    assert 'required' in result.children.lower()


def test_handle_trends_query_with_data_returns_table(_isolated_monitor):
    monitor = _isolated_monitor
    monitor._record_quality_metric('completeness', 0.9)
    result = monitoring_page._handle_trends_query(1, 'completeness', 24)
    # A DataTable component, not a bare message string.
    assert not isinstance(result, str)
    assert result.data
    assert result.data[0]['value'] == 0.9
