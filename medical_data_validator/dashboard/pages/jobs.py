"""Dash page: async job submission and status polling."""

import json

import dash
import dash_bootstrap_components as dbc
from dash import dcc, html, dash_table, Input, Output, State, callback

from medical_data_validator.dashboard.utils import register_page_once
from medical_data_validator.jobs import submit_job, list_jobs

register_page_once(__name__, path='/jobs', name='Jobs')

DASH_TENANT = 'default'

layout = dbc.Container([
    html.H2("Validation Jobs"),
    dbc.Row([
        dbc.Col(dcc.Dropdown(id='jobs-type-dropdown',
                              options=[{'label': 'Validate', 'value': 'validate'},
                                       {'label': 'Anonymize', 'value': 'anonymize'}],
                              value='validate'), width=2),
        dbc.Col(dbc.Textarea(id='jobs-payload-input', placeholder='{"data": {"age": [200]}}'), width=7),
        dbc.Col(dbc.Button('Submit job', id='jobs-submit-btn', color='primary'), width=3),
    ], className='mb-3'),
    html.Div(id='jobs-submit-message'),
    dash_table.DataTable(id='jobs-table', columns=[
        {'name': 'ID', 'id': 'id'},
        {'name': 'Type', 'id': 'job_type'},
        {'name': 'Status', 'id': 'status'},
        {'name': 'Created', 'id': 'created_at'},
    ]),
    dbc.Button('Refresh', id='jobs-refresh-btn', className='mt-3'),
], fluid=True)


def _list_jobs_table_data(tenant=DASH_TENANT):
    return [
        {
            'id': j['id'],
            'job_type': j['job_type'],
            'status': j['status'],
            'created_at': j.get('created_at', ''),
        }
        for j in list_jobs(tenant=tenant)
    ]


def _submit_job_from_form(job_type, payload_json):
    if job_type not in ('validate', 'anonymize'):
        return False, "job_type must be 'validate' or 'anonymize'"
    try:
        payload = json.loads(payload_json) if payload_json else {}
    except (TypeError, ValueError) as exc:
        return False, f"Invalid JSON payload: {exc}"
    if not isinstance(payload, dict):
        return False, "payload must be a JSON object"
    submit_job(job_type, payload, tenant=DASH_TENANT, username='dash-ui')
    return True, "Job submitted"


@callback(
    [Output('jobs-table', 'data'), Output('jobs-submit-message', 'children')],
    [Input('jobs-submit-btn', 'n_clicks'), Input('jobs-refresh-btn', 'n_clicks')],
    [State('jobs-type-dropdown', 'value'), State('jobs-payload-input', 'value')],
    prevent_initial_call=False,
)
def _handle_jobs_actions(submit_clicks, refresh_clicks, job_type, payload_json):
    triggered = dash.ctx.triggered_id
    message = ""
    if triggered == 'jobs-submit-btn':
        ok, message = _submit_job_from_form(job_type, payload_json)
    return _list_jobs_table_data(), message
