"""Integration tests for the FastAPI app's public HTTP surface: /health and
/api/auth/*. These exercise routers/auth.py end-to-end through api.py, hitting
real HTTP request/response cycles against the isolated test database."""
import os

import pyotp

from conftest import unique


_ADMIN_EMAIL = os.environ.get("BOOTSTRAP_ADMIN_EMAIL", "admin@example.com")
_ADMIN_PW = os.environ.get("BOOTSTRAP_ADMIN_PASSWORD", "test-bootstrap-pw-not-for-production")


def test_health_endpoint(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_register_returns_token_and_user(client):
    email = unique("newuser") + "@example.com"
    resp = client.post(
        "/api/auth/register",
        json={"email": email, "password": "long-enough-pw", "full_name": "New User"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["token"]
    assert body["user"]["email"] == email
    assert body["user"]["role"] == "other"


def test_register_duplicate_email_conflicts(client):
    email = unique("dupe") + "@example.com"
    payload = {"email": email, "password": "long-enough-pw", "full_name": "Dupe User"}
    first = client.post("/api/auth/register", json=payload)
    assert first.status_code == 200
    second = client.post("/api/auth/register", json=payload)
    assert second.status_code == 409


def test_register_short_password_rejected(client):
    resp = client.post(
        "/api/auth/register",
        json={"email": unique("short") + "@example.com", "password": "short", "full_name": "Short PW"},
    )
    assert resp.status_code == 422


def test_login_admin_bypasses_otp(client):
    resp = client.post(
        "/api/auth/login", json={"email": _ADMIN_EMAIL, "password": _ADMIN_PW}
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert "token" in body
    assert body["user"]["role"] == "admin"


def test_login_wrong_password_returns_401(client):
    resp = client.post(
        "/api/auth/login", json={"email": _ADMIN_EMAIL, "password": "totally-wrong"}
    )
    assert resp.status_code == 401


def test_login_unknown_email_returns_401(client):
    resp = client.post(
        "/api/auth/login",
        json={"email": unique("ghost") + "@example.com", "password": "whatever12"},
    )
    assert resp.status_code == 401


def test_login_regular_user_requires_otp(client):
    email = unique("otpuser") + "@example.com"
    reg = client.post(
        "/api/auth/register",
        json={"email": email, "password": "regular-password", "full_name": "OTP User"},
    )
    assert reg.status_code == 200

    login_resp = client.post("/api/auth/login", json={"email": email, "password": "regular-password"})
    assert login_resp.status_code == 200
    body = login_resp.json()
    assert body["otp_required"] is True
    assert body["demo_otp"]  # SMTP isn't configured in tests, so the code is echoed back


def test_verify_otp_with_correct_demo_code_succeeds(client):
    email = unique("verifyme") + "@example.com"
    client.post(
        "/api/auth/register",
        json={"email": email, "password": "regular-password", "full_name": "Verify Me"},
    )
    challenge = client.post("/api/auth/login", json={"email": email, "password": "regular-password"}).json()

    resp = client.post(
        "/api/auth/verify-otp",
        json={"user_id": challenge["user_id"], "code": challenge["demo_otp"]},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["token"]


def test_verify_otp_with_wrong_code_fails(client):
    email = unique("wrongotp") + "@example.com"
    client.post(
        "/api/auth/register",
        json={"email": email, "password": "regular-password", "full_name": "Wrong OTP"},
    )
    challenge = client.post("/api/auth/login", json={"email": email, "password": "regular-password"}).json()

    resp = client.post(
        "/api/auth/verify-otp",
        json={"user_id": challenge["user_id"], "code": "000000"},
    )
    assert resp.status_code == 401


def test_me_requires_authentication(client):
    resp = client.get("/api/auth/me")
    assert resp.status_code == 401


def test_me_returns_current_user(client, admin_headers):
    resp = client.get("/api/auth/me", headers=admin_headers)
    assert resp.status_code == 200
    assert resp.json()["email"] == "admin@example.com"


def test_enable_and_disable_2fa_toggle(client, registered_user):
    _, headers = registered_user
    enable_resp = client.post("/api/auth/enable-2fa", headers=headers)
    assert enable_resp.status_code == 200
    assert enable_resp.json()["totp_enabled"] is True

    disable_resp = client.post("/api/auth/disable-2fa", headers=headers)
    assert disable_resp.status_code == 200
    assert disable_resp.json()["totp_enabled"] is False


def test_setup_and_confirm_totp_activates_authenticator_2fa(client, registered_user):
    _, headers = registered_user
    setup_resp = client.post("/api/auth/setup-totp", headers=headers)
    assert setup_resp.status_code == 200
    secret = setup_resp.json()["secret"]
    assert setup_resp.json()["qr_base64"]

    code = pyotp.TOTP(secret).now()
    confirm_resp = client.post("/api/auth/confirm-totp", json={"code": code}, headers=headers)
    assert confirm_resp.status_code == 200, confirm_resp.text
    assert confirm_resp.json()["totp_enabled"] is True


def test_confirm_totp_with_wrong_code_rejected(client, registered_user):
    _, headers = registered_user
    client.post("/api/auth/setup-totp", headers=headers)
    resp = client.post("/api/auth/confirm-totp", json={"code": "000000"}, headers=headers)
    assert resp.status_code == 401


def test_disable_totp_clears_secret(client, registered_user):
    _, headers = registered_user
    setup_resp = client.post("/api/auth/setup-totp", headers=headers)
    secret = setup_resp.json()["secret"]
    code = pyotp.TOTP(secret).now()
    client.post("/api/auth/confirm-totp", json={"code": code}, headers=headers)

    resp = client.post("/api/auth/disable-totp", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["totp_enabled"] is False
