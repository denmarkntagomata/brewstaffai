"""
app.py - BrewStaffAI (Streamlit). Internal system for Jungle Brew Café: Manager and Staff accounts only.

Run locally:   python -m streamlit run app.py
"""
from datetime import datetime, timedelta

import sqlalchemy as sa
import streamlit as st
from PIL import Image

import auth
import db
import ui

st.set_page_config(page_title="BrewStaffAI · Jungle Brew", layout="wide",
                   page_icon=Image.open(f"{ui.ASSETS}/logo_circle.png"))
ui.inject_css()

import login_page               # noqa: E402
import pages_manager as pm      # noqa: E402
import pages_pilot as pp        # noqa: E402
import pages_staff as ps        # noqa: E402
import session_cookie as sc     # noqa: E402
import settings_page as sp      # noqa: E402


def logout(msg=None):
    sc.end(msg)
    st.rerun()


def badge(title, n):
    return f"{title} ({n})" if n else title


def show_db_error(exc):
    st.error(db.friendly_error(exc), icon=":material/cloud_off:")
    st.caption(f"Technical detail for the developer: {type(exc).__name__}")
    if st.button("Try again", icon=":material/refresh:", type="primary"):
        st.rerun()


def main():
    db.init_db()
    db.cleanup()
    user = st.session_state.get("user") or sc.restore()

    if user:
        last = st.session_state.get("last_active")
        if last and datetime.now() - last > timedelta(minutes=auth.IDLE_MINUTES):
            logout("You were logged out after 30 minutes of no activity.")

    if not user:
        with st.sidebar:
            sc.clear_if_needed()
        if st.session_state.get("flash"):
            st.toast(st.session_state.pop("flash"), icon="🔒")
        login_page.render()
        return

    st.session_state.last_active = datetime.now()
    fresh = db.get_user(user["email"])
    if not fresh or not fresh["active"]:
        logout("Your account is no longer active.")
    with st.sidebar:
        sc.keep_alive()

    if fresh["must_change"]:
        sp.force_password_change(fresh)
        return

    st.logo(f"{ui.ASSETS}/logo_circle.png", size="large")
    with st.sidebar:
        st.markdown(f"<div class='bs-card' style='padding:12px 14px'><b>{ui.esc(user['full_name'])}</b><br>"
                    f"<span style='color:{ui.MUTED};font-size:.85rem'>{user['role'].title()} · "
                    f"{ui.esc(user['email'])}</span></div>", unsafe_allow_html=True)

    P = st.session_state.setdefault("pages", {})
    if user["role"] == "manager":
        new = db.count_new_reports()
        P.update(
            dashboard=st.Page(pm.dashboard, title="Dashboard", icon=":material/home:", url_path="dashboard",
                              default=True),
            planner=st.Page(pm.planner, title="Staffing Planner", icon=":material/calendar_month:",
                            url_path="planner"),
            reports=st.Page(pm.reports, title=badge("Staff Reports", new), icon=":material/inbox:",
                            url_path="reports"),
            pilot=st.Page(pp.pilot_results, title="Pilot Results", icon=":material/monitoring:", url_path="pilot"),
            ai=st.Page(pm.how_ai_works, title="How the AI Works", icon=":material/psychology:", url_path="ai"),
            settings=st.Page(sp.manager_settings, title="Settings", icon=":material/settings:", url_path="settings"))
        nav = {"Home": [P["dashboard"]], "AI Staffing": [P["planner"], P["reports"]],
               "Results": [P["pilot"], P["ai"]], "Account": [P["settings"]]}
    else:
        replies = db.count_unseen_replies(user["email"])
        P.update(
            home=st.Page(ps.home, title="My Shift Today", icon=":material/home:", url_path="home", default=True),
            eos=st.Page(ps.end_of_shift, title="End-of-Shift Report", icon=":material/edit_note:", url_path="eos"),
            incident=st.Page(ps.incident, title="Report an Incident", icon=":material/report:", url_path="incident"),
            mine=st.Page(ps.my_reports, title=badge("My Reports", replies), icon=":material/description:",
                         url_path="mine"),
            settings=st.Page(sp.staff_settings, title="Settings", icon=":material/settings:", url_path="settings"))
        nav = {"Home": [P["home"]], "Reports": [P["eos"], P["incident"], P["mine"]], "Account": [P["settings"]]}

    page = st.navigation(nav)
    with st.sidebar:
        st.divider()
        if st.button("Log out", icon=":material/logout:", width="stretch"):
            db.log(user["email"], "logout")
            logout("You have logged out.")
        st.caption(f"Auto logout after {auth.IDLE_MINUTES} min of no activity")
    page.run()


try:
    main()
except sa.exc.SQLAlchemyError as e:
    show_db_error(e)
