"""Dash page: dataset registry (list, create, view run history)."""

import dash
import dash_bootstrap_components as dbc
from dash import dcc, html, dash_table, Input, Output, State, callback

from medical_data_validator.dashboard.utils import register_page_once
from medical_data_validator.registry import list_datasets, register_dataset, get_run_history

register_page_once(__name__, path='/registry', name='Registry')

DASH_TENANT = 'default'

layout = dbc.Container([
    html.H2("Dataset Registry"),
    dbc.Row([
        dbc.Col(dbc.Input(id='registry-name-input', placeholder='Dataset name'), width=3),
        dbc.Col(dbc.Input(id='registry-description-input', placeholder='Description (optional)'), width=4),
        dbc.Col(dbc.Input(id='registry-tags-input', placeholder='Tags, comma-separated (optional)'), width=3),
        dbc.Col(dbc.Button('Register dataset', id='registry-create-btn', color='primary'), width=2),
    ], className='mb-3'),
    html.Div(id='registry-create-message'),
    dash_table.DataTable(id='registry-table', columns=[
        {'name': 'Name', 'id': 'name'},
        {'name': 'Description', 'id': 'description'},
        {'name': 'Tags', 'id': 'tags'},
        {'name': 'Created', 'id': 'created_at'},
    ]),
    dbc.Button('Refresh', id='registry-refresh-btn', className='mt-3'),
], fluid=True)


def _list_datasets_table_data(tenant=DASH_TENANT):
    datasets = list_datasets(tenant=tenant)
    return [
        {
            'name': d['name'],
            'description': d.get('description') or '',
            'tags': ', '.join(d.get('tags') or []),
            'created_at': d.get('created_at', ''),
        }
        for d in datasets
    ]


def _create_dataset_from_form(name, description, tags_csv):
    name = (name or '').strip()
    if not name:
        return False, "Dataset name is required"
    tags = [t.strip() for t in (tags_csv or '').split(',') if t.strip()]
    try:
        register_dataset(name, tenant=DASH_TENANT, description=description or None, tags=tags or None)
        return True, f"Registered '{name}'"
    except ValueError as exc:
        return False, str(exc)


@callback(
    [Output('registry-table', 'data'), Output('registry-create-message', 'children')],
    [Input('registry-create-btn', 'n_clicks'), Input('registry-refresh-btn', 'n_clicks')],
    [State('registry-name-input', 'value'),
     State('registry-description-input', 'value'),
     State('registry-tags-input', 'value')],
    prevent_initial_call=False,
)
def _handle_registry_actions(create_clicks, refresh_clicks, name, description, tags_csv):
    triggered = dash.ctx.triggered_id
    message = ""
    if triggered == 'registry-create-btn':
        ok, message = _create_dataset_from_form(name, description, tags_csv)
    return _list_datasets_table_data(), message
