"""
Shared pytest fixtures for the ipsos-qc-engine test suite.

All tests run against an isolated, throwaway SQLite database (never the
committed qc_dashboard.db). The SQLITE_PATH / DATABASE_URL environment
variables are pinned *before* shared_db (or anything that imports it) is
ever imported, because shared_db reads them at module import time.
"""
import os
import sys
import tempfile
import uuid
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

# Force SQLite mode with a private, per-test-run database file, regardless of
# any DATABASE_URL / SQLITE_PATH set in the environment or a local .env file.
_tmp_db_fd, _tmp_db_path = tempfile.mkstemp(prefix="qc_test_", suffix=".db")
os.close(_tmp_db_fd)
os.environ["DATABASE_URL"] = ""
os.environ["SQLITE_PATH"] = _tmp_db_path
os.environ.setdefault("JWT_SECRET", "test-secret-not-for-production-32-bytes")
# Explicit bootstrap credentials required by shared_db — no guessable default allowed.
os.environ.setdefault("BOOTSTRAP_ADMIN_EMAIL", "admin@example.com")
os.environ.setdefault("BOOTSTRAP_ADMIN_PASSWORD", "test-bootstrap-pw-not-for-production")
# Make sure no real SMTP send is ever attempted from the test suite.
os.environ["SMTP_HOST"] = ""
os.environ["SMTP_USER"] = ""
os.environ["SMTP_PASS"] = ""

import pytest  # noqa: E402

import shared_db  # noqa: E402

shared_db.init_tables()


def unique(prefix: str = "x") -> str:
    """A short, collision-free token for building unique test fixtures
    (emails, interviewer codes, ...) against the shared test database."""
    return f"{prefix}-{uuid.uuid4().hex[:10]}"


@pytest.fixture()
def db():
    """The shared_db module itself, for readability at call sites."""
    return shared_db


@pytest.fixture()
def make_user(db):
    """Create a user with sane defaults, returning the full user dict."""
    created_ids = []

    def _make(role="qc_officer", **overrides):
        import bcrypt

        email = overrides.pop("email", unique("user") + "@example.com")
        password = overrides.pop("password", "correct horse battery staple")
        full_name = overrides.pop("full_name", "Test User")
        pw_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
        ok, err = db.create_user(email, pw_hash, full_name, role)
        assert ok, err
        user = db.get_user_by_email(email)
        user["_plaintext_password"] = password
        created_ids.append(user["id"])
        return user

    return _make


@pytest.fixture()
def make_project(db):
    def _make(**overrides):
        name = overrides.pop("name", unique("Project"))
        created_by = overrides.pop("created_by", None)
        if created_by is None:
            import bcrypt

            email = unique("owner") + "@example.com"
            pw_hash = bcrypt.hashpw(b"whatever-password", bcrypt.gensalt()).decode()
            ok, _ = db.create_user(email, pw_hash, "Project Owner", "admin")
            assert ok
            created_by = db.get_user_by_email(email)["id"]
        project_id = db.create_project(name, created_by)
        return db.get_project(project_id)

    return _make


@pytest.fixture()
def client():
    """A FastAPI TestClient with the app's startup lifespan (init_tables) run."""
    from fastapi.testclient import TestClient

    from api import app

    with TestClient(app) as c:
        yield c


@pytest.fixture()
def admin_token(client, db):
    """Log in as the seeded default admin — that account is in the OTP_BYPASS
    list, so login returns a token directly."""
    resp = client.post(
        "/api/auth/login", json={"email": os.environ["BOOTSTRAP_ADMIN_EMAIL"], "password": os.environ["BOOTSTRAP_ADMIN_PASSWORD"]}
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["token"]


@pytest.fixture()
def admin_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}"}


@pytest.fixture()
def registered_user(client):
    """Register a fresh, non-admin user through the public API and return
    (user_dict, auth_headers)."""
    email = unique("apiuser") + "@example.com"
    resp = client.post(
        "/api/auth/register",
        json={"email": email, "password": "a-fine-password", "full_name": "API User"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    headers = {"Authorization": f"Bearer {body['token']}"}
    return body["user"], headers
