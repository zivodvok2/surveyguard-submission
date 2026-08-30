import io
import os
import random
import smtplib
import string
from datetime import datetime, timedelta
from email.mime.text import MIMEText

import bcrypt
import pyotp
import qrcode
import streamlit as st
import database as db
from config import ROLES, SL_ACCENT, SL_MUTED, SL_TX, SL_LINE, SL_SURFACE, SL_BG, SL_CRITICAL


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode(), hashed.encode())
    except Exception:
        return False


def _generate_otp() -> str:
    return "".join(random.choices(string.digits, k=6))


def _send_otp_email(to_email: str, otp: str) -> bool:
    smtp_host = os.environ.get("SMTP_HOST", "")
    smtp_user = os.environ.get("SMTP_USER", "")
    smtp_pass = os.environ.get("SMTP_PASS", "")
    smtp_port = int(os.environ.get("SMTP_PORT", "587"))
    if not smtp_host or not smtp_user:
        return False
    import sys
    msg = MIMEText(
        f"Your QC Dashboard verification code is: {otp}\n\n"
        f"This code expires in 10 minutes.\n"
        f"If you did not request this, ignore this email."
    )
    msg["Subject"] = "[QC Dashboard] Your sign-in verification code"
    msg["From"] = smtp_user
    msg["To"] = to_email
    try:
        if smtp_port == 465:
            with smtplib.SMTP_SSL(smtp_host, smtp_port, timeout=15) as s:
                s.login(smtp_user, smtp_pass)
                s.send_message(msg)
        else:
            with smtplib.SMTP(smtp_host, smtp_port, timeout=15) as s:
                s.starttls()
                s.login(smtp_user, smtp_pass)
                s.send_message(msg)
        return True
    except Exception as e:
        print(f"[SMTP ERROR] host={smtp_host} port={smtp_port} error={e}", file=sys.stderr)
        return False


def _complete_login(user: dict):
    st.session_state["logged_in"]    = True
    st.session_state["user_id"]      = user["id"]
    st.session_state["user_email"]   = user["email"]
    st.session_state["user_name"]    = user["full_name"]
    st.session_state["user_role"]    = user["role"]
    st.session_state["page"]         = "dashboard"
    st.session_state["project_id"]   = None
    st.session_state["project_tab"]  = "quality_report"
    for k in ["otp_pending_user_id", "otp_sent_to", "otp_expires", "otp_method"]:
        st.session_state.pop(k, None)


def login(email: str, password: str):
    user = db.get_user_by_email(email.strip().lower())
    if not user:
        return False, "Invalid email or password."
    if not verify_password(password, user["password_hash"]):
        return False, "Invalid email or password."

    if user.get("totp_enabled"):
        totp_secret = user.get("totp_secret")
        if totp_secret:
            # Google Authenticator TOTP — ask for the 6-digit code from the app
            st.session_state["otp_pending_user_id"] = user["id"]
            st.session_state["otp_method"] = "totp"
            return "otp_sent", "Enter the 6-digit code from your authenticator app."
        else:
            # Fallback: email OTP
            otp = _generate_otp()
            expires = (datetime.utcnow() + timedelta(minutes=10)).isoformat()
            otp_hash = bcrypt.hashpw(otp.encode(), bcrypt.gensalt()).decode()
            db.set_user_otp(user["id"], otp_hash, expires)
            sent = _send_otp_email(user["email"], otp)
            st.session_state["otp_pending_user_id"] = user["id"]
            st.session_state["otp_sent_to"] = user["email"]
            st.session_state["otp_expires"] = expires
            st.session_state["otp_method"] = "email"
            if sent:
                return "otp_sent", f"A 6-digit code has been sent to {user['email']}."
            else:
                st.session_state["dev_otp"] = otp
                return "otp_sent", f"(Dev mode) Your OTP is: {otp}"

    _complete_login(user)
    return True, None


def verify_otp(otp_input: str):
    user_id = st.session_state.get("otp_pending_user_id")
    if not user_id:
        return False, "Session expired. Please sign in again."

    user = db.get_user_by_id(user_id)
    if not user:
        return False, "Invalid session."

    method = st.session_state.get("otp_method", "email")

    if method == "totp":
        secret = user.get("totp_secret")
        if not secret:
            return False, "Authenticator not configured. Contact an admin."
        totp = pyotp.TOTP(secret)
        if not totp.verify(otp_input.strip(), valid_window=1):
            return False, "Incorrect code. Please try again."
        _complete_login(user)
        return True, None
    else:
        expires_str = st.session_state.get("otp_expires", "")
        try:
            if datetime.utcnow() > datetime.fromisoformat(expires_str):
                return False, "Code expired. Please sign in again."
        except Exception:
            return False, "Session error. Please sign in again."
        if not user.get("otp_code"):
            return False, "Invalid session."
        if not bcrypt.checkpw(otp_input.encode(), user["otp_code"].encode()):
            return False, "Incorrect code. Please try again."
        db.clear_user_otp(user_id)
        _complete_login(user)
        return True, None


def generate_totp_secret(email: str) -> tuple[str, str]:
    """Generate a new TOTP secret and return (secret, provisioning_uri)."""
    secret = pyotp.random_base32()
    uri = pyotp.totp.TOTP(secret).provisioning_uri(
        name=email, issuer_name="Servallab QC"
    )
    return secret, uri


def totp_qr_bytes(uri: str) -> bytes:
    """Render a provisioning URI as a PNG QR code and return the raw bytes."""
    img = qrcode.make(uri)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def logout():
    for key in list(st.session_state.keys()):
        del st.session_state[key]


def guest_login():
    st.session_state["logged_in"]    = True
    st.session_state["user_id"]      = None
    st.session_state["user_email"]   = None
    st.session_state["user_name"]    = "Guest"
    st.session_state["user_role"]    = "qc_executive"
    st.session_state["is_guest"]     = True
    st.session_state["page"]         = "dashboard"
    st.session_state["project_id"]   = None
    st.session_state["project_tab"]  = "quality_report"


def require_login() -> bool:
    return st.session_state.get("logged_in", False)


def require_role(*roles) -> bool:
    return st.session_state.get("user_role") in roles


def show_login_page():
    _, col, _ = st.columns([1, 1, 1])
    with col:
        # ── Brand mark ──
        st.markdown(
            f"""<div style="text-align:center;padding:2.5rem 0 2rem;">
                <div style="display:inline-flex;align-items:center;gap:12px;margin-bottom:0.5rem;">
                    <div style="width:40px;height:40px;background:{SL_ACCENT};border-radius:8px;
                         display:flex;align-items:center;justify-content:center;">
                        <span style="font-family:Syne,sans-serif;font-weight:800;color:#0b0c0f;
                                     font-size:0.9rem;">SL</span>
                    </div>
                    <span style="font-family:Syne,sans-serif;font-weight:800;font-size:1.8rem;
                                 color:{SL_TX};">Servallab</span>
                </div>
                <p style="font-family:DM Mono,monospace;font-size:0.82rem;color:{SL_MUTED};
                           margin:0;">QC Dashboard &nbsp;·&nbsp; Internal use only</p>
            </div>""",
            unsafe_allow_html=True,
        )

        # ── Card container ──
        st.markdown(
            f"""<div style="background:{SL_SURFACE};border:1px solid {SL_LINE};
                 border-radius:10px;padding:1.75rem 1.5rem 1.25rem;">""",
            unsafe_allow_html=True,
        )

        tab_login, tab_register = st.tabs(["Sign In", "Register"])

        with tab_login:
            # ── OTP / TOTP verification step ──
            if st.session_state.get("otp_pending_user_id"):
                method = st.session_state.get("otp_method", "email")
                if method == "totp":
                    hint_text = "🔐 Open your authenticator app and enter the 6-digit code."
                else:
                    sent_to = st.session_state.get("otp_sent_to", "your email")
                    hint_text = f"📧 Verification code sent to <strong>{sent_to}</strong>. Enter it below."
                st.markdown(
                    f'<div style="background:rgba(0,181,163,0.08);border:1px solid rgba(0,181,163,0.3);'
                    f'border-radius:6px;padding:0.6rem 0.8rem;font-size:0.82rem;color:{SL_ACCENT};'
                    f'font-family:DM Mono,monospace;margin-bottom:0.75rem;">'
                    f'{hint_text}</div>',
                    unsafe_allow_html=True,
                )
                dev_otp = st.session_state.get("dev_otp")
                if dev_otp:
                    st.markdown(
                        f'<div style="background:rgba(240,192,74,0.12);border:1px solid rgba(240,192,74,0.4);'
                        f'border-radius:6px;padding:0.6rem 0.8rem;font-size:0.82rem;color:#f0c04a;'
                        f'font-family:DM Mono,monospace;margin-bottom:0.75rem;">'
                        f'&#9888; SMTP not configured &mdash; your code: '
                        f'<strong style="font-size:1.1rem;letter-spacing:3px;">{dev_otp}</strong></div>',
                    unsafe_allow_html=True,
                )
                with st.form("otp_form"):
                    otp_input = st.text_input("6-digit code", placeholder="123456", max_chars=6)
                    otp_submitted = st.form_submit_button("Verify", use_container_width=True, type="primary")
                if otp_submitted:
                    ok, err = verify_otp(otp_input.strip())
                    if ok:
                        st.rerun()
                    else:
                        st.markdown(
                            f'<div style="background:rgba(240,74,106,0.1);border:1px solid rgba(240,74,106,0.3);'
                            f'border-radius:6px;padding:0.6rem 0.8rem;font-size:0.82rem;color:{SL_CRITICAL};'
                            f'font-family:DM Mono,monospace;margin-top:0.5rem;">{err}</div>',
                            unsafe_allow_html=True,
                        )
                if st.button("← Back to sign in", use_container_width=False):
                    for k in ["otp_pending_user_id", "otp_sent_to", "otp_expires", "dev_otp", "otp_method"]:
                        st.session_state.pop(k, None)
                    st.rerun()
            else:
                # ── Normal sign in ──
                with st.form("login_form"):
                    email    = st.text_input("Email", placeholder="you@example.com")
                    password = st.text_input("Password", type="password", placeholder="••••••••")
                    submitted = st.form_submit_button(
                        "Sign In", use_container_width=True, type="primary"
                    )
                if submitted:
                    ok, err = login(email, password)
                    if ok is True:
                        st.rerun()
                    elif ok == "otp_sent":
                        st.markdown(
                            f'<div style="background:rgba(0,181,163,0.08);border:1px solid rgba(0,181,163,0.3);'
                            f'border-radius:6px;padding:0.6rem 0.8rem;font-size:0.82rem;color:{SL_ACCENT};'
                            f'font-family:DM Mono,monospace;margin-top:0.5rem;">{err}</div>',
                            unsafe_allow_html=True,
                        )
                        st.rerun()
                    else:
                        st.markdown(
                            f'<div style="background:rgba(240,74,106,0.1);border:1px solid rgba(240,74,106,0.3);'
                            f'border-radius:6px;padding:0.6rem 0.8rem;font-size:0.82rem;color:{SL_CRITICAL};'
                            f'font-family:DM Mono,monospace;margin-top:0.5rem;">{err}</div>',
                            unsafe_allow_html=True,
                        )

        with tab_register:
            with st.form("register_form"):
                r_name  = st.text_input("Full Name")
                r_email = st.text_input("Email", placeholder="you@example.com")
                r_pass  = st.text_input("Password", type="password", placeholder="Min. 8 characters")
                r_pass2 = st.text_input("Confirm Password", type="password")
                submitted2 = st.form_submit_button(
                    "Create Account", use_container_width=True, type="primary"
                )
            if submitted2:
                if not r_name or not r_email or not r_pass:
                    st.error("All fields are required.")
                elif r_pass != r_pass2:
                    st.error("Passwords do not match.")
                elif len(r_pass) < 8:
                    st.error("Password must be at least 8 characters.")
                else:
                    ok, err = db.create_user(
                        r_email.strip().lower(),
                        hash_password(r_pass),
                        r_name.strip(),
                        "other",
                    )
                    if ok:
                        st.markdown(
                            f'<div style="background:rgba(74,240,160,0.1);border:1px solid rgba(74,240,160,0.25);'
                            f'border-radius:6px;padding:0.6rem 0.8rem;font-size:0.82rem;color:{SL_ACCENT};'
                            f'font-family:DM Mono,monospace;margin-top:0.5rem;">'
                            f'Account created. Sign in — your role will be set by an admin.</div>',
                            unsafe_allow_html=True,
                        )
                    else:
                        st.error(err)

        st.markdown("</div>", unsafe_allow_html=True)

        # ── Guest access ──
        st.markdown(
            f'<p style="text-align:center;font-size:0.75rem;color:{SL_MUTED};'
            f'font-family:DM Mono,monospace;margin-top:1rem;">No account?</p>',
            unsafe_allow_html=True,
        )
        if st.button("Continue as Guest", use_container_width=True):
            guest_login()
            st.rerun()
