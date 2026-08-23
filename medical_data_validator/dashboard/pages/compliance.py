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

import json

import dash
import dash_bootstrap_components as dbc
from dash import dcc, html, dash_table, Input, Output, State, callback

from medical_data_validator.dashboard.routes import (
    _builtin_compliance_template_names,
    _delete_custom_template,
    _list_custom_templates,
    _upsert_custom_template,
    build_v1_2_compliance_report,
    normalize_custom_template_rules,
    plugin_info_rows,
)
from medical_data_validator.dashboard.utils import (
    _is_error,
    decode_upload_to_dataframe,
    register_page_once,
)

register_page_once(__name__, path='/compliance', name='Compliance')

# Keys in build_v1_2_compliance_report()'s response that are bookkeeping
# rather than a per-standard report -- everything else (hipaa/gdpr/fda/
# medical_coding, plus any plugin standard key such as fhir_r4/snomed_ct) is
# rendered as its own block.
_REPORT_BOOKKEEPING_KEYS = {
    'overall_score', 'risk_level', 'all_violations', 'template_applied', 'plugins_applied',
}

layout = dbc.Container([
    dbc.Row([
        dbc.Col([
            html.H1("Compliance", className="text-center mb-4"),
            html.P(
                "Run v1.2 compliance reports, manage custom compliance templates, "
                "and view discovered compliance plugins",
                className="text-center"
            )
        ])
    ]),

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
        dbc.Col(dbc.Input(id='compliance-tmpl-name-input', placeholder='Template name'), width=3),
        dbc.Col(dbc.Input(id='compliance-tmpl-description-input', placeholder='Description (optional)'), width=3),
        dbc.Col(dbc.Textarea(
            id='compliance-tmpl-rules-input',
            placeholder='[{"name":"...","pattern":"...","severity":"medium"}]',
        ), width=4),
        dbc.Col(dbc.Button('Save template', id='compliance-tmpl-save-btn', color='primary'), width=2),
    ], className='mb-3'),
    dbc.Row([
        dbc.Col(dbc.Input(id='compliance-tmpl-delete-name-input', placeholder='Template name to delete'), width=4),
        dbc.Col(dbc.Button('Delete', id='compliance-tmpl-delete-btn', color='danger'), width=2),
    ], className='mb-3'),
    html.Div(id='compliance-tmpl-message'),
    dash_table.DataTable(id='compliance-tmpl-table', columns=[
        {'name': 'Name', 'id': 'name'},
        {'name': 'Description', 'id': 'description'},
        {'name': 'Rule count', 'id': 'rule_count'},
    ]),
    dbc.Button('Refresh', id='compliance-tmpl-refresh-btn', className='mt-3'),

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

def _template_dropdown_options():
    """Built-in template names plus every saved custom template name,
    refreshed on every call (not cached at import time)."""
    options = [{'label': name, 'value': name} for name in sorted(_builtin_compliance_template_names())]
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
        df = decode_upload_to_dataframe(contents, filename)
    except Exception as exc:
        return {'error': f"Could not parse {filename}: {exc}"}

    try:
        return build_v1_2_compliance_report(df, template or None, bool(use_plugins))
    except Exception as exc:
        return {'error': str(exc)}


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
    """Parse the Textarea's JSON rule array and upsert the template. Uses
    normalize_custom_template_rules() (shared with api_add_custom_template())
    for validation and default severity/description/field_pattern/
    recommendation normalization, so a rule saved with just name+pattern is
    still usable by CustomComplianceRule(**r) later."""
    name = (name or '').strip()
    if not name:
        return False, "Template name is required"

    try:
        rules = json.loads(rules_json) if rules_json else []
    except (TypeError, ValueError) as exc:
        return False, f"Invalid JSON payload: {exc}"

    ok, error, normalized_rules = normalize_custom_template_rules(rules)
    if not ok:
        return False, error

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
    """Delegates to routes.plugin_info_rows() -- the same field extraction
    (name/class_name/module/first-line-of-docstring-as-description) used by
    api_compliance_plugins(), called directly rather than via the HTTP route
    (no-HTTP-to-self)."""
    return plugin_info_rows()


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
    [Output('compliance-tmpl-table', 'data'), Output('compliance-tmpl-message', 'children'),
     Output('compliance-template-dropdown', 'options', allow_duplicate=True)],
    [Input('compliance-tmpl-save-btn', 'n_clicks'), Input('compliance-tmpl-delete-btn', 'n_clicks'), Input('compliance-tmpl-refresh-btn', 'n_clicks')],
    [State('compliance-tmpl-name-input', 'value'), State('compliance-tmpl-description-input', 'value'),
     State('compliance-tmpl-rules-input', 'value'), State('compliance-tmpl-delete-name-input', 'value')],
    prevent_initial_call=True,
)
def _handle_template_actions(save_clicks, delete_clicks, refresh_clicks, name, description, rules_json, delete_name):
    triggered = dash.ctx.triggered_id
    message = ""
    if triggered == 'compliance-tmpl-save-btn':
        _ok, message = _save_custom_template_from_form(name, description, rules_json)
    elif triggered == 'compliance-tmpl-delete-btn':
        _ok, message = _delete_custom_template_from_form(delete_name)
    return _list_templates_table_data(), message, _template_dropdown_options()


@callback(
    Output('compliance-plugins-table', 'data'),
    Input('compliance-plugins-refresh-btn', 'n_clicks'),
    prevent_initial_call=False,
)
def _handle_plugins_refresh(n_clicks):
    return _list_plugins_table_data()
