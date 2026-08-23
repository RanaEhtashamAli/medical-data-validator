"""Session-wide test fixtures shared across the whole suite."""

import os
import tempfile

import pytest


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
