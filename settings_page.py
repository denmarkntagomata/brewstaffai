"""
settings_page.py - settings in one place.
Manager: My account · Team accounts · Café defaults · AI services · Data & backup
Staff:   My account
"""
import pandas as pd
import streamlit as st

import auth
import db
import privacy
from ai_helper import ai_status, ask_llm
from ui import AMBER, LEVEL_COLOR, MUTED, RED, badge, esc, kpi, page_header, password_feedback


# ------------------------------------------------------------------ shared
def _change_password_box(user, require_current=True, key="cp"):
    if require_current:
        cur = st.text_input("Current password", type="password", key=f"{key}_cur")
    new = st.text_input("New password", type="password", key=f"{key}_new")
    password_feedback(new, user["email"])
    new2 = st.text_input("Type the new password again", type="password", key=f"{key}_new2")
    if st.button("Save new password", type="primary", key=f"{key}_btn"):
        if require_current and not db.check_password(user["email"], cur):
            st.error("Your current password is incorrect.")
        elif not auth.password_ok(new, user["email"]):
            st.error("The new password does not meet all the rules.")
        elif new != new2:
            st.error("The two new passwords do not match.")
        else:
            db.change_password(user["email"], new)
            st.success("Password changed.")
            return True
    return False


def _my_account(user):
    c1, c2 = st.columns([1, 1.4], gap="large")
    with c1:
        st.markdown("##### Profile")
        st.markdown(f"**Name:** {esc(user['full_name'])}  \n**Email:** {esc(user['email'])}  \n"
                    f"**Role:** {user['role'].title()}")
        st.caption("To change your name or email, ask the manager.")
        with st.expander("Privacy notice"):
            privacy.show_notice_text()
            accepted = (db.get_user(user["email"]) or {}).get("privacy_at")
            if accepted:
                st.caption(f"You accepted this notice on {accepted[:16]}.")
    with c2:
        st.markdown("##### Change password")
        _change_password_box(user)


def force_password_change(user):
    page_header("Set your own password",
                "Your manager created this account with a temporary password. Please choose your own before continuing.")
    _, mid, _ = st.columns([1, 2, 1])
    with mid:
        if _change_password_box(user, require_current=False, key="force"):
            st.session_state.user["must_change"] = 0
            st.rerun()


# ------------------------------------------------------------------ staff
def staff_settings():
    user = st.session_state.user
    page_header("Settings", "Your profile and password.")
    _my_account(user)


# ------------------------------------------------------------------ manager
def manager_settings():
    user = st.session_state.user
    page_header("Settings", "Everything you can change in BrewStaffAI, grouped in one place.")
    t1, t2, t3, t4, t5 = st.tabs(["My account", "Team accounts", "Café defaults", "AI services", "Data & backup"])
    with t1:
        _my_account(user)
    with t2:
        _team(user)
    with t3:
        _cafe_defaults()
    with t4:
        _ai_services()
    with t5:
        _data_backup(user)


def _team(user):
    users = db.list_users()
    a, b, c = st.columns(3)
    with a:
        kpi("Active accounts", sum(u["active"] for u in users))
    with b:
        kpi("Staff", sum(u["role"] == "staff" and u["active"] for u in users))
    with c:
        kpi("Waiting to set password", sum(u["must_change"] for u in users), color=AMBER)
    st.write("")
    df = pd.DataFrame(users)
    df["Status"] = df.active.map(lambda a: "Active" if a else "Deactivated")
    df["Password"] = df.must_change.map(lambda m: "Temporary" if m else "Set by user")
    st.dataframe(df.rename(columns={"full_name": "Name", "email": "Email", "role": "Role", "last_login": "Last login"})
                 [["Name", "Email", "Role", "Status", "Password", "Last login"]], hide_index=True, width="stretch")

    left, right = st.columns(2, gap="large")
    with left:
        with st.container(border=True):
            st.markdown("##### Add a team member")
            name = st.text_input("Full name", key="add_name")
            email = st.text_input("Work email", placeholder=f"name@{auth.COMPANY_DOMAIN}", key="add_email")
            if email and auth.email_problem(email):
                st.error(auth.email_problem(email))
            role = st.radio("Role", ["staff", "manager"], horizontal=True, key="add_role",
                            format_func=str.title)
            if st.button("Create account", type="primary", key="add_btn"):
                if not name.strip() or auth.email_problem(email):
                    st.error("Please enter a name and a valid work email.")
                else:
                    temp = auth.generate_password()
                    try:
                        db.create_user(email, name, role, temp, must_change=True, by=st.session_state.user["email"])
                        st.success(f"Account created for {name}.")
                        st.markdown("**Temporary password** (shown only once; give it to the person privately):")
                        st.code(temp, language=None)
                        st.caption("They will be asked to set their own password on first login.")
                    except ValueError as e:
                        st.error(str(e))
    with right:
        with st.container(border=True):
            st.markdown("##### Manage an account")
            others = [u for u in users if u["email"] != user["email"]]
            if not others:
                st.info("No other accounts yet.")
                return
            pick = st.selectbox("Choose a person", others, format_func=lambda u: f"{u['full_name']} ({u['email']})")
            c1, c2 = st.columns(2)
            if c1.button("Reset password", icon=":material/lock_reset:", width="stretch"):
                temp = auth.generate_password()
                db.change_password(pick["email"], temp, must_change=True, by=st.session_state.user["email"])
                st.success("Password reset. New temporary password (shown once):")
                st.code(temp, language=None)
            label = "Deactivate" if pick["active"] else "Reactivate"
            if c2.button(label, icon=":material/person_off:" if pick["active"] else ":material/person:",
                         width="stretch"):
                db.set_active(pick["email"], not pick["active"], by=st.session_state.user["email"])
                st.rerun()


def _cafe_defaults():
    st.caption("These numbers feed the Staffing Planner. Update them after the on-site observation.")
    prof = db.get_setting("hourly_profile")
    svc = db.get_setting("service_times")
    left, right = st.columns([1.2, 1], gap="large")
    with left:
        st.markdown("##### Usual customers per hour")
        df = pd.DataFrame({"Hour": [f"{int(h):02d}:00-{int(h) + 1:02d}:00" for h in prof],
                           "Customers": list(prof.values())})
        edited = st.data_editor(df, hide_index=True, disabled=["Hour"], width="stretch", key="prof_edit",
                                column_config={"Customers": st.column_config.NumberColumn(min_value=0, max_value=120)})
        st.bar_chart(edited.set_index("Hour"), color="#A6CE39", height=200)
    with right:
        st.markdown("##### Service times (minutes)")
        cm = st.number_input("Cashier: time per order", 0.3, 5.0, float(svc["cashier"]), 0.1)
        sp_ = st.number_input("Barista: simple drink", 0.5, 8.0, float(svc["simple"]), 0.1)
        cp = st.number_input("Barista: complex drink", 1.0, 12.0, float(svc["complex"]), 0.1)
        ps = st.slider("Share of simple drinks (%)", 0, 100, int(svc["p_simple"] * 100), 5)
        mx = st.slider("Most counter staff available in one hour", 2, 6, int(db.get_setting("max_counter_staff")))
        st.markdown("##### Congestion levels (agreed with the manager)")
        st.markdown(f"{badge('Okay')} ≤ 7 min  {badge('Congested')} 7–15 min  {badge('Overloaded')} > 15 min",
                    unsafe_allow_html=True)
        st.caption("Changing these levels requires retraining the AI (labels.py → train_model.py).")
    if st.button("Save café defaults", icon=":material/save:", type="primary"):
        db.set_setting("hourly_profile", {k: int(v) for k, v in zip(prof.keys(), edited["Customers"])}, by=st.session_state.user["email"])
        db.set_setting("service_times", {"cashier": cm, "simple": sp_, "complex": cp, "p_simple": ps / 100}, by=st.session_state.user["email"])
        db.set_setting("max_counter_staff", mx, by=st.session_state.user["email"])
        st.success("Saved. The planner will use these numbers from now on.")


def _ai_services():
    s = ai_status()
    c1, c2 = st.columns(2)
    with c1:
        kpi("Gemini (main)", "Connected" if s["Gemini"] else "No key", s["Gemini model"],
            color=LEVEL_COLOR["Okay"] if s["Gemini"] else RED)
    with c2:
        kpi("Groq (backup)", "Connected" if s["Groq"] else "Not set", s["Groq model"],
            color=LEVEL_COLOR["Okay"] if s["Groq"] else MUTED)
    st.write("")
    if st.button("Test AI connection", icon=":material/network_check:"):
        with st.spinner("Asking the AI..."):
            text, provider = ask_llm("Reply with exactly: BrewStaffAI is ready.")
        if provider:
            st.success(f"{provider} replied: {text}")
        else:
            st.error("No AI service answered. Check the keys in .streamlit/secrets.toml (see README).")
    st.caption("Keys are stored in .streamlit/secrets.toml (never in the code, never uploaded to GitHub). "
               "Staff names are removed before any text is sent to an AI service.")


# ------------------------------------------------------------------ data & backup
ACTION_LABELS = {
    "login": "Logged in", "logout": "Logged out", "login_failed": "Failed login", "account_locked": "Account locked",
    "account_created": "Account created", "password_changed": "Password changed", "password_reset": "Password reset",
    "account_activated": "Account activated", "account_deactivated": "Account deactivated",
    "setup_code_wrong": "Wrong setup code", "plan_published": "Plan published", "settings_changed": "Settings changed",
    "report_status": "Report status changed", "report_edited": "Report edited by sender",
    "report_deleted": "Report deleted", "report_reply": "Manager replied", "report_archived": "Report archived",
    "report_restored": "Report restored", "archive_auto_deleted": "Old archived reports deleted",
    "tag_checked": "AI tag checked", "privacy_accepted": "Privacy notice accepted",
    "privacy_declined": "Privacy notice declined", "tag_checks_cleared": "Tag checks cleared", "data_exported": "Data exported",
}


def _data_backup(user):
    info = db.backend_info()
    ok, ms = db.ping()
    n = db.counts()
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        kpi("Database", "Cloud" if info["mode"] == "cloud" else "Local",
            info["label"], color=LEVEL_COLOR["Okay"] if info["mode"] == "cloud" else AMBER)
    with c2:
        kpi("Connection", "Online" if ok else "Offline", f"{ms} ms response" if ok else "check DATABASE_URL",
            color=LEVEL_COLOR["Okay"] if ok else RED)
    with c3:
        kpi("Records", f"{n['reports']} reports", f"{n['users']} accounts · {n['plans']} plan hours")
    with c4:
        kpi("Activity log", f"{n['audit']} events", "logins, changes, exports")
    if info["mode"] == "local":
        st.info("You are using the **local** database: accounts and reports exist only on this computer. "
                "To share one database with the whole team, add a free Neon `DATABASE_URL` to "
                "`.streamlit/secrets.toml` (see **DEPLOY.md**).")
    else:
        st.success("Everyone who opens BrewStaffAI shares this database: the same accounts, reports, and plans.")

    st.write("")
    with st.container(border=True):
        st.markdown("##### Full backup")
        st.caption("All accounts (without passwords), reports, plans, settings, and the activity log as CSV "
                   "files in one ZIP. Download one every day during the pilot.")
        if st.button("Prepare backup", key="bk_prep"):
            st.session_state.backup_zip = db.export_zip(by=user["email"])
        if st.session_state.get("backup_zip"):
            st.download_button("Download BrewStaffAI backup (.zip)", st.session_state.backup_zip,
                               file_name=f"brewstaffai_backup_{db.ph_today()}.zip", mime="application/zip",
                               type="primary", icon=":material/download:")

    st.markdown("##### Activity log")
    st.caption("Who did what, and when (Philippine time). Useful for accountability during the pilot.")
    log = pd.DataFrame(db.get_audit(300))
    if log.empty:
        st.info("No activity yet.")
    else:
        log["action"] = log["action"].map(lambda a: ACTION_LABELS.get(a, a))
        st.dataframe(log.rename(columns={"at": "When", "actor": "Who", "action": "What", "detail": "Details"}),
                     hide_index=True, width="stretch", height=320)
