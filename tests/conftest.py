"""Session-wide test fixtures shared across the whole suite."""

import base64
import os
import tempfile

import pytest
from dash._callback_context import context_value
from dash._utils import AttributeDict


@pytest.fixture(scope="session", autouse=True)
def _isolated_auth_db():
    """Give the whole test session its own fresh SQLite-backed auth store.

    Without this, auth.py would fall back to its real default path
    (~/.medical_validator/auth.db) during tests -- writing into a
    developer's actual data directory, and risking a stale admin
    password hash from a previous local run/session silently surviving
    into the current one (auth.py only seeds the admin account when the
    users table is empty).

    Session-scoped rather than per-file (contrast audit.py/registry.py/
    jobs.py's per-file temp-DB fixtures): several test files intentionally
    treat auth's user/tenant store as one shared, process-wide fixture for
    the whole run -- see the "auth._USERS is a process-wide in-memory
    store shared by every test file" comments in test_registry_routes.py
    and test_job_routes.py. A per-file DB swap would break that assumption
    (e.g. a module-scoped `admin` token fixture would go stale in the very
    next file). One DB for the whole session preserves the same semantics
    the old in-memory dict had, just backed by SQLite instead.
    """
    import medical_data_validator.auth as auth

    tf = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tf.close()

    auth.AUTH_DB_PATH = tf.name
    if auth._conn is not None:
        auth._conn.close()
        auth._conn = None

    yield

    if auth._conn is not None:
        auth._conn.close()
        auth._conn = None
    try:
        os.unlink(tf.name)
    except FileNotFoundError:
        pass


@pytest.fixture(scope="session", autouse=True)
def _isolated_custom_rules_db():
    """Same rationale as _isolated_auth_db, for the custom-rules SQLite
    store now backing medical_data_validator.dashboard.routes._custom_rules_storage."""
    from medical_data_validator.dashboard import routes as routes_module

    tf = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tf.close()

    routes_module.CUSTOM_RULES_DB_PATH = tf.name
    if routes_module._custom_rules_conn is not None:
        routes_module._custom_rules_conn.close()
        routes_module._custom_rules_conn = None

    yield

    if routes_module._custom_rules_conn is not None:
        routes_module._custom_rules_conn.close()
        routes_module._custom_rules_conn = None
    try:
        os.unlink(tf.name)
    except FileNotFoundError:
        pass


def _make_upload_contents(raw_bytes: bytes, mime: str = 'text/csv') -> str:
    """Build a dcc.Upload-style 'contents' string: 'data:<mime>;base64,<b64>'.

    Shared by the Dash page test files whose pages take a raw-bytes upload
    (test_dash_security_page.py, test_dash_anonymize_page.py,
    test_dash_analytics_page.py, test_dash_compliance_page.py), which used
    to define this identically. test_dash_layout.py's DataFrame-based helper
    of the same name is a distinct, differently-shaped local helper and is
    out of scope here.
    """
    encoded = base64.b64encode(raw_bytes).decode()
    return f"data:{mime};base64,{encoded}"


def _set_triggered(component_id):
    """Make dash.ctx.triggered_id resolve to component_id inside a
    directly-called callback. Shared by every Dash page test file that
    exercises a multi-button ctx.triggered_id dispatcher, which used to
    define this identically."""
    context_value.set(AttributeDict(triggered_inputs=[{'prop_id': f'{component_id}.n_clicks'}]))


@pytest.fixture
def _clean_custom_templates():
    """Save/restore the custom_templates table so tests don't leak state
    into each other or into other test files sharing the same session-wide
    SQLite-backed store (see _isolated_custom_rules_db above). Shared by
    test_compliance_plugins_templates.py and test_dash_compliance_page.py,
    which used to define this identically."""
    from medical_data_validator.dashboard import routes as routes_module

    before_names = {t['name'] for t in routes_module._list_custom_templates()}
    yield
    for t in routes_module._list_custom_templates():
        if t['name'] not in before_names:
            routes_module._delete_custom_template(t['name'])
