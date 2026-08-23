"""Dash page: v1.2 compliance report runner, custom compliance template CRUD,
and read-only compliance plugin listing.

Combines three independent concerns the user already groups under one
"Compliance" heading (per the Task 6 plan) rather than splitting the
plugin-listing table off into its own page with nothing else on it.

Follows dashboard/pages/security.py's upload-decode pattern for the report
runner, dashboard/pages/custom_rules.py's layout for the CRUD table, and
dashboard/pages/jobs.py's JSON-Textarea + try/except pattern for the
structurally-nested 'rules' field.
"""

import base64
import json

import dash
import dash_bootstrap_components as dbc
from dash import dcc, html, dash_table, Input, Output, State, callback

from medical_data_validator.dashboard.routes import (
    _BUILTIN_COMPLIANCE_TEMPLATE_NAMES,
    _delete_custom_template,
    _list_custom_templates,
    _upsert_custom_template,
    build_v1_2_compliance_report,
)
from medical_data_validator.dashboard.utils import (
    dataframe_from_upload_bytes,
    register_page_once,
)
from medical_data_validator.plugins import discover_plugins

register_page_once(__name__, path='/compliance', name='Compliance')

# Keys in build_v1_2_compliance_report()'s response that are bookkeeping
# rather than a per-standard report -- everything else (hipaa/gdpr/fda/
# medical_coding, plus any plugin standard key such as fhir_r4/snomed_ct) is
# rendered as its own block.
_REPORT_BOOKKEEPING_KEYS = {
    'overall_score', 'risk_level', 'all_violations', 'template_applied', 'plugins_applied',
}

layout = dbc.Container([
    html.H1("Compliance", className="mb-4"),

    # --- 1. v1.2 compliance report runner ---------------------------------
    html.H3("Run Compliance Report"),
    dbc.Row([
        dbc.Col([
            dcc.Upload(
                id='compliance-upload',
                children=html.Div([
                    'Drag and Drop or ',
                    html.A('Select Files')
                ]),
                style={
                    'width': '100%',
                    'height': '60px',
                    'lineHeight': '60px',
                    'borderWidth': '1px',
                    'borderStyle': 'dashed',
                    'borderRadius': '5px',
                    'textAlign': 'center',
                    'margin': '10px'
                },
                multiple=False
            ),
        ])
    ]),
    dbc.Row([
        dbc.Col(dcc.Dropdown(
            id='compliance-template-dropdown',
            placeholder='Select compliance template (optional)',
            clearable=True,
        ), width=6),
        dbc.Col(dbc.Checkbox(
            id='compliance-use-plugins-checkbox',
            label='Use plugin-loaded standards (FHIR R4, SNOMED CT)',
            value=False,
        ), width=4),
        dbc.Col(dbc.Button('Run Report', id='compliance-run-btn', color='primary'), width=2),
    ], className='mb-3'),
    html.Div(id='compliance-report-results'),

    html.Hr(),

    # --- 2. Custom compliance templates CRUD ------------------------------
    html.H3("Custom Compliance Templates"),
    dbc.Row([
        dbc.Col(dbc.Input(id='tmpl-name-input', placeholder='Template name'), width=3),
        dbc.Col(dbc.Input(id='tmpl-description-input', placeholder='Description (optional)'), width=3),
        dbc.Col(dbc.Textarea(
            id='tmpl-rules-input',
            placeholder='[{"name":"...","pattern":"...","severity":"medium"}]',
        ), width=4),
        dbc.Col(dbc.Button('Save template', id='tmpl-save-btn', color='primary'), width=2),
    ], className='mb-3'),
    dbc.Row([
        dbc.Col(dbc.Input(id='tmpl-delete-name-input', placeholder='Template name to delete'), width=4),
        dbc.Col(dbc.Button('Delete', id='tmpl-delete-btn', color='danger'), width=2),
    ], className='mb-3'),
    html.Div(id='tmpl-message'),
    dash_table.DataTable(id='tmpl-table', columns=[
        {'name': 'Name', 'id': 'name'},
        {'name': 'Description', 'id': 'description'},
        {'name': 'Rule count', 'id': 'rule_count'},
    ]),
    dbc.Button('Refresh', id='tmpl-refresh-btn', className='mt-3'),

    html.Hr(),

    # --- 3. Plugin listing (read-only) ------------------------------------
    html.H3("Discovered Compliance Plugins"),
    dash_table.DataTable(id='compliance-plugins-table', columns=[
        {'name': 'Name', 'id': 'name'},
        {'name': 'Class', 'id': 'class_name'},
        {'name': 'Module', 'id': 'module'},
        {'name': 'Description', 'id': 'description'},
    ]),
    dbc.Button('Refresh', id='compliance-plugins-refresh-btn', className='mt-3'),
], fluid=True)


# --- 1. Report runner helpers ----------------------------------------------

def _decode_upload(contents, filename):
    """Decode a dcc.Upload contents string into a DataFrame. Raises on
    missing upload or an unparseable/unsupported file -- callers turn this
    into an inline error message rather than letting the callback crash."""
    if contents is None:
        raise ValueError("Upload a file first")
    _header, b64data = contents.split(',', 1)
    raw_bytes = base64.b64decode(b64data)
    return dataframe_from_upload_bytes(filename or '', raw_bytes)


def _template_dropdown_options():
    """Built-in template names plus every saved custom template name,
    refreshed on every call (not cached at import time)."""
    options = [{'label': name, 'value': name} for name in sorted(_BUILTIN_COMPLIANCE_TEMPLATE_NAMES)]
    options.extend({'label': t['name'], 'value': t['name']} for t in _list_custom_templates())
    return options


def _run_compliance_report_from_upload(contents, filename, template, use_plugins):
    """Decode the upload and run build_v1_2_compliance_report(). Returns the
    flattened report dict, or {'error': message} if the upload couldn't be
    parsed, the template name is unrecognized (ValueError), or the
    validator/validation itself failed (RuntimeError) -- build_v1_2_compliance_report
    is documented to raise both, and this must never let either propagate
    raw into the Dash callback."""
    try:
        df = _decode_upload(contents, filename)
    except Exception as exc:
        return {'error': f"Could not parse {filename}: {exc}"}

    try:
        return build_v1_2_compliance_report(df, template or None, bool(use_plugins))
    except Exception as exc:
        return {'error': str(exc)}


def _is_error(result) -> bool:
    return isinstance(result, dict) and 'error' in result


def _render_compliance_report(report):
    if _is_error(report):
        return dbc.Alert(report['error'], color='danger')

    summary = html.P(
        f"Overall score: {report.get('overall_score')} | "
        f"Risk level: {report.get('risk_level')} | "
        f"Template applied: {report.get('template_applied')} | "
        f"Plugins applied: {', '.join(report.get('plugins_applied') or []) or 'none'}"
    )

    standard_blocks = []
    for key, value in report.items():
        if key in _REPORT_BOOKKEEPING_KEYS:
            continue
        standard_blocks.append(html.Div([
            html.H5(key),
            html.Pre(json.dumps(value, indent=2, default=str)),
        ], className='mb-3'))

    return html.Div([summary] + standard_blocks)


# --- 2. Custom template CRUD helpers ----------------------------------------

def _list_templates_table_data():
    return [
        {'name': t['name'], 'description': t.get('description') or '', 'rule_count': len(t['rules'])}
        for t in _list_custom_templates()
    ]


def _save_custom_template_from_form(name, description, rules_json):
    """Parse the Textarea's JSON rule array and upsert the template. Mirrors
    api_add_custom_template()'s normalization (default severity/description/
    field_pattern/recommendation) so a rule saved with just name+pattern is
    still usable by CustomComplianceRule(**r) later."""
    name = (name or '').strip()
    if not name:
        return False, "Template name is required"

    try:
        rules = json.loads(rules_json) if rules_json else []
    except (TypeError, ValueError) as exc:
        return False, f"Invalid JSON payload: {exc}"

    if not isinstance(rules, list) or len(rules) == 0:
        return False, "rules must be a non-empty JSON array"

    for rule in rules:
        if not isinstance(rule, dict) or 'name' not in rule or 'pattern' not in rule:
            return False, "Each rule requires at least 'name' and 'pattern'"

    normalized_rules = [
        {
            'name': rule['name'],
            'pattern': rule['pattern'],
            'severity': rule.get('severity', 'medium'),
            'field_pattern': rule.get('field_pattern'),
            'description': rule.get('description', ''),
            'recommendation': rule.get('recommendation'),
        }
        for rule in rules
    ]

    _upsert_custom_template(name, description or '', normalized_rules)
    return True, f"Saved template '{name}'"


def _delete_custom_template_from_form(name):
    name = (name or '').strip()
    if not name:
        return False, "Template name is required"
    if _delete_custom_template(name):
        return True, f"Deleted template '{name}'"
    return False, f"Template '{name}' not found"


# --- 3. Plugin listing helper -----------------------------------------------

def _list_plugins_table_data():
    """Mirrors api_compliance_plugins()'s field extraction (name/class_name/
    module/first-line-of-docstring-as-description), calling discover_plugins()
    directly rather than the HTTP route (no-HTTP-to-self)."""
    rows = []
    for plugin in discover_plugins():
        doc = (type(plugin).__doc__ or '').strip()
        rows.append({
            'name': plugin.name,
            'class_name': type(plugin).__name__,
            'module': type(plugin).__module__,
            'description': doc.split('\n')[0].strip() if doc else None,
        })
    return rows


# --- Callbacks ---------------------------------------------------------------

@callback(
    [Output('compliance-report-results', 'children'),
     Output('compliance-template-dropdown', 'options')],
    Input('compliance-run-btn', 'n_clicks'),
    [State('compliance-upload', 'contents'), State('compliance-upload', 'filename'),
     State('compliance-template-dropdown', 'value'), State('compliance-use-plugins-checkbox', 'value')],
    prevent_initial_call=False,
)
def _handle_compliance_report_actions(n_clicks, contents, filename, template, use_plugins):
    options = _template_dropdown_options()
    if not n_clicks:
        # Initial page load (or no click yet): just populate the template
        # dropdown, run nothing.
        return html.Div(), options
    report = _run_compliance_report_from_upload(contents, filename, template, use_plugins)
    return _render_compliance_report(report), options


@callback(
    [Output('tmpl-table', 'data'), Output('tmpl-message', 'children'),
     Output('compliance-template-dropdown', 'options', allow_duplicate=True)],
    [Input('tmpl-save-btn', 'n_clicks'), Input('tmpl-delete-btn', 'n_clicks'), Input('tmpl-refresh-btn', 'n_clicks')],
    [State('tmpl-name-input', 'value'), State('tmpl-description-input', 'value'),
     State('tmpl-rules-input', 'value'), State('tmpl-delete-name-input', 'value')],
    prevent_initial_call=True,
)
def _handle_template_actions(save_clicks, delete_clicks, refresh_clicks, name, description, rules_json, delete_name):
    triggered = dash.ctx.triggered_id
    message = ""
    if triggered == 'tmpl-save-btn':
        _ok, message = _save_custom_template_from_form(name, description, rules_json)
    elif triggered == 'tmpl-delete-btn':
        _ok, message = _delete_custom_template_from_form(delete_name)
    return _list_templates_table_data(), message, _template_dropdown_options()


@callback(
    Output('compliance-plugins-table', 'data'),
    Input('compliance-plugins-refresh-btn', 'n_clicks'),
    prevent_initial_call=False,
)
def _handle_plugins_refresh(n_clicks):
    return _list_plugins_table_data()
