"""
app.py — BrewStaffAI v2 (Streamlit)
Internal web system for Jungle Brew Café: Manager and Staff accounts only.

Run locally:   python -m streamlit run app.py
"""
from datetime import datetime, timedelta

import streamlit as st
from PIL import Image

import auth
import db
import ui

st.set_page_config(page_title="BrewStaffAI · Jungle Brew", layout="wide",
                   page_icon=Image.open(f"{ui.ASSETS}/logo_circle.png"))
db.init_db()
ui.inject_css()

import login_page          # noqa: E402  (after page config)
import pages_manager as pm  # noqa: E402
import pages_staff as ps    # noqa: E402
import settings_page as sp  # noqa: E402


def logout(msg=None):
    st.session_state.clear()
    if msg:
        st.session_state.flash = msg
    st.rerun()


user = st.session_state.get("user")

# ---- automatic logout after 30 minutes without activity
if user:
    last = st.session_state.get("last_active")
    if last and datetime.now() - last > timedelta(minutes=auth.IDLE_MINUTES):
        logout("You were logged out after 30 minutes of no activity.")

if not user:
    if st.session_state.get("flash"):
        st.toast(st.session_state.pop("flash"), icon="🔒")
    login_page.render()
    st.stop()

st.session_state.last_active = datetime.now()
fresh = db.get_user(user["email"])
if not fresh or not fresh["active"]:
    logout("Your account is no longer active.")

# ---- staff created by the manager must set their own password first
if fresh["must_change"]:
    sp.force_password_change(fresh)
    st.stop()

# ---- sidebar
st.logo(f"{ui.ASSETS}/logo_circle.png", size="large")
with st.sidebar:
    icon = "🧑‍💼" if user["role"] == "manager" else "👩‍🍳"
    st.markdown(f"<div class='bs-card' style='padding:12px 14px'><div style='font-size:1.6rem'>{icon}</div>"
                f"<b>{user['full_name']}</b><br><span style='color:{ui.MUTED};font-size:.85rem'>"
                f"{user['role'].title()} · {user['email']}</span></div>", unsafe_allow_html=True)

P = st.session_state.setdefault("pages", {})
if user["role"] == "manager":
    P.update(dashboard=st.Page(pm.dashboard, title="Dashboard", icon="🏠", default=True),
             planner=st.Page(pm.planner, title="Staffing Planner", icon="📅"),
             reports=st.Page(pm.reports, title="Staff Reports", icon="🗂️"),
             ai=st.Page(pm.how_ai_works, title="How the AI Works", icon="🧠"),
             settings=st.Page(sp.manager_settings, title="Settings", icon="⚙️"))
    nav = {"Home": [P["dashboard"]], "AI Staffing": [P["planner"], P["reports"], P["ai"]], "Account": [P["settings"]]}
else:
    P.update(home=st.Page(ps.home, title="My Shift Today", icon="🏠", default=True),
             eos=st.Page(ps.end_of_shift, title="End-of-Shift Report", icon="📝"),
             incident=st.Page(ps.incident, title="Report an Incident", icon="⚠️"),
             mine=st.Page(ps.my_reports, title="My Reports", icon="📄"),
             settings=st.Page(sp.staff_settings, title="Settings", icon="⚙️"))
    nav = {"Home": [P["home"]], "Reports": [P["eos"], P["incident"], P["mine"]], "Account": [P["settings"]]}

page = st.navigation(nav)
with st.sidebar:
    st.divider()
    if st.button("🚪 Log out", width="stretch"):
        logout("You have logged out.")
    st.caption(f"🔒 Auto logout after {auth.IDLE_MINUTES} min of no activity")
page.run()
