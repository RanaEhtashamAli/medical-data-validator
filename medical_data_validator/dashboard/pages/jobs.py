"""Dash page: async job submission, status polling, detail view, and report downloads."""

import json

import dash
import dash_bootstrap_components as dbc
from dash import dcc, html, dash_table, Input, Output, State, callback

from medical_data_validator.dashboard.utils import register_page_once
from medical_data_validator.jobs import submit_job, list_jobs, get_job

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
    dbc.Row([
        dbc.Col(dbc.Input(id='jobs-lookup-id-input', placeholder='Job ID (see ID column below)'), width=5),
        dbc.Col(dbc.Button('View Result', id='jobs-view-btn'), width=2),
        dbc.Col(dbc.Button("Download PDF", id='jobs-download-pdf-btn'), width=2),
        dbc.Col(dbc.Button("Download CSV", id='jobs-download-csv-btn'), width=2),
    ], className='mb-3'),
    html.Div(id='jobs-detail-message'),
    dcc.Download(id='jobs-download-report'),
    dcc.Store(id='jobs-last-detail-result'),
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


def _get_job_detail(job_id):
    job_id = (job_id or '').strip()
    if not job_id:
        return False, "Job ID is required", None
    job = get_job(job_id)
    if job is not None and job.get('tenant') != DASH_TENANT:
        job = None
    if job is None:
        return False, f"Job '{job_id}' not found", None
    summary = f"status={job['status']} type={job['job_type']}"
    if job.get('error'):
        summary += f" error={job['error']}"
    return True, summary, job


@callback(
    [Output('jobs-table', 'data'), Output('jobs-submit-message', 'children'),
     Output('jobs-detail-message', 'children'), Output('jobs-last-detail-result', 'data')],
    [Input('jobs-submit-btn', 'n_clicks'), Input('jobs-refresh-btn', 'n_clicks'),
     Input('jobs-view-btn', 'n_clicks')],
    [State('jobs-type-dropdown', 'value'), State('jobs-payload-input', 'value'),
     State('jobs-lookup-id-input', 'value')],
    prevent_initial_call=False,
)
def _handle_jobs_actions(submit_clicks, refresh_clicks, view_clicks, job_type, payload_json, lookup_id):
    triggered = dash.ctx.triggered_id
    submit_message = ""
    detail_message = ""
    detail_job = dash.no_update
    if triggered == 'jobs-submit-btn':
        _ok, submit_message = _submit_job_from_form(job_type, payload_json)
    elif triggered == 'jobs-view-btn':
        _ok, detail_message, detail_job = _get_job_detail(lookup_id)
    return _list_jobs_table_data(), submit_message, detail_message, detail_job


@callback(
    Output('jobs-download-report', 'data'),
    [Input('jobs-download-pdf-btn', 'n_clicks'), Input('jobs-download-csv-btn', 'n_clicks')],
    State('jobs-last-detail-result', 'data'),
    prevent_initial_call=True,
)
def _download_job_report(pdf_clicks, csv_clicks, job):
    if not job or job.get('job_type') != 'validate' or job.get('status') != 'completed' or not job.get('result'):
        return dash.no_update
    from medical_data_validator.reports import generate_pdf_report, generate_csv_report
    triggered = dash.ctx.triggered_id
    result_dict = job['result']
    if triggered == 'jobs-download-pdf-btn':
        return dcc.send_bytes(generate_pdf_report(result_dict), f"job_{job['id']}_report.pdf")
    return dcc.send_string(generate_csv_report(result_dict), f"job_{job['id']}_report.csv")
