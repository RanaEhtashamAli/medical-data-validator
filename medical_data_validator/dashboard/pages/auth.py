"""Dash page: user and tenant management (no login gate — see Global Constraints)."""

import dash
import dash_bootstrap_components as dbc
from dash import dcc, html, dash_table, Input, Output, State, callback

from medical_data_validator.dashboard.utils import register_page_once
from medical_data_validator.auth import (
    list_user_accounts, create_user_account, deactivate_user_account, create_tenant_account,
)

register_page_once(__name__, path='/auth', name='Users & Tenants')

layout = dbc.Container([
    html.H2("Users"),
    dbc.Row([
        dbc.Col(dbc.Input(id='auth-username-input', placeholder='Username'), width=2),
        dbc.Col(dbc.Input(id='auth-password-input', placeholder='Password', type='password'), width=2),
        dbc.Col(dcc.Dropdown(id='auth-role-dropdown',
                              options=[{'label': r, 'value': r} for r in ('admin', 'data-steward', 'read-only')],
                              value='read-only'), width=2),
        dbc.Col(dbc.Input(id='auth-tenant-input', placeholder='Tenant', value='default'), width=2),
        dbc.Col(dbc.Button('Create user', id='auth-create-user-btn', color='primary'), width=2),
        dbc.Col(dbc.Button('Deactivate', id='auth-deactivate-btn', color='danger'), width=2),
    ], className='mb-3'),
    html.Div(id='auth-user-message'),
    dash_table.DataTable(id='auth-users-table', columns=[
        {'name': 'Username', 'id': 'username'},
        {'name': 'Role', 'id': 'role'},
        {'name': 'Tenant', 'id': 'tenant'},
        {'name': 'Active', 'id': 'active'},
    ]),
    html.H2("Tenants", className='mt-4'),
    dbc.Row([
        dbc.Col(dbc.Input(id='auth-new-tenant-input', placeholder='New tenant ID'), width=4),
        dbc.Col(dbc.Button('Create tenant', id='auth-create-tenant-btn', color='primary'), width=2),
    ], className='mb-3'),
    html.Div(id='auth-tenant-message'),
    dbc.Button('Refresh', id='auth-refresh-btn', className='mt-3'),
], fluid=True)


def _list_users_table_data():
    return list_user_accounts()


def _create_user_from_form(username, password, role, tenant):
    try:
        create_user_account(username, password, role=role or 'read-only', tenant=tenant or 'default')
        return True, f"Created user '{username}'"
    except ValueError as exc:
        return False, str(exc)


def _deactivate_user_from_form(username):
    try:
        deactivate_user_account(username)
        return True, f"Deactivated '{username}'"
    except ValueError as exc:
        return False, str(exc)


def _create_tenant_from_form(tenant_id):
    try:
        create_tenant_account(tenant_id)
        return True, f"Created tenant '{tenant_id}'"
    except ValueError as exc:
        return False, str(exc)


@callback(
    [Output('auth-users-table', 'data'), Output('auth-user-message', 'children')],
    [Input('auth-create-user-btn', 'n_clicks'), Input('auth-deactivate-btn', 'n_clicks'),
     Input('auth-refresh-btn', 'n_clicks')],
    [State('auth-username-input', 'value'), State('auth-password-input', 'value'),
     State('auth-role-dropdown', 'value'), State('auth-tenant-input', 'value')],
    prevent_initial_call=False,
)
def _handle_user_actions(create_clicks, deactivate_clicks, refresh_clicks, username, password, role, tenant):
    triggered = dash.ctx.triggered_id
    message = ""
    if triggered == 'auth-create-user-btn':
        ok, message = _create_user_from_form(username, password, role, tenant)
    elif triggered == 'auth-deactivate-btn':
        ok, message = _deactivate_user_from_form(username)
    return _list_users_table_data(), message


@callback(
    Output('auth-tenant-message', 'children'),
    Input('auth-create-tenant-btn', 'n_clicks'),
    State('auth-new-tenant-input', 'value'),
    prevent_initial_call=True,
)
def _handle_tenant_actions(create_clicks, tenant_id):
    ok, message = _create_tenant_from_form(tenant_id)
    return message
