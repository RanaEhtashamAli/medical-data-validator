"""Regression test for the Fix 2 bug: `medical_data_validator.security` used
to do `from flask import request, jsonify` at module scope. Since `security`
is imported by `core.py` inside the shared v1.2 try/except ImportError block
(alongside ComplianceEngine, AdvancedAnalytics, and monitor), a base install
without Flask would raise ImportError on that whole block -- silently
disabling compliance, analytics, and monitoring, not just security features.

This test simulates "Flask is not installed" via builtins.__import__ patching
and confirms the v1.2 engines still import successfully.
"""

import builtins
import importlib
import sys

import pytest


def _clear_package_modules():
    """Remove medical_data_validator.* from sys.modules and return what was
    removed, so the caller can restore it afterwards."""
    to_clear = [
        name for name in sys.modules
        if name == "medical_data_validator" or name.startswith("medical_data_validator.")
    ]
    return {name: sys.modules.pop(name) for name in to_clear}


def test_core_v12_imports_survive_flask_being_unavailable(monkeypatch):
    real_import = builtins.__import__

    def fake_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "flask" or name.startswith("flask."):
            raise ImportError(f"No module named '{name}' (simulated for test)")
        return real_import(name, globals, locals, fromlist, level)

    saved_modules = _clear_package_modules()
    try:
        monkeypatch.setattr(builtins, "__import__", fake_import)
        core = importlib.import_module("medical_data_validator.core")

        # The whole shared v1.2 block must still succeed even though Flask
        # is unavailable -- security.py must not drag it down.
        assert core.ComplianceEngine is not None
        assert core.AdvancedAnalytics is not None
        assert core.monitor is not None
    finally:
        monkeypatch.undo()
        _clear_package_modules()
        sys.modules.update(saved_modules)
        # Re-import cleanly so later tests in the same process see the
        # normal, Flask-enabled modules.
        importlib.import_module("medical_data_validator.core")
