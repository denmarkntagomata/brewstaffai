"""
login_page.py - login screen (based on the group's Canva design).
Left: storefront photo. Right: logo, Staff/Manager switch, login form.
With no manager yet, the right side shows the one-time setup form, protected by SETUP_CODE.
"""
import secrets

import streamlit as st

import auth
import db
import session_cookie
from ui import BORDER, MUTED, TEXT, asset_b64, password_feedback

LOGIN_CSS = f"""
<style>
header[data-testid="stHeader"], section[data-testid="stSidebar"], div[data-testid="stSidebarCollapsedControl"] {{display:none;}}
.block-container {{ padding:0 !important; max-width:100% !important; }}
.st-key-login div[data-testid="stHorizontalBlock"] {{ gap:0 !important; align-items:stretch; }}
.st-key-login div[data-testid="stColumn"]:first-child {{ padding:0 !important; }}
.st-key-login div[data-testid="stColumn"]:last-child {{ height:100vh; overflow-y:auto; }}
html, body, section.stMain, [data-testid="stMain"] {{ overflow:hidden; }}
.bs-photo {{ height:100vh; min-height:640px; background-size:cover; background-position:center 45%;
  image-rendering:auto;
  position:relative; }}
.bs-photo::after {{ content:""; position:absolute; inset:0;
  background:linear-gradient(90deg, rgba(14,19,17,0) 60%, rgba(14,19,17,.85) 100%); }}
.bs-logo {{ display:flex; justify-content:center; margin:4vh 0 1.2vh 0; }}
.bs-logo img {{ width:min(190px, 46vw); height:auto; border-radius:50%; box-shadow:0 10px 40px rgba(0,0,0,.45); }}
.bs-login-title {{ font-size:2.3rem; font-weight:800; margin:4px 0 0 0; color:{TEXT}; }}
.bs-tag {{ color:{MUTED}; margin:2px 0 18px 0; font-size:0.98rem; }}
.bs-help {{ color:{MUTED}; font-size:0.86rem; margin-top:10px; }}
.bs-secure {{ display:block; line-height:1.6; color:{MUTED}; font-size:0.82rem; margin-top:18px;
  border-top:1px solid {BORDER}; padding-top:12px; }}
@media (max-width: 820px) {{
  html, body, section.stMain, [data-testid="stMain"] {{ overflow:auto; }}
  .st-key-login div[data-testid="stColumn"]:last-child {{ height:auto; }}
  .st-key-login div[data-testid="stColumn"]:first-child {{ display:none; }}
  .bs-logo {{ margin-top:3vh; }}
  .st-key-login div[data-testid="stColumn"]:last-child {{ padding:0 18px 24px 18px !important; }}
  .bs-login-title {{ font-size:1.9rem; }}
}}
</style>"""


def _brand_block():
    st.markdown(f"<div class='bs-logo'><img src='data:image/png;base64,{asset_b64('logo_circle.png')}' "
                f"alt='Jungle Brew Café & Resto logo'></div>"
                "<div class='bs-login-title'>BrewStaffAI</div>"
                "<div class='bs-tag'>AI-Based Staffing Recommendation System · Jungle Brew Café, Parañaque City "
                "· Internal use only</div>", unsafe_allow_html=True)


def _setup_form():
    st.markdown("#### First-time setup")
    code_needed = db.secret("SETUP_CODE")
    if not code_needed and db.backend() == "cloud":
        st.warning("Setup is locked. Add a SETUP_CODE line to the app's Secrets first (see DEPLOY.md), "
                   "then reload this page.")
        return
    st.caption("No accounts exist yet. Create the **manager account** first. The manager then adds staff "
               "accounts in Settings.")
    code = st.text_input("Setup code", type="password", key="setup_code",
                         help="The SETUP_CODE from Secrets. Only the system owner has it.") if code_needed else ""
    name = st.text_input("Manager's full name", key="setup_name")
    email = st.text_input("Work email", placeholder=f"firstname.lastname@{auth.COMPANY_DOMAIN}", key="setup_email")
    if email and auth.email_problem(email):
        st.error(auth.email_problem(email))
    pw = st.text_input("Create a password", type="password", key="setup_pw")
    password_feedback(pw, email)
    pw2 = st.text_input("Type the password again", type="password", key="setup_pw2")
    if st.button("Create manager account", type="primary", width="stretch"):
        if code_needed and not secrets.compare_digest(code.encode(), str(code_needed).encode()):
            db.log(auth.normalize_email(email) or "-", "setup_code_wrong")
            st.error("The setup code is incorrect.")
        elif not name.strip():
            st.error("Please enter the manager's full name.")
        elif auth.email_problem(email):
            st.error(auth.email_problem(email))
        elif not auth.password_ok(pw, email):
            st.error("The password does not meet all the rules above.")
        elif pw != pw2:
            st.error("The two passwords do not match.")
        elif db.has_manager():
            st.error("A manager account already exists. Please log in.")
        else:
            db.create_user(email, name, "manager", pw)
            st.session_state.flash = "Manager account created. You can now log in."
            st.rerun()


def _login_form():
    role_label = st.segmented_control("I am logging in as", ["👩‍🍳 Staff", "🧑‍💼 Manager"], default="👩‍🍳 Staff",
                                      key="login_role", width="stretch")
    role = "manager" if role_label and "Manager" in role_label else "staff"
    with st.form("login_form", border=False):
        email = st.text_input("Work email", placeholder=f"name@{auth.COMPANY_DOMAIN}")
        pw = st.text_input("Password", type="password")
        ok = st.form_submit_button(f"Log in as {role.title()}", type="primary", width="stretch")
    if ok:
        problem = auth.email_problem(email)
        if problem:
            st.error(problem)
        elif not pw:
            st.error("Please enter your password.")
        else:
            user, err = db.login(email, pw, role)
            if err:
                st.error(err)
            else:
                session_cookie.start(user)
                st.rerun()
    st.markdown("<div class='bs-help'>Forgot your password? Ask the manager to reset it in "
                "<b>Settings → Team accounts</b>.</div>"
                f"<div class='bs-secure'>Only <b>@{auth.COMPANY_DOMAIN}</b> accounts · passwords are encrypted · "
                f"account locks after {auth.MAX_FAILED} wrong tries</div>", unsafe_allow_html=True)


def render():
    st.markdown(LOGIN_CSS, unsafe_allow_html=True)
    with st.container(key="login"):
        left, right = st.columns([1.05, 1], gap="small")
        with left:
            st.markdown(f"<div class='bs-photo' role='img' aria-label='Jungle Brew Café storefront at night' "
                        f"style=\"background-image:url('data:image/jpeg;base64,{asset_b64('storefront_hd.jpg')}')\">"
                        f"</div>", unsafe_allow_html=True)
        with right:
            _, mid, _ = st.columns([1, 8, 1])
            with mid:
                _brand_block()
                if db.has_manager():
                    _login_form()
                else:
                    _setup_form()
