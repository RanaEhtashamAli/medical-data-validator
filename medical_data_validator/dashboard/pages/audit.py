"""Dash page: audit log viewer."""

import dash_bootstrap_components as dbc
from dash import html, dash_table, Input, Output, callback

from medical_data_validator.dashboard.utils import register_page_once
from medical_data_validator.audit import query_log

register_page_once(__name__, path='/audit', name='Audit Log')

DASH_TENANT = 'default'

layout = dbc.Container([
    html.H2("Audit Log"),
    dash_table.DataTable(id='audit-table', columns=[
        {'name': 'Timestamp', 'id': 'timestamp'},
        {'name': 'Username', 'id': 'username'},
        {'name': 'Event Type', 'id': 'event_type'},
        {'name': 'Dataset ID', 'id': 'dataset_id'},
    ], page_size=25),
    dbc.Button('Refresh', id='audit-refresh-btn', className='mt-3'),
], fluid=True)


def _list_audit_log_table_data(tenant=DASH_TENANT, limit=100):
    records = query_log(tenant=tenant, limit=limit)
    return [
        {
            'timestamp': r.get('timestamp', ''),
            'username': r.get('username', ''),
            'event_type': r.get('event_type', ''),
            'dataset_id': r.get('dataset_id', ''),
        }
        for r in records
    ]


@callback(
    Output('audit-table', 'data'),
    Input('audit-refresh-btn', 'n_clicks'),
    prevent_initial_call=False,
)
def _handle_audit_refresh(n_clicks):
    return _list_audit_log_table_data()
