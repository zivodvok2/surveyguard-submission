"""Unit tests for the user-management functions in shared_db.py."""
import bcrypt

from conftest import unique


def _hash(pw: str) -> str:
    return bcrypt.hashpw(pw.encode(), bcrypt.gensalt()).decode()


def test_create_user_success(db):
    email = unique("alice") + "@example.com"
    ok, err = db.create_user(email, _hash("s3cret!!"), "Alice Example", "qc_officer")
    assert ok is True
    assert err in (None, "") or "already" not in (err or "")
    user = db.get_user_by_email(email)
    assert user is not None
    assert user["full_name"] == "Alice Example"
    assert user["role"] == "qc_officer"
    assert user["is_active"] == 1


def test_create_user_duplicate_email_fails(db):
    email = unique("dup") + "@example.com"
    ok1, _ = db.create_user(email, _hash("first-pass"), "First", "qc_officer")
    assert ok1 is True
    ok2, err2 = db.create_user(email, _hash("second-pass"), "Second", "qc_officer")
    assert ok2 is False
    assert err2  # some error message explaining the conflict


def test_get_user_by_email_unknown_returns_none(db):
    assert db.get_user_by_email(unique("nobody") + "@example.com") is None


def test_get_user_by_id_roundtrip(db, make_user):
    user = make_user()
    fetched = db.get_user_by_id(user["id"])
    assert fetched is not None
    assert fetched["email"] == user["email"]


def test_get_user_by_id_unknown_returns_none(db):
    assert db.get_user_by_id(987654321) is None


def test_get_all_users_includes_new_user(db, make_user):
    user = make_user()
    all_users = db.get_all_users()
    assert any(u["id"] == user["id"] for u in all_users)


def test_update_user_role(db, make_user):
    user = make_user(role="qc_officer")
    db.update_user_role(user["id"], "operations_manager")
    fetched = db.get_user_by_id(user["id"])
    assert fetched["role"] == "operations_manager"


def test_toggle_user_active_deactivates_and_hides_from_active_lookup(db, make_user):
    user = make_user()
    assert db.get_user_by_email(user["email"]) is not None
    db.toggle_user_active(user["id"], 0)
    # get_user_by_email filters on is_active=1, so a deactivated user disappears from it.
    assert db.get_user_by_email(user["email"]) is None
    # ...but get_user_by_id keeps returning it (used by admin screens).
    fetched = db.get_user_by_id(user["id"])
    assert fetched["is_active"] == 0
    db.toggle_user_active(user["id"], 1)
    assert db.get_user_by_email(user["email"]) is not None


def test_update_user_password_changes_hash(db, make_user):
    user = make_user()
    old_hash = user["password_hash"]
    new_hash = _hash("a-brand-new-password")
    db.update_user_password(user["id"], new_hash)
    fetched = db.get_user_by_id(user["id"])
    assert fetched["password_hash"] == new_hash
    assert fetched["password_hash"] != old_hash


def test_set_and_clear_user_otp(db, make_user):
    user = make_user()
    db.set_user_otp(user["id"], "some-otp-hash", "2099-01-01T00:00:00")
    fetched = db.get_user_by_id(user["id"])
    assert fetched["otp_code"] == "some-otp-hash"
    assert fetched["otp_expires_at"] == "2099-01-01T00:00:00"
    db.clear_user_otp(user["id"])
    fetched = db.get_user_by_id(user["id"])
    assert fetched["otp_code"] is None
    assert fetched["otp_expires_at"] is None


def test_set_totp_secret_and_2fa_toggle(db, make_user):
    user = make_user()
    db.set_totp_secret(user["id"], "ABCDEFGHIJKLMNOP")
    fetched = db.get_user_by_id(user["id"])
    assert fetched["totp_secret"] == "ABCDEFGHIJKLMNOP"

    db.set_2fa_enabled(user["id"], True)
    assert db.get_user_by_id(user["id"])["totp_enabled"] == 1

    db.set_2fa_enabled(user["id"], False)
    assert db.get_user_by_id(user["id"])["totp_enabled"] == 0


def test_clear_totp_secret(db, make_user):
    user = make_user()
    db.set_totp_secret(user["id"], "SOMESECRET1234")
    db.set_2fa_enabled(user["id"], True)
    db.clear_totp_secret(user["id"])
    fetched = db.get_user_by_id(user["id"])
    assert fetched["totp_secret"] is None
    assert fetched["totp_enabled"] == 0


def test_delete_user_removes_them(db, make_user):
    user = make_user()
    db.delete_user(user["id"])
    assert db.get_user_by_id(user["id"]) is None


def test_password_reset_token_lifecycle(db, make_user):
    user = make_user()
    token_id = db.create_password_reset_token(user["id"], "hashed-code", "2099-01-01T00:00:00")
    assert isinstance(token_id, int)

    fetched = db.get_password_reset_token("hashed-code")
    assert fetched is not None
    assert fetched["user_id"] == user["id"]
    assert fetched["used"] == 0

    latest = db.get_latest_password_reset_token_by_user(user["id"])
    assert latest is not None
    assert latest["id"] == token_id

    db.consume_password_reset_token(token_id)
    consumed = db.get_password_reset_token("hashed-code")
    assert consumed["used"] == 1


def test_password_reset_token_unknown_hash_returns_none(db):
    assert db.get_password_reset_token("no-such-hash-exists") is None
