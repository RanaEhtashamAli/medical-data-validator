"""Dash page: compliance custom-rules (list, add, remove)."""

import dash
import dash_bootstrap_components as dbc
from dash import dcc, html, dash_table, Input, Output, State, callback

from medical_data_validator.dashboard.routes import _custom_rules_storage
from medical_data_validator.dashboard.utils import register_page_once

register_page_once(__name__, path='/custom-rules', name='Custom Rules')

layout = dbc.Container([
    html.H2("Custom Compliance Rules"),
    dbc.Row([
        dbc.Col(dbc.Input(id='rules-name-input', placeholder='Rule name'), width=3),
        dbc.Col(dbc.Input(id='rules-pattern-input', placeholder='Regex pattern'), width=4),
        dbc.Col(dcc.Dropdown(id='rules-severity-dropdown',
                              options=[{'label': s, 'value': s} for s in ('low', 'medium', 'high', 'critical')],
                              value='medium'), width=2),
        dbc.Col(dbc.Button('Add rule', id='rules-add-btn', color='primary'), width=2),
        dbc.Col(dbc.Button('Remove', id='rules-remove-btn', color='danger'), width=1),
    ], className='mb-3'),
    html.Div(id='rules-add-message'),
    dash_table.DataTable(id='rules-table', columns=[
        {'name': 'Name', 'id': 'name'},
        {'name': 'Pattern', 'id': 'pattern'},
        {'name': 'Severity', 'id': 'severity'},
    ]),
    dbc.Button('Refresh', id='rules-refresh-btn', className='mt-3'),
], fluid=True)


def _list_custom_rules_table_data():
    return [
        {'name': r['name'], 'pattern': r['pattern'], 'severity': r.get('severity', 'medium')}
        for r in _custom_rules_storage
    ]


def _add_custom_rule_from_form(name, pattern, severity):
    name = (name or '').strip()
    pattern = (pattern or '').strip()
    if not name or not pattern:
        return False, "Both name and pattern are required"
    rule_data = {'name': name, 'pattern': pattern, 'severity': severity or 'medium',
                 'field_pattern': None, 'description': '', 'recommendation': None}
    for i, existing in enumerate(_custom_rules_storage):
        if existing['name'] == name:
            _custom_rules_storage[i] = rule_data
            return True, f"Updated rule '{name}'"
    _custom_rules_storage.append(rule_data)
    return True, f"Added rule '{name}'"


def _remove_custom_rule_from_form(name):
    name = (name or '').strip()
    if not name:
        return False, "Rule name is required"
    for i, existing in enumerate(_custom_rules_storage):
        if existing['name'] == name:
            _custom_rules_storage.pop(i)
            return True, f"Removed rule '{name}'"
    return False, f"Rule '{name}' not found"


@callback(
    [Output('rules-table', 'data'), Output('rules-add-message', 'children')],
    [Input('rules-add-btn', 'n_clicks'), Input('rules-remove-btn', 'n_clicks'), Input('rules-refresh-btn', 'n_clicks')],
    [State('rules-name-input', 'value'), State('rules-pattern-input', 'value'),
     State('rules-severity-dropdown', 'value')],
    prevent_initial_call=False,
)
def _handle_rules_actions(add_clicks, remove_clicks, refresh_clicks, name, pattern, severity):
    triggered = dash.ctx.triggered_id
    message = ""
    if triggered == 'rules-add-btn':
        _ok, message = _add_custom_rule_from_form(name, pattern, severity)
    elif triggered == 'rules-remove-btn':
        _ok, message = _remove_custom_rule_from_form(name)
    return _list_custom_rules_table_data(), message
