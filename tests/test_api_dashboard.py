"""Integration tests for /api/projects and /api/dashboard/* — the endpoints the
React dashboard (datasense-ui) talks to. These exercise routers/projects.py and
routers/dashboard.py end-to-end via HTTP, on top of the isolated test database."""
import io

import pandas as pd

from conftest import unique


def _xlsx_bytes(df: pd.DataFrame) -> bytes:
    buf = io.BytesIO()
    df.to_excel(buf, index=False)
    return buf.getvalue()


# ── Projects (routers/projects.py) ──────────────────────────────────────────────

def test_list_projects_requires_auth(client):
    resp = client.get("/api/projects")
    assert resp.status_code == 401


def test_create_and_list_project(client, admin_headers):
    name = unique("API Project")
    create = client.post("/api/projects", json={"name": name}, headers=admin_headers)
    assert create.status_code == 200, create.text
    assert create.json()["name"] == name

    listing = client.get("/api/projects", headers=admin_headers)
    assert listing.status_code == 200
    assert any(p["name"] == name for p in listing.json())


def test_create_project_duplicate_name_conflicts(client, admin_headers):
    name = unique("Dup API Project")
    client.post("/api/projects", json={"name": name}, headers=admin_headers)
    second = client.post("/api/projects", json={"name": name}, headers=admin_headers)
    assert second.status_code == 409


def test_create_project_forbidden_for_unprivileged_role(client, registered_user):
    # A freshly registered user gets role "other", which cannot create projects.
    _, headers = registered_user
    resp = client.post("/api/projects", json={"name": unique("Nope")}, headers=headers)
    assert resp.status_code == 403


# ── Dashboard: project creation/update (admin only) ─────────────────────────────

def test_create_project_full_via_dashboard_router(client, admin_headers):
    name = unique("Full Dashboard Project")
    resp = client.post(
        "/api/dashboard/projects/full",
        json={"name": name, "client": "Acme", "sample_target": 100},
        headers=admin_headers,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["client"] == "Acme"
    assert body["sample_target"] == 100


def test_create_project_full_forbidden_for_non_admin(client, registered_user):
    _, headers = registered_user
    resp = client.post(
        "/api/dashboard/projects/full", json={"name": unique("Blocked")}, headers=headers
    )
    assert resp.status_code == 403


def test_update_project_via_dashboard_router(client, admin_headers):
    created = client.post(
        "/api/dashboard/projects/full", json={"name": unique("To Update")}, headers=admin_headers
    ).json()
    resp = client.put(
        f"/api/dashboard/projects/{created['id']}",
        json={"status": "paused", "client": "New Client"},
        headers=admin_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "paused"
    assert resp.json()["client"] == "New Client"


def test_update_unknown_project_returns_404(client, admin_headers):
    resp = client.put("/api/dashboard/projects/999999999", json={"status": "paused"}, headers=admin_headers)
    assert resp.status_code == 404


# ── Project assignees ────────────────────────────────────────────────────────────

def test_assignee_add_list_remove_roundtrip(client, admin_headers, registered_user):
    project = client.post(
        "/api/dashboard/projects/full", json={"name": unique("Assignee Project")}, headers=admin_headers
    ).json()
    member_user, _ = registered_user

    add_resp = client.post(
        f"/api/dashboard/projects/{project['id']}/assignees",
        json={"user_id": member_user["id"]},
        headers=admin_headers,
    )
    assert add_resp.status_code == 200

    list_resp = client.get(f"/api/dashboard/projects/{project['id']}/assignees", headers=admin_headers)
    assert any(a["id"] == member_user["id"] for a in list_resp.json())

    remove_resp = client.delete(
        f"/api/dashboard/projects/{project['id']}/assignees/{member_user['id']}", headers=admin_headers
    )
    assert remove_resp.status_code == 200
    list_resp2 = client.get(f"/api/dashboard/projects/{project['id']}/assignees", headers=admin_headers)
    assert not any(a["id"] == member_user["id"] for a in list_resp2.json())


# ── Summary / activity ───────────────────────────────────────────────────────────

def test_summary_endpoint_returns_list(client, admin_headers):
    resp = client.get("/api/dashboard/summary", headers=admin_headers)
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


def test_activity_endpoint_respects_limit_query_param(client, admin_headers):
    resp = client.get("/api/dashboard/activity", params={"limit": 3}, headers=admin_headers)
    assert resp.status_code == 200
    assert len(resp.json()) <= 3


# ── Users (admin only) ───────────────────────────────────────────────────────────

def test_list_users_forbidden_for_non_admin(client, registered_user):
    _, headers = registered_user
    resp = client.get("/api/dashboard/users", headers=headers)
    assert resp.status_code == 403


def test_admin_can_create_and_list_users(client, admin_headers):
    email = unique("adminmade") + "@example.com"
    create = client.post(
        "/api/dashboard/users",
        json={"email": email, "password": "long-enough-pw", "full_name": "Admin Made", "role": "qc_officer"},
        headers=admin_headers,
    )
    assert create.status_code == 201, create.text

    listing = client.get("/api/dashboard/users", headers=admin_headers)
    assert any(u["email"] == email for u in listing.json())


def test_admin_can_update_user_role_and_active_state(client, admin_headers):
    email = unique("roleflip") + "@example.com"
    client.post(
        "/api/dashboard/users",
        json={"email": email, "password": "long-enough-pw", "full_name": "Role Flip", "role": "qc_officer"},
        headers=admin_headers,
    )
    users = client.get("/api/dashboard/users", headers=admin_headers).json()
    target = next(u for u in users if u["email"] == email)

    role_resp = client.put(
        f"/api/dashboard/users/{target['id']}/role", json={"role": "researcher"}, headers=admin_headers
    )
    assert role_resp.status_code == 200

    active_resp = client.patch(
        f"/api/dashboard/users/{target['id']}/active", json={"is_active": False}, headers=admin_headers
    )
    assert active_resp.status_code == 200


def test_admin_cannot_delete_own_account(client, admin_headers):
    me = client.get("/api/auth/me", headers=admin_headers).json()
    resp = client.delete(f"/api/dashboard/users/{me['id']}", headers=admin_headers)
    assert resp.status_code == 400


# ── Password reset flow ──────────────────────────────────────────────────────────

def test_password_reset_request_and_reset_roundtrip(client):
    email = unique("forgetful") + "@example.com"
    client.post(
        "/api/auth/register",
        json={"email": email, "password": "original-pass", "full_name": "Forgetful User"},
    )

    request_resp = client.post("/api/dashboard/auth/request-password-reset", json={"email": email})
    assert request_resp.status_code == 200
    demo_code = request_resp.json()["demo_code"]
    assert demo_code  # SMTP isn't configured, so the code is echoed back

    reset_resp = client.post(
        "/api/dashboard/auth/reset-password",
        json={"email": email, "code": demo_code, "password": "brand-new-password"},
    )
    assert reset_resp.status_code == 200

    login_resp = client.post("/api/auth/login", json={"email": email, "password": "brand-new-password"})
    assert login_resp.status_code == 200


def test_password_reset_unknown_email_still_returns_ok(client):
    # The endpoint must not leak whether an email is registered.
    resp = client.post(
        "/api/dashboard/auth/request-password-reset", json={"email": unique("noone") + "@example.com"}
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


# ── Supervisors & interviewers ───────────────────────────────────────────────────

def test_supervisor_crud_via_api(client, admin_headers):
    name = unique("API Supervisor")
    create = client.post(
        "/api/dashboard/supervisors",
        json={"name": name, "region": "North"},
        headers=admin_headers,
    )
    assert create.status_code == 200
    sid = create.json()["id"]

    listing = client.get("/api/dashboard/supervisors", headers=admin_headers)
    assert any(s["id"] == sid for s in listing.json())

    update = client.put(
        f"/api/dashboard/supervisors/{sid}", json={"name": name, "region": "South"}, headers=admin_headers
    )
    assert update.status_code == 200

    delete = client.delete(f"/api/dashboard/supervisors/{sid}", headers=admin_headers)
    assert delete.status_code == 200


def test_interviewer_upsert_and_list_via_api(client, admin_headers):
    code = unique("APIINT")
    resp = client.post(
        "/api/dashboard/interviewers",
        json={"interviewer_code": code, "name": "API Interviewer", "region": "East"},
        headers=admin_headers,
    )
    assert resp.status_code == 200

    listing = client.get("/api/dashboard/interviewers", headers=admin_headers)
    assert any(i["interviewer_code"] == code for i in listing.json())


def test_interviewer_block_warn_escalate_actions_via_api(client, admin_headers):
    code = unique("APIBLOCK")
    client.post(
        "/api/dashboard/interviewers", json={"interviewer_code": code}, headers=admin_headers
    )

    block = client.post(
        f"/api/dashboard/interviewers/{code}/block", json={"message": "Fabrication suspected"}, headers=admin_headers
    )
    assert block.status_code == 200

    warn = client.post(
        f"/api/dashboard/interviewers/{code}/warn", json={"message": "Late submissions"}, headers=admin_headers
    )
    assert warn.status_code == 200

    escalate = client.post(
        f"/api/dashboard/interviewers/{code}/escalate", json={"message": "Repeated lateness"}, headers=admin_headers
    )
    assert escalate.status_code == 200

    unblock = client.post(f"/api/dashboard/interviewers/{code}/unblock", headers=admin_headers)
    assert unblock.status_code == 200

    actions = client.get(f"/api/dashboard/interviewers/{code}/actions", headers=admin_headers)
    assert actions.status_code == 200
    action_types = {a["action_type"] for a in actions.json()}
    assert {"block", "warning", "escalation", "unblock"} <= action_types


def test_interviewer_metrics_endpoint(client, admin_headers):
    code = unique("APIMETRICS")
    client.post("/api/dashboard/interviewers", json={"interviewer_code": code}, headers=admin_headers)
    resp = client.get(f"/api/dashboard/interviewers/{code}/metrics", headers=admin_headers)
    assert resp.status_code == 200
    assert resp.json()["info"]["interviewer_code"] == code


def test_interviewer_analytics_endpoint(client, admin_headers):
    resp = client.get("/api/dashboard/interviewers/analytics", headers=admin_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert "interviewers" in body and "by_supervisor" in body


# ── Manual listen-in entry ────────────────────────────────────────────────────────

def test_manual_listen_in_entry_and_project_records(client, admin_headers):
    project = client.post(
        "/api/dashboard/projects/full", json={"name": unique("Listen In Project")}, headers=admin_headers
    ).json()

    resp = client.post(
        f"/api/dashboard/projects/{project['id']}/listen-in/manual",
        json={
            "interviewer_id": "INTMAN",
            "listen_date": "2026-01-10",
            "listen_type": "Full",
            "result": "Pass",
        },
        headers=admin_headers,
    )
    assert resp.status_code == 200

    records = client.get(
        f"/api/dashboard/projects/{project['id']}/listen-in-records", headers=admin_headers
    )
    assert records.status_code == 200
    assert len(records.json()) == 1
    assert records.json()[0]["interviewer_id"] == "INTMAN"


def test_manual_listen_in_unknown_project_returns_404(client, admin_headers):
    resp = client.post(
        "/api/dashboard/projects/999999999/listen-in/manual",
        json={
            "interviewer_id": "INTMAN",
            "listen_date": "2026-01-10",
            "listen_type": "Full",
            "result": "Pass",
        },
        headers=admin_headers,
    )
    assert resp.status_code == 404


# ── File-upload endpoint (multipart) ─────────────────────────────────────────────

def test_timing_upload_via_multipart_excel(client, admin_headers):
    project = client.post(
        "/api/dashboard/projects/full", json={"name": unique("Timing Upload Project")}, headers=admin_headers
    ).json()

    df = pd.DataFrame(
        [
            {
                "Instance ID": unique("inst"),
                "Interviewer ID": "INTFILE",
                "Interview Date": "2026-01-10",
                "Duration Minutes": 28,
            }
        ]
    )
    files = {
        "file": (
            "timing.xlsx",
            _xlsx_bytes(df),
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
    }
    resp = client.post(
        f"/api/dashboard/projects/{project['id']}/timing", files=files, headers=admin_headers
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["row_count"] == 1

    records = client.get(
        f"/api/dashboard/projects/{project['id']}/timing-records", headers=admin_headers
    )
    assert len(records.json()) == 1
    assert records.json()[0]["interviewer_id"] == "INTFILE"


def test_timing_upload_forbidden_for_role_without_upload_permission(client, registered_user):
    project_owner_headers = registered_user[1]
    df = pd.DataFrame([{"Instance ID": "x", "Interviewer ID": "y"}])
    files = {"file": ("timing.xlsx", _xlsx_bytes(df), "application/octet-stream")}
    resp = client.post(
        "/api/dashboard/projects/1/timing", files=files, headers=project_owner_headers
    )
    assert resp.status_code == 403


# ── Quality / backcheck / performance / cancelled record listing (empty case) ────

def test_project_report_endpoints_return_empty_lists_for_new_project(client, admin_headers):
    project = client.post(
        "/api/dashboard/projects/full", json={"name": unique("Empty Project")}, headers=admin_headers
    ).json()
    for suffix in (
        "quality-records", "backcheck-records", "listen-in-records",
        "performance-records", "timing-records", "cancelled-records", "upload-log",
    ):
        resp = client.get(f"/api/dashboard/projects/{project['id']}/{suffix}", headers=admin_headers)
        assert resp.status_code == 200, f"{suffix}: {resp.text}"
        assert resp.json() == []
