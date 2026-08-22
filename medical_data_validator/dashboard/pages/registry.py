"""Dash page: dataset registry (list, create, view, update, delete)."""

import dash
import dash_bootstrap_components as dbc
from dash import html, dash_table, Input, Output, State, callback

from medical_data_validator.dashboard.utils import register_page_once
from medical_data_validator.registry import (
    list_datasets, register_dataset, get_dataset, update_dataset, delete_dataset,
)

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
    dbc.Row([
        dbc.Col(dbc.Input(id='registry-lookup-id-input', placeholder='Dataset ID (see ID column below)'), width=5),
        dbc.Col(dbc.Button('View', id='registry-view-btn'), width=1),
        dbc.Col(dbc.Button('Update', id='registry-update-btn'), width=2),
        dbc.Col(dbc.Button('Delete', id='registry-delete-btn', color='danger'), width=2),
    ], className='mb-3'),
    html.Div(id='registry-lookup-message'),
    html.Pre(id='registry-details', className='bg-light p-2'),
    dash_table.DataTable(id='registry-table', columns=[
        {'name': 'ID', 'id': 'id'},
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
            'id': d['id'],
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


def _get_dataset_details(dataset_id):
    dataset_id = (dataset_id or '').strip()
    if not dataset_id:
        return False, "Dataset ID is required", ""
    dataset = get_dataset(dataset_id)
    if dataset is not None and dataset.get('tenant') != DASH_TENANT:
        dataset = None
    if dataset is None:
        return False, f"Dataset '{dataset_id}' not found", ""
    lines = [f"{key}: {value}" for key, value in dataset.items()]
    return True, "", "\n".join(lines)


def _update_dataset_from_form(dataset_id, description, tags_csv):
    dataset_id = (dataset_id or '').strip()
    if not dataset_id:
        return False, "Dataset ID is required"
    existing = get_dataset(dataset_id)
    if existing is None or existing.get('tenant') != DASH_TENANT:
        return False, f"Dataset '{dataset_id}' not found"
    tags = [t.strip() for t in (tags_csv or '').split(',') if t.strip()] if tags_csv else None
    updated = update_dataset(dataset_id, description=description or None, tags=tags)
    if updated is None:
        return False, f"Dataset '{dataset_id}' not found"
    return True, f"Updated '{updated['name']}'"


def _delete_dataset_by_id(dataset_id):
    dataset_id = (dataset_id or '').strip()
    if not dataset_id:
        return False, "Dataset ID is required"
    existing = get_dataset(dataset_id)
    if existing is None or existing.get('tenant') != DASH_TENANT:
        return False, f"Dataset '{dataset_id}' not found"
    if delete_dataset(dataset_id):
        return True, f"Deleted dataset '{dataset_id}'"
    return False, f"Dataset '{dataset_id}' not found"


@callback(
    [Output('registry-table', 'data'), Output('registry-create-message', 'children'),
     Output('registry-lookup-message', 'children'), Output('registry-details', 'children')],
    [Input('registry-create-btn', 'n_clicks'), Input('registry-refresh-btn', 'n_clicks'),
     Input('registry-view-btn', 'n_clicks'), Input('registry-update-btn', 'n_clicks'),
     Input('registry-delete-btn', 'n_clicks')],
    [State('registry-name-input', 'value'),
     State('registry-description-input', 'value'),
     State('registry-tags-input', 'value'),
     State('registry-lookup-id-input', 'value')],
    prevent_initial_call=False,
)
def _handle_registry_actions(create_clicks, refresh_clicks, view_clicks, update_clicks, delete_clicks,
                              name, description, tags_csv, lookup_id):
    triggered = dash.ctx.triggered_id
    create_message = ""
    lookup_message = ""
    details = ""
    if triggered == 'registry-create-btn':
        _ok, create_message = _create_dataset_from_form(name, description, tags_csv)
    elif triggered == 'registry-view-btn':
        _ok, lookup_message, details = _get_dataset_details(lookup_id)
    elif triggered == 'registry-update-btn':
        _ok, lookup_message = _update_dataset_from_form(lookup_id, description, tags_csv)
    elif triggered == 'registry-delete-btn':
        _ok, lookup_message = _delete_dataset_by_id(lookup_id)
    return _list_datasets_table_data(), create_message, lookup_message, details
