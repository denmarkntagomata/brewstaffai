"""
session_cookie.py - keeps a person logged in after a page refresh.

On login a random token is saved in a browser cookie and only its SHA-256 hash is saved in the
database. On refresh the token is read back and checked (exists, used within the last 30 minutes,
account still active). Logging out deletes the token from the database, so an old cookie stops working.
If the browser blocks cookies, the app still works; a refresh just asks for the password again.
"""
from datetime import datetime

import streamlit as st

import db

COOKIE = "bs_session"
MAX_AGE = 12 * 60 * 60     # the browser forgets the cookie after 12 hours; the 30-minute idle rule still applies


def _js(value, max_age):
    st.html(f"""<script>
document.cookie = "{COOKIE}={value}; path=/; max-age={max_age}; SameSite=Strict"
  + (location.protocol === "https:" ? "; Secure" : "");
</script>""", unsafe_allow_javascript=True)


def start(user):
    token = db.start_session(user["email"])
    st.session_state.user = user
    st.session_state.token = token
    st.session_state.cookie_pending = token
    st.session_state.last_active = datetime.now()
    st.session_state.touched = datetime.now()


def restore():
    """Logs the person back in from the cookie. Returns the user or None."""
    try:
        token = st.context.cookies.get(COOKIE)
    except Exception:
        return None
    user = db.session_user(token)
    if not user:
        return None
    st.session_state.user = user
    st.session_state.token = token
    st.session_state.last_active = datetime.now()
    st.session_state.touched = datetime.now()
    db.touch_session(token)
    return user


def keep_alive():
    """Called on every page load while logged in: writes pending cookies and refreshes the idle timer."""
    if st.session_state.get("cookie_pending"):
        _js(st.session_state.pop("cookie_pending"), MAX_AGE)
    token = st.session_state.get("token")
    last = st.session_state.get("touched")
    if token and (not last or (datetime.now() - last).total_seconds() > 60):
        db.touch_session(token)
        st.session_state.touched = datetime.now()


def end(msg=None):
    db.end_session(st.session_state.get("token"))
    st.session_state.clear()
    st.session_state.clear_cookie = True
    if msg:
        st.session_state.flash = msg


def clear_if_needed():
    if st.session_state.pop("clear_cookie", False):
        _js("", 0)

