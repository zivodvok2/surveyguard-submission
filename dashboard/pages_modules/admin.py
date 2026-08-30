import streamlit as st
import pandas as pd
import database as db
import auth as auth_module
from config import IPSOS_NAVY, IPSOS_TEAL, ROLES, ADMIN_ROLES, SL_ACCENT, SL_CRITICAL, SL_TX, SL_MUTED, SL_LINE, SL_SURFACE2
from utils.exports import to_excel_bytes


def show():
    st.markdown(
        f'<h2 style="color:{IPSOS_NAVY}; border-bottom: 3px solid {IPSOS_TEAL}; padding-bottom:0.4rem;">Admin Panel</h2>',
        unsafe_allow_html=True,
    )

    role = st.session_state["user_role"]
    if role not in ADMIN_ROLES:
        st.error("Access denied. Admins only.")
        return

    tab_users, tab_projects, tab_assignments, tab_uploads, tab_2fa = st.tabs(
        ["User Management", "Project Management", "Project Assignments", "Upload History", "2FA Management"]
    )

    # ── User Management ────────────────────────────────────────────────────
    with tab_users:
        st.markdown("### Users")
        users = db.get_all_users()
        df = pd.DataFrame(users)[["id", "email", "full_name", "role", "is_active", "created_at"]]
        df.columns = ["ID", "Email", "Name", "Role", "Active", "Created"]
        st.dataframe(df, use_container_width=True, hide_index=True)

        st.markdown("---")
        col1, col2 = st.columns(2)

        with col1:
            st.markdown("#### Change User Role")
            user_opts = {f"{u['full_name']} ({u['email']})": u["id"] for u in users}
            selected_label = st.selectbox("Select User", list(user_opts.keys()), key="role_user")
            new_role = st.selectbox("New Role", list(ROLES.keys()),
                                    format_func=lambda r: ROLES[r], key="role_new")
            if st.button("Update Role", key="role_btn"):
                db.update_user_role(user_opts[selected_label], new_role)
                st.success("Role updated.")
                st.rerun()

        with col2:
            st.markdown("#### Activate / Deactivate User")
            sel2 = st.selectbox("Select User", list(user_opts.keys()), key="act_user")
            action = st.radio("Action", ["Activate", "Deactivate"], horizontal=True, key="act_radio")
            if st.button("Apply", key="act_btn"):
                db.toggle_user_active(user_opts[sel2], 1 if action == "Activate" else 0)
                st.success(f"User {action.lower()}d.")
                st.rerun()

        st.markdown("#### Add New User (Admin)")
        with st.form("admin_add_user"):
            a_name = st.text_input("Full Name")
            a_email = st.text_input("Email")
            a_role = st.selectbox("Role", list(ROLES.keys()), format_func=lambda r: ROLES[r])
            a_pass = st.text_input("Temporary Password", type="password")
            submitted = st.form_submit_button("Create User")
        if submitted:
            if not all([a_name, a_email, a_role, a_pass]):
                st.error("All fields required.")
            elif len(a_pass) < 8:
                st.error("Password must be at least 8 characters.")
            else:
                ok, err = db.create_user(
                    a_email.strip().lower(),
                    auth_module.hash_password(a_pass),
                    a_name.strip(),
                    a_role,
                    st.session_state["user_id"],
                )
                if ok:
                    st.success(f"User {a_name} created with role {ROLES[a_role]}.")
                    st.rerun()
                else:
                    st.error(err)

    # ── Project Management ─────────────────────────────────────────────────
    with tab_projects:
        st.markdown("### Projects")
        projects = db.get_all_projects()
        if projects:
            df_cols = ["id", "job_number", "name", "client", "sample_target", "status", "start_date", "end_date"]
            existing_cols = [c for c in df_cols if c in projects[0]]
            df = pd.DataFrame(projects)[existing_cols]
            col_labels = {"id": "ID", "job_number": "Job No.", "name": "Name", "client": "Client",
                          "sample_target": "Target", "status": "Status", "start_date": "Start", "end_date": "End"}
            df.columns = [col_labels.get(c, c) for c in existing_cols]
            st.dataframe(df, use_container_width=True, hide_index=True)

        st.markdown("---")
        st.markdown("#### Add New Project")
        with st.form("add_project_form"):
            pa1, pa2 = st.columns(2)
            p_name = pa1.text_input("Project Name *")
            p_job  = pa2.text_input("Job Number", placeholder="e.g. KE-2025-042")
            p_client = st.text_input("Client / Study Name")
            p_target = st.number_input("Sample Target", min_value=0, value=1000, step=50)
            c1, c2 = st.columns(2)
            p_start = c1.date_input("Start Date")
            p_end = c2.date_input("End Date")
            c3, c4, c5 = st.columns(3)
            p_bc = c3.slider("Back-check Target (%)", 5, 50, 20) / 100
            p_li = c4.slider("Listen-in Target (%)", 5, 30, 10) / 100
            p_acc = c5.slider("Accompaniment Target (%)", 5, 50, 20) / 100
            submitted_p = st.form_submit_button("Create Project")
        if submitted_p:
            if not p_name:
                st.error("Project name is required.")
            else:
                db.create_project(
                    p_name, p_client, p_target,
                    str(p_start), str(p_end),
                    p_bc, p_li, p_acc,
                    st.session_state["user_id"],
                    job_number=p_job.strip() or None,
                )
                st.success(f"Project '{p_name}' created.")
                st.rerun()

        st.markdown("#### Edit Project")
        if projects:
            proj_opts = {f"{p.get('job_number', '') and p['job_number']+' — ' or ''}{p['name']}": p["id"] for p in projects}
            sel_proj = st.selectbox("Select Project to Edit", list(proj_opts.keys()), key="edit_proj")
            sel_pid = proj_opts[sel_proj]
            cur = next(p for p in projects if p["id"] == sel_pid)

            with st.form("edit_project_form"):
                from datetime import date as _date
                def _parse_date(s):
                    try:
                        return _date.fromisoformat(str(s))
                    except Exception:
                        return _date.today()

                ep1, ep2 = st.columns(2)
                e_name   = ep1.text_input("Project Name *", value=cur["name"])
                e_job    = ep2.text_input("Job Number", value=cur.get("job_number") or "")
                e_client = st.text_input("Client / Study Name", value=cur.get("client") or "")
                e_target = st.number_input("Sample Target", min_value=0,
                                           value=int(cur.get("sample_target") or 0), step=50)
                ec1, ec2 = st.columns(2)
                e_start  = ec1.date_input("Start Date", value=_parse_date(cur.get("start_date")))
                e_end    = ec2.date_input("End Date",   value=_parse_date(cur.get("end_date")))
                ec3, ec4, ec5 = st.columns(3)
                e_bc  = ec3.slider("Back-check Target (%)",   5, 50, int(round((cur.get("backcheck_target")    or 0.20) * 100))) / 100
                e_li  = ec4.slider("Listen-in Target (%)",    5, 30, int(round((cur.get("listenin_target")     or 0.10) * 100))) / 100
                e_acc = ec5.slider("Accompaniment Target (%)", 5, 50, int(round((cur.get("accompaniment_target") or 0.20) * 100))) / 100
                e_status = st.selectbox("Status", ["active", "paused", "completed"],
                                        index=["active", "paused", "completed"].index(cur.get("status", "active")))

                st.markdown("##### Flag Calibration (project-specific)")
                fc1, fc2, fc3, fc4 = st.columns(4)
                e_loi_min = fc1.number_input(
                    "Min LOI (minutes)", min_value=0.0, max_value=120.0, step=0.5,
                    value=float(cur.get("loi_min_minutes") or 0),
                    help="Absolute minimum interview duration. 0 = not used.",
                )
                e_loi_pct = fc2.slider(
                    "Short LOI threshold (% of avg)", 10, 80,
                    int(round((cur.get("loi_pct_threshold") or 0.50) * 100)),
                    help="Flag interviews shorter than X% of project average.",
                ) / 100
                e_warn_pct = fc3.slider(
                    "Flag warning level (%)", 1, 20,
                    int(round(cur.get("flag_warning_pct") or 5.0)),
                    help="Flagged rate at which a warning alert is raised.",
                )
                e_crit_pct = fc4.slider(
                    "Flag critical level (%)", 1, 30,
                    int(round(cur.get("flag_critical_pct") or 10.0)),
                    help="Flagged rate at which a critical alert is raised.",
                )

                save_edit = st.form_submit_button("Save Changes", use_container_width=True)

            if save_edit:
                if not e_name:
                    st.error("Project name is required.")
                else:
                    db.update_project(
                        sel_pid,
                        name=e_name, job_number=e_job.strip() or None,
                        client=e_client, sample_target=e_target,
                        start_date=str(e_start), end_date=str(e_end),
                        backcheck_target=e_bc, listenin_target=e_li,
                        accompaniment_target=e_acc, status=e_status,
                        loi_min_minutes=e_loi_min, loi_pct_threshold=e_loi_pct,
                        flag_warning_pct=float(e_warn_pct), flag_critical_pct=float(e_crit_pct),
                    )
                    st.success(f"Project '{e_name}' updated.")
                    st.rerun()

    # ── Project Assignments ────────────────────────────────────────────────
    with tab_assignments:
        st.markdown("### Project Assignments")
        projects = db.get_all_projects()
        users = db.get_all_users()

        if not projects:
            st.info("No projects yet.")
        else:
            proj_opts = {p["name"]: p["id"] for p in projects}
            sel = st.selectbox("Select Project", list(proj_opts.keys()), key="assign_proj")
            pid = proj_opts[sel]
            assignees = db.get_project_assignees(pid)

            st.markdown(f"**Currently assigned ({len(assignees)}):**")
            for a in assignees:
                c1, c2, c3 = st.columns([3, 2, 1])
                c1.write(f"{a['full_name']} ({a['email']})")
                c2.caption(ROLES.get(a["role"], a["role"]))
                if c3.button("Remove", key=f"rm_{pid}_{a['id']}"):
                    db.remove_user_from_project(pid, a["id"])
                    st.rerun()

            st.markdown("**Assign users:**")
            assigned_ids = {a["id"] for a in assignees}
            unassigned = [u for u in users if u["id"] not in assigned_ids]
            if unassigned:
                user_opts = {f"{u['full_name']} ({u['email']})": u["id"] for u in unassigned}
                to_add = st.multiselect("Select users to assign", list(user_opts.keys()), key="assign_users")
                if st.button("Assign Selected", key="assign_btn"):
                    for label in to_add:
                        db.assign_user_to_project(pid, user_opts[label], st.session_state["user_id"])
                    st.success("Users assigned.")
                    st.rerun()
            else:
                st.caption("All users are already assigned to this project.")

    # ── Upload History ─────────────────────────────────────────────────────
    with tab_uploads:
        st.markdown("### Upload History (All Projects)")
        logs = db.get_upload_log()
        if logs:
            log_df = pd.DataFrame(logs)[[
                "project_name", "report_type", "filename", "row_count",
                "uploader_name", "upload_date", "upload_id"
            ]]
            log_df.columns = ["Project", "Type", "File", "Rows", "Uploader", "Date", "Upload ID"]
            st.dataframe(log_df, use_container_width=True, hide_index=True)

            st.markdown("#### Delete an Upload")
            upload_opts = {
                f"{l['project_name']} — {l['report_type']} — {l['filename']} ({l['upload_date'][:10]})": (
                    l["upload_id"], l["report_type"]
                )
                for l in logs
            }
            sel_log = st.selectbox("Select Upload to Delete", list(upload_opts.keys()), key="del_upload")
            if st.button("Delete Upload", type="secondary"):
                uid, rtype = upload_opts[sel_log]
                db.delete_upload(uid, rtype)
                st.success("Upload deleted.")
                st.rerun()
        else:
            st.info("No uploads yet.")

    # ── 2FA Management ────────────────────────────────────────────────────────
    with tab_2fa:
        st.markdown(
            f'<h3 style="font-family:Syne,sans-serif;font-weight:700;color:{SL_TX};">'
            f'Two-Factor Authentication</h3>'
            f'<p style="color:{SL_MUTED};font-size:0.82rem;font-family:DM Mono,monospace;">'
            f'Optional TOTP 2FA via Google Authenticator. Enable per user below — '
            f'they will need to scan the QR code once, then enter a 6-digit code on every login.</p>',
            unsafe_allow_html=True,
        )

        users_2fa = db.get_all_users()
        if not users_2fa:
            st.info("No users found.")
        else:
            # Summary table
            rows_html = ""
            for u in users_2fa:
                enabled = bool(u.get("totp_enabled"))
                status_color = SL_ACCENT if enabled else SL_MUTED
                status_text = "Enabled" if enabled else "Disabled"
                rows_html += (
                    f'<tr>'
                    f'<td style="padding:5px 12px;font-size:0.8rem;color:{SL_TX};">{u["full_name"]}</td>'
                    f'<td style="padding:5px 12px;font-size:0.8rem;color:{SL_MUTED};">{u["email"]}</td>'
                    f'<td style="padding:5px 12px;font-size:0.8rem;color:{status_color};font-weight:600;">{status_text}</td>'
                    f'</tr>'
                )
            st.markdown(
                f'<table style="width:100%;border-collapse:collapse;font-family:DM Mono,monospace;margin-bottom:1.5rem;">'
                f'<thead><tr style="border-bottom:1px solid {SL_LINE};">'
                f'<th style="padding:6px 12px;text-align:left;font-size:0.73rem;color:{SL_MUTED};">Name</th>'
                f'<th style="padding:6px 12px;text-align:left;font-size:0.73rem;color:{SL_MUTED};">Email</th>'
                f'<th style="padding:6px 12px;text-align:left;font-size:0.73rem;color:{SL_MUTED};">2FA Status</th>'
                f'</tr></thead>'
                f'<tbody>{rows_html}</tbody></table>',
                unsafe_allow_html=True,
            )

            st.markdown(f'<hr style="border-color:{SL_LINE};">', unsafe_allow_html=True)

            user_2fa_opts = {f"{u['full_name']} ({u['email']})": u for u in users_2fa}
            sel_2fa_label = st.selectbox("Select user", list(user_2fa_opts.keys()), key="2fa_user_sel")
            sel_user = user_2fa_opts[sel_2fa_label]
            already_enabled = bool(sel_user.get("totp_enabled"))

            col_enable, col_disable = st.columns(2)
            with col_enable:
                if st.button("Generate QR Code / Setup 2FA", key="2fa_setup_btn", use_container_width=True):
                    secret, uri = auth_module.generate_totp_secret(sel_user["email"])
                    db.set_totp_secret(sel_user["id"], secret)
                    st.session_state["2fa_setup_secret"] = secret
                    st.session_state["2fa_setup_uri"] = uri
                    st.session_state["2fa_setup_user"] = sel_user["email"]
                    st.rerun()

            with col_disable:
                if already_enabled:
                    if st.button("Disable 2FA for this user", key="2fa_disable_btn",
                                 use_container_width=True, type="secondary"):
                        db.disable_totp(sel_user["id"])
                        st.success(f"2FA disabled for {sel_user['full_name']}.")
                        st.rerun()

            # QR code display (shown after generating)
            if st.session_state.get("2fa_setup_user") == sel_user["email"] and st.session_state.get("2fa_setup_secret"):
                secret = st.session_state["2fa_setup_secret"]
                uri = st.session_state["2fa_setup_uri"]
                qr_bytes = auth_module.totp_qr_bytes(uri)

                st.markdown(
                    f'<div style="background:{SL_SURFACE2};border:1px solid {SL_LINE};border-radius:8px;'
                    f'padding:1rem 1.25rem;margin-top:1rem;">'
                    f'<div style="font-family:Syne,sans-serif;font-weight:700;color:{SL_TX};margin-bottom:0.5rem;">'
                    f'Setup Instructions</div>'
                    f'<ol style="color:{SL_MUTED};font-family:DM Mono,monospace;font-size:0.82rem;margin:0;padding-left:1.2rem;">'
                    f'<li>Open <strong style="color:{SL_TX};">Google Authenticator</strong> (or Authy) on your phone.</li>'
                    f'<li>Tap the <strong style="color:{SL_TX};">+</strong> button and select <strong style="color:{SL_TX};">Scan a QR code</strong>.</li>'
                    f'<li>Scan the QR code below.</li>'
                    f'<li>On next login, enter the 6-digit rotating code from the app.</li>'
                    f'</ol></div>',
                    unsafe_allow_html=True,
                )

                img_col, info_col = st.columns([1, 2])
                with img_col:
                    st.image(qr_bytes, caption="Scan with authenticator app", width=200)
                with info_col:
                    st.markdown(
                        f'<div style="font-family:DM Mono,monospace;font-size:0.78rem;color:{SL_MUTED};margin-top:0.5rem;">'
                        f'<div style="color:{SL_TX};font-weight:600;margin-bottom:4px;">Manual entry key</div>'
                        f'<code style="background:{SL_LINE};padding:4px 8px;border-radius:4px;'
                        f'color:{SL_ACCENT};letter-spacing:2px;font-size:0.88rem;">{secret}</code>'
                        f'<br><br>'
                        f'<span style="color:{SL_MUTED};">User: <strong style="color:{SL_TX};">{sel_user["email"]}</strong></span>'
                        f'<br><span style="color:{SL_MUTED};">Issuer: Servallab QC</span>'
                        f'</div>',
                        unsafe_allow_html=True,
                    )

                st.info("2FA is now active for this user. Share the QR code or manual key securely — it is only shown once.")
                if st.button("Done", key="2fa_done_btn"):
                    for k in ["2fa_setup_secret", "2fa_setup_uri", "2fa_setup_user"]:
                        st.session_state.pop(k, None)
                    st.rerun()
