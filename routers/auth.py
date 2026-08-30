import base64
import io
import os
import secrets
import smtplib
from datetime import datetime, timedelta, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional, Union

import bcrypt
import jwt
import pyotp
import qrcode
from fastapi import APIRouter, Depends, HTTPException, Header
from pydantic import BaseModel

import shared_db

if os.environ.get("APP_ENV", "development").lower() == "production" and not os.environ.get("JWT_SECRET"):
    raise RuntimeError("JWT_SECRET must be set when APP_ENV=production")
# Development can start without setup, but its sessions intentionally expire on
# process restart. Production always requires a stable secret from the platform.
SECRET_KEY = os.environ.get("JWT_SECRET") or secrets.token_urlsafe(48)
ALGORITHM = "HS256"
TOKEN_EXPIRE_HOURS = 24 * 7
OTP_EXPIRE_MINUTES = 10


class LoginRequest(BaseModel):
    email: str
    password: str


class UserOut(BaseModel):
    id: int
    email: str
    name: str
    role: str
    totp_enabled: bool = False


class LoginResponse(BaseModel):
    token: str
    user: UserOut


class OtpChallenge(BaseModel):
    otp_required: bool = True
    user_id: int
    demo_otp: str = ""
    is_totp: bool = False


class TotpSetupResponse(BaseModel):
    secret: str
    provisioning_uri: str
    qr_base64: str


class ConfirmTotpRequest(BaseModel):
    code: str


class VerifyOtpRequest(BaseModel):
    user_id: int
    code: str


class RegisterRequest(BaseModel):
    email: str
    password: str
    full_name: str


router = APIRouter()


def _send_otp_email(to_email: str, code: str) -> bool:
    smtp_host = os.environ.get("SMTP_HOST", "")
    smtp_port = int(os.environ.get("SMTP_PORT", "587"))
    smtp_user = os.environ.get("SMTP_USER", "")
    smtp_pass = os.environ.get("SMTP_PASS", "")
    if not all([smtp_host, smtp_user, smtp_pass]):
        return False
    msg = MIMEMultipart("alternative")
    msg["Subject"] = "Your QC Central verification code"
    msg["From"] = smtp_user
    msg["To"] = to_email
    msg.attach(MIMEText(
        f"Your QC Central verification code is: {code}\n\nThis code expires in {OTP_EXPIRE_MINUTES} minutes.",
        "plain",
    ))
    msg.attach(MIMEText(
        f"<p>Your QC Central verification code is:</p>"
        f"<p style='font-size:24px;font-weight:bold;letter-spacing:4px'>{code}</p>"
        f"<p>This code expires in {OTP_EXPIRE_MINUTES} minutes.</p>",
        "html",
    ))
    try:
        if smtp_port == 465:
            with smtplib.SMTP_SSL(smtp_host, smtp_port, timeout=15) as s:
                s.login(smtp_user, smtp_pass)
                s.sendmail(smtp_user, to_email, msg.as_string())
        else:
            with smtplib.SMTP(smtp_host, smtp_port, timeout=15) as s:
                s.starttls()
                s.login(smtp_user, smtp_pass)
                s.sendmail(smtp_user, to_email, msg.as_string())
        return True
    except Exception as e:
        logging.getLogger(__name__).error("SMTP error host=%s port=%s: %s", smtp_host, smtp_port, e)
        return False


def _verify_password(password: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode(), hashed.encode())
    except Exception:
        return False


def _make_token(user_id: int) -> str:
    exp = datetime.now(tz=timezone.utc) + timedelta(hours=TOKEN_EXPIRE_HOURS)
    return jwt.encode({"sub": str(user_id), "exp": exp}, SECRET_KEY, algorithm=ALGORITHM)


def _decode_token(token: str) -> Optional[int]:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return int(payload["sub"])
    except Exception:
        return None


def get_current_user(authorization: str = Header(default="")) -> dict:
    """FastAPI dependency — resolves Bearer token → user dict or raises 401."""
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    user_id = _decode_token(token)
    if user_id is None:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    if not shared_db.db_available():
        raise HTTPException(status_code=503, detail="Auth database not available")
    user = shared_db.get_user_by_id(user_id)
    if user is None:
        raise HTTPException(status_code=401, detail="User not found or deactivated")
    return user


def _user_out(user: dict) -> UserOut:
    return UserOut(
        id=user["id"], email=user["email"], name=user["full_name"], role=user["role"],
        totp_enabled=bool(user.get("totp_enabled")),
    )


@router.post("/auth/login", response_model=Union[LoginResponse, OtpChallenge])
def login(req: LoginRequest):
    if not shared_db.db_available():
        raise HTTPException(status_code=503, detail="Auth database not available")
    user = shared_db.get_user_by_email(req.email.strip().lower())
    if not user or not _verify_password(req.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    # The local demo admin skips email OTP only outside production.
    OTP_BYPASS = {"admin@example.com"} if os.environ.get("APP_ENV", "development").lower() != "production" else set()
    if user.get("email") in OTP_BYPASS:
        token = _make_token(user["id"])
        return LoginResponse(token=token, user=_user_out(user))

    code = f"{secrets.randbelow(1_000_000):06d}"
    otp_hash = bcrypt.hashpw(code.encode(), bcrypt.gensalt()).decode()
    expires_at = (datetime.now(tz=timezone.utc) + timedelta(minutes=OTP_EXPIRE_MINUTES)).isoformat()
    shared_db.set_user_otp(user["id"], otp_hash, expires_at)
    email_sent = _send_otp_email(user["email"], code)
    demo = "" if email_sent else code
    return OtpChallenge(user_id=user["id"], demo_otp=demo)


@router.post("/auth/verify-otp", response_model=LoginResponse)
def verify_otp(req: VerifyOtpRequest):
    if not shared_db.db_available():
        raise HTTPException(status_code=503, detail="Auth database not available")
    user = shared_db.get_user_by_id(req.user_id)
    if not user:
        raise HTTPException(status_code=401, detail="No pending verification for this user")

    if not user.get("otp_code"):
        raise HTTPException(status_code=401, detail="No pending verification for this user")
    expires_at = user.get("otp_expires_at")
    if not expires_at or datetime.now(tz=timezone.utc) > datetime.fromisoformat(expires_at):
        shared_db.clear_user_otp(user["id"])
        raise HTTPException(status_code=401, detail="Code expired — please log in again")
    if not bcrypt.checkpw(req.code.encode(), user["otp_code"].encode()):
        raise HTTPException(status_code=401, detail="Invalid code")
    shared_db.clear_user_otp(user["id"])
    token = _make_token(user["id"])
    return LoginResponse(token=token, user=_user_out(user))


@router.post("/auth/enable-2fa", response_model=UserOut)
def enable_2fa(user: dict = Depends(get_current_user)):
    shared_db.set_2fa_enabled(user["id"], True)
    user["totp_enabled"] = 1
    return _user_out(user)


@router.post("/auth/disable-2fa", response_model=UserOut)
def disable_2fa(user: dict = Depends(get_current_user)):
    shared_db.set_2fa_enabled(user["id"], False)
    user["totp_enabled"] = 0
    return _user_out(user)


@router.post("/auth/setup-totp", response_model=TotpSetupResponse)
def setup_totp(user: dict = Depends(get_current_user)):
    """Generate a new TOTP secret and return the QR code for Google Authenticator setup."""
    secret = pyotp.random_base32()
    totp = pyotp.TOTP(secret)
    label = user["email"]
    uri = totp.provisioning_uri(name=label, issuer_name="QC Central")

    # Generate QR code as base64 PNG
    img = qrcode.make(uri)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    qr_b64 = base64.b64encode(buf.getvalue()).decode()

    # Store secret temporarily — confirm-totp will activate it
    # We store it now so confirm can read it back; it's only "live" once confirmed
    shared_db.set_totp_secret(user["id"], secret)
    # But don't mark as enabled until confirmed — reset totp_enabled to 0 while pending
    shared_db.set_2fa_enabled(user["id"], False)

    return TotpSetupResponse(secret=secret, provisioning_uri=uri, qr_base64=qr_b64)


@router.post("/auth/confirm-totp", response_model=UserOut)
def confirm_totp(req: ConfirmTotpRequest, user: dict = Depends(get_current_user)):
    """Verify first TOTP code after scanning QR — activates Google Authenticator 2FA."""
    fresh = shared_db.get_user_by_id(user["id"])
    if not fresh or not fresh.get("totp_secret"):
        raise HTTPException(status_code=400, detail="No pending TOTP setup — call setup-totp first")
    totp = pyotp.TOTP(fresh["totp_secret"])
    if not totp.verify(req.code.strip(), valid_window=1):
        raise HTTPException(status_code=401, detail="Invalid code — check your authenticator app and try again")
    # Code verified — activate 2FA
    shared_db.set_2fa_enabled(user["id"], True)
    fresh["totp_enabled"] = 1
    return _user_out(fresh)


@router.post("/auth/disable-totp", response_model=UserOut)
def disable_totp(user: dict = Depends(get_current_user)):
    """Remove the TOTP secret and disable Google Authenticator 2FA."""
    shared_db.clear_totp_secret(user["id"])
    user["totp_enabled"] = 0
    return _user_out(user)


@router.post("/auth/register", response_model=LoginResponse)
def register(req: RegisterRequest):
    if not shared_db.db_available():
        raise HTTPException(status_code=503, detail="Auth database not available")
    if len(req.password) < 8:
        raise HTTPException(status_code=422, detail="Password must be at least 8 characters")
    hashed = bcrypt.hashpw(req.password.encode(), bcrypt.gensalt()).decode()
    ok, err = shared_db.create_user(
        req.email.strip().lower(), hashed, req.full_name.strip(), "other"
    )
    if not ok:
        raise HTTPException(status_code=409, detail=err)
    user = shared_db.get_user_by_email(req.email.strip().lower())
    token = _make_token(user["id"])
    return LoginResponse(token=token, user=_user_out(user))


@router.get("/auth/me", response_model=UserOut)
def me(user: dict = Depends(get_current_user)):
    return _user_out(user)
