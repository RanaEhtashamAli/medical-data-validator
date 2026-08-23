"""Dash page: real-time monitoring (stats, alerts, quality trends)."""

import dash
import dash_bootstrap_components as dbc
from dash import html, dash_table, Input, Output, State, callback

from medical_data_validator.dashboard.utils import register_page_once
# NOTE: RealTimeMonitor.alerts (monitoring.py) is an in-memory list with no
# SQLite backing — a pre-existing characteristic, not something this page
# fixes. An alert acknowledged/resolved via this page may not stay that way
# if a later request lands on a different Gunicorn worker process in
# production, since each worker process has its own `monitor` singleton.
from medical_data_validator.monitoring import monitor

register_page_once(__name__, path='/monitoring', name='Monitoring')

layout = dbc.Container([
    html.H2("Monitoring"),

    html.H4("Stats", className='mt-4'),
    dash_table.DataTable(id='monitoring-stats-table', columns=[
        {'name': 'Stat', 'id': 'stat'},
        {'name': 'Value', 'id': 'value'},
    ]),
    dbc.Button('Refresh', id='monitoring-stats-refresh-btn', className='mt-2'),

    html.H4("Alerts", className='mt-4'),
    dbc.Row([
        dbc.Col(dbc.Input(id='monitoring-alert-id-input', placeholder='Alert ID (see table)'), width=4),
        dbc.Col(dbc.Button('Acknowledge', id='monitoring-ack-btn'), width=2),
        dbc.Col(dbc.Button('Resolve', id='monitoring-resolve-btn'), width=2),
        dbc.Col(dbc.Button('Refresh', id='monitoring-alerts-refresh-btn'), width=2),
    ], className='mb-2'),
    html.Div(id='monitoring-alerts-message'),
    dash_table.DataTable(id='monitoring-alerts-table', columns=[
        {'name': 'ID', 'id': 'id'},
        {'name': 'Timestamp', 'id': 'timestamp'},
        {'name': 'Type', 'id': 'alert_type'},
        {'name': 'Severity', 'id': 'severity'},
        {'name': 'Message', 'id': 'message'},
        {'name': 'Acknowledged', 'id': 'acknowledged'},
    ]),

    html.H4("Quality Trends", className='mt-4'),
    dbc.Row([
        dbc.Col(dbc.Input(id='monitoring-metric-input', placeholder='Metric name'), width=4),
        dbc.Col(dbc.Input(id='monitoring-hours-input', type='number', value=24), width=2),
        dbc.Col(dbc.Button('Get Trends', id='monitoring-trends-btn'), width=2),
    ], className='mb-2'),
    html.Div(id='monitoring-trends-output'),
], fluid=True)


def _stats_table_data():
    stats = monitor.get_monitoring_stats()
    return [{'stat': key, 'value': str(value)} for key, value in stats.items()]


def _alerts_table_data():
    alerts = monitor.get_active_alerts()
    return [
        {
            'id': alert['id'],
            'timestamp': alert['timestamp'],
            'alert_type': alert['alert_type'],
            'severity': alert['severity'],
            'message': alert['message'],
            'acknowledged': alert['acknowledged'],
        }
        for alert in alerts
    ]


def _acknowledge_alert_by_id(alert_id):
    alert_id = (alert_id or '').strip()
    if not alert_id:
        return False, "Alert ID is required"
    if monitor.acknowledge_alert(alert_id):
        return True, f"Acknowledged alert '{alert_id}'"
    return False, f"Alert '{alert_id}' not found"


def _resolve_alert_by_id(alert_id):
    alert_id = (alert_id or '').strip()
    if not alert_id:
        return False, "Alert ID is required"
    if monitor.resolve_alert(alert_id):
        return True, f"Resolved alert '{alert_id}'"
    return False, f"Alert '{alert_id}' not found"


def _quality_trends_rows(metric_name, hours):
    metric_name = (metric_name or '').strip()
    if not metric_name:
        return False, "Metric name is required", []
    try:
        hours = int(hours) if hours is not None else 24
    except (TypeError, ValueError):
        hours = 24
    rows = monitor.get_quality_trends(metric_name, hours=hours)
    if not rows:
        return True, f"No trend data found for metric '{metric_name}'", []
    return True, "", rows


@callback(
    Output('monitoring-stats-table', 'data'),
    Input('monitoring-stats-refresh-btn', 'n_clicks'),
    prevent_initial_call=False,
)
def _handle_stats_refresh(n_clicks):
    return _stats_table_data()


@callback(
    [Output('monitoring-alerts-table', 'data'), Output('monitoring-alerts-message', 'children')],
    [Input('monitoring-ack-btn', 'n_clicks'),
     Input('monitoring-resolve-btn', 'n_clicks'),
     Input('monitoring-alerts-refresh-btn', 'n_clicks')],
    [State('monitoring-alert-id-input', 'value')],
    prevent_initial_call=False,
)
def _handle_alert_actions(ack_clicks, resolve_clicks, refresh_clicks, alert_id):
    triggered = dash.ctx.triggered_id
    message = ""
    if triggered == 'monitoring-ack-btn':
        _ok, message = _acknowledge_alert_by_id(alert_id)
    elif triggered == 'monitoring-resolve-btn':
        _ok, message = _resolve_alert_by_id(alert_id)
    return _alerts_table_data(), message


@callback(
    Output('monitoring-trends-output', 'children'),
    Input('monitoring-trends-btn', 'n_clicks'),
    [State('monitoring-metric-input', 'value'), State('monitoring-hours-input', 'value')],
    prevent_initial_call=True,
)
def _handle_trends_query(n_clicks, metric_name, hours):
    _ok, message, rows = _quality_trends_rows(metric_name, hours)
    if not rows:
        return message
    return dash_table.DataTable(
        columns=[
            {'name': 'Timestamp', 'id': 'timestamp'},
            {'name': 'Value', 'id': 'value'},
            {'name': 'Status', 'id': 'status'},
        ],
        data=rows,
    )
