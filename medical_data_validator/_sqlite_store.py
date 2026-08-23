"""
Shared SQLite connection helper for audit.py, jobs.py, and registry.py.

A configured data directory (e.g. a Docker/Railway persistent volume
mounted at /data) can arrive owned by root even when the image sets
different ownership at build time — the mount happens at container
start and overrides whatever the image baked in. When that happens,
sqlite3.connect() fails with "unable to open database file". Rather
than 500 on every request, fall back to a writable temp directory and
log a warning so the operator can fix the underlying permissions.
"""

import logging
import os
import sqlite3
import tempfile

logger = logging.getLogger(__name__)


def connect(primary_path: str, fallback_name: str) -> sqlite3.Connection:
    """Connect to a SQLite DB at primary_path, falling back to a temp
    directory if primary_path's directory can't be created or written to."""
    try:
        os.makedirs(os.path.dirname(primary_path), exist_ok=True)
        conn = sqlite3.connect(primary_path, check_same_thread=False)
        conn.execute('CREATE TABLE IF NOT EXISTS _write_check (x INTEGER)')
        conn.execute('DROP TABLE _write_check')
        return conn
    except (OSError, sqlite3.OperationalError) as exc:
        fallback_dir = os.path.join(tempfile.gettempdir(), 'medical_validator')
        os.makedirs(fallback_dir, exist_ok=True)
        fallback_path = os.path.join(fallback_dir, fallback_name)
        logger.warning(
            "Could not open database at %s (%s); falling back to %s. "
            "Data stored here will not persist across restarts until the "
            "configured path is made writable.",
            primary_path, exc, fallback_path,
        )
        return sqlite3.connect(fallback_path, check_same_thread=False)
