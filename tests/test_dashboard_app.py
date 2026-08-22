"""Tests for medical_data_validator/dashboard/app.py's production-config and
error-handling branches.

Scope (per the Task 1 brief in
.superpowers/sdd/2026-08-22-test-coverage-improvement-plan/task-1-brief.md):

- create_dashboard_app(): the RuntimeError raised when SECRET_KEY is unset
  AND FLASK_ENV=production.
- The generic @app.errorhandler(Exception) handler: JSON shape for an
  unhandled, non-HTTP exception, including the debug-gated traceback field.
- create_production_app(): the production config flags it sets.
- run_production_server(debug=True): delegates straight to Flask's dev
  server with debug=True.
- run_production_server(debug=False) success path: builds the gunicorn
  StandaloneApplication with the correct options dict (gunicorn's real
  BaseApplication.__init__/do_load_config is swapped out so the test never
  hits the documented, pre-existing "No configuration setting for:
  access_logfile" gunicorn bug -- only the options dict and control flow are
  verified, and only a mocked `.run()` is invoked, never the real one).
- run_production_server(debug=False) except ImportError fallback: falls
  back to Flask's dev server when gunicorn.app.base can't be imported.
- run_dashboard(): delegates to Flask's dev server with the documented
  host/port/debug values.

Explicitly out of scope (see brief): the `if __name__ == "__main__":`
sys.path shim, and actually invoking gunicorn's real `.run()`.
"""

import sys
from unittest.mock import MagicMock, patch

import pytest
from flask import Flask

from medical_data_validator.dashboard.app import (
    create_dashboard_app,
    create_production_app,
    run_dashboard,
    run_production_server,
)


# --------------------------------------------------------------------------
# create_dashboard_app(): SECRET_KEY / FLASK_ENV production guard
# --------------------------------------------------------------------------

class TestSecretKeyProductionGuard:
    def test_raises_runtime_error_when_secret_key_unset_in_production(self, monkeypatch):
        monkeypatch.delenv("SECRET_KEY", raising=False)
        monkeypatch.setenv("FLASK_ENV", "production")

        with pytest.raises(RuntimeError, match="SECRET_KEY"):
            create_dashboard_app()

    def test_generates_a_secret_key_when_unset_outside_production(self, monkeypatch):
        monkeypatch.delenv("SECRET_KEY", raising=False)
        monkeypatch.delenv("FLASK_ENV", raising=False)

        app = create_dashboard_app()

        assert app.config["SECRET_KEY"]
        assert isinstance(app.config["SECRET_KEY"], str)
        assert len(app.config["SECRET_KEY"]) >= 32


# --------------------------------------------------------------------------
# Generic @app.errorhandler(Exception) handler
# --------------------------------------------------------------------------

class TestGenericErrorHandler:
    @staticmethod
    def _client_with_boom_route(app):
        @app.route("/__test_unhandled_error__")
        def _boom():
            raise ValueError("kaboom")

        return app.test_client()

    def test_unhandled_exception_returns_500_json_without_traceback_when_not_debug(self):
        app = create_dashboard_app()
        app.config["DEBUG"] = False
        client = self._client_with_boom_route(app)

        resp = client.get("/__test_unhandled_error__")

        assert resp.status_code == 500
        data = resp.get_json()
        assert data["success"] is False
        assert "kaboom" in data["error"]
        assert data["traceback"] is None

    def test_unhandled_exception_includes_traceback_when_debug(self):
        app = create_dashboard_app()
        app.config["DEBUG"] = True
        client = self._client_with_boom_route(app)

        resp = client.get("/__test_unhandled_error__")

        assert resp.status_code == 500
        data = resp.get_json()
        assert data["success"] is False
        assert "kaboom" in data["error"]
        assert data["traceback"] is not None
        assert "Traceback" in data["traceback"]
        assert "ValueError" in data["traceback"]


# --------------------------------------------------------------------------
# create_production_app()
# --------------------------------------------------------------------------

class TestCreateProductionApp:
    def test_sets_production_config_flags(self, monkeypatch):
        monkeypatch.delenv("FLASK_ENV", raising=False)

        app = create_production_app()

        assert app.config["TESTING"] is False
        assert app.config["DEBUG"] is False
        assert app.config["JSON_SORT_KEYS"] is False
        assert app.config["JSONIFY_PRETTYPRINT_REGULAR"] is False


# --------------------------------------------------------------------------
# run_production_server()
# --------------------------------------------------------------------------

class TestRunProductionServer:
    def test_debug_true_delegates_to_flask_dev_server(self, monkeypatch):
        monkeypatch.delenv("FLASK_ENV", raising=False)

        with patch.object(Flask, "run") as mock_run:
            run_production_server(host="127.0.0.1", port=9001, debug=True)

        mock_run.assert_called_once_with(host="127.0.0.1", port=9001, debug=True)

    def test_debug_false_builds_gunicorn_app_with_correct_options(self, monkeypatch):
        """Exercises the real `import gunicorn.app.base` success path and the
        StandaloneApplication construction/options dict, without ever
        triggering gunicorn's real config validation or Arbiter -- both of
        which are where the documented, pre-existing "No configuration
        setting for: access_logfile" bug actually fires.
        """
        monkeypatch.delenv("FLASK_ENV", raising=False)
        import gunicorn.app.base as gunicorn_base

        mock_run = MagicMock()

        class DummyBaseApplication:
            """Stand-in for gunicorn's real BaseApplication. The real one
            calls do_load_config() -> load_config() -> Config.set(...) from
            __init__, which is exactly what trips the pre-existing
            access_logfile bug. This dummy skips that entirely so only
            StandaloneApplication's own __init__ (which sets .options and
            .application) and its inherited `run` matter for this test."""

            def __init__(self, usage=None, prog=None):
                pass

            def run(self):
                mock_run(self)

        monkeypatch.setattr(gunicorn_base, "BaseApplication", DummyBaseApplication)

        run_production_server(host="10.0.0.5", port=9999, workers=7, debug=False)

        mock_run.assert_called_once()
        instance = mock_run.call_args.args[0]
        assert instance.options["bind"] == "10.0.0.5:9999"
        assert instance.options["workers"] == 7
        assert instance.options["worker_class"] == "sync"
        assert instance.options["access_logfile"] == "-"
        assert instance.options["error_logfile"] == "-"
        assert instance.application is not None

    def test_debug_false_falls_back_to_flask_dev_server_when_gunicorn_unavailable(self, monkeypatch):
        monkeypatch.delenv("FLASK_ENV", raising=False)
        monkeypatch.setitem(sys.modules, "gunicorn.app.base", None)

        with patch.object(Flask, "run") as mock_run:
            run_production_server(host="0.0.0.0", port=8000, debug=False)

        mock_run.assert_called_once_with(host="0.0.0.0", port=8000, debug=False)


# --------------------------------------------------------------------------
# run_dashboard()
# --------------------------------------------------------------------------

class TestRunDashboard:
    def test_delegates_to_flask_dev_server_with_documented_defaults(self, monkeypatch):
        monkeypatch.delenv("FLASK_ENV", raising=False)

        with patch.object(Flask, "run") as mock_run:
            run_dashboard()

        mock_run.assert_called_once_with(host="0.0.0.0", port=5000, debug=True)
