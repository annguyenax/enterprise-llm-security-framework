"""Session-wide pytest configuration.

Final Phase 12B re-audit fix (Section 5, route-test database isolation):
redirects `RETRIEVAL_DB_PATH` to a temporary file before any test module
in this directory is collected/imported. pytest imports `conftest.py`
before it imports any test module in the same directory, so this
top-level code runs before the first `from app.main import app` anywhere
in the session -- which is what makes it reliable regardless of *which*
test file happens to import `app.main` first. Setting the environment
variable inside an individual test file's own fixture is too late if a
different test file (collected earlier, e.g. alphabetically) already
imported `app.main` first: `app.core.config.settings` is a module-level
singleton built once at first import and cached in `sys.modules`
thereafter, and `app.api.routes` eagerly calls `_retriever.initialize()`
against `settings.retrieval_db_path` at that same import time.

This does not change any production initialization behavior -- only the
path the test session's `settings` singleton resolves for
`retrieval_db_path`, via the same `RETRIEVAL_DB_PATH` environment
variable `app/core/config.py` already reads in production.
"""
import os
import tempfile

if "RETRIEVAL_DB_PATH" not in os.environ:
    _session_tmp_dir = tempfile.mkdtemp(prefix="retrieval-test-session-")
    os.environ["RETRIEVAL_DB_PATH"] = os.path.join(_session_tmp_dir, "retrieval.db")
