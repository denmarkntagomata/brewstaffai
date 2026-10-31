"""
privacy.py - privacy notice shown once to every user (Data Privacy Act of 2012, RA 10173).
Change NOTICE_VERSION when the text changes so everyone is asked to read it again.
"""
import streamlit as st

import db
import ui

NOTICE_VERSION = "1.0"
CONTACT = "the BrewStaffAI research team leader through the café manager"
KEEP_UNTIL = "the end of the study (December 2026)"

NOTICE = f"""
##### Who is responsible for your data
BrewStaffAI is a student research system made by IT students of PUP Parañaque for Jungle Brew Café.
The research team and the café manager handle your data for the study.

##### What we collect
- Your name, work email, and role (manager or staff)
- Your shift reports: busiest hour, number of customers, crew, how busy it felt, and your comments
- Login activity (when you logged in, and changes you made), for security

##### What we do NOT collect
Your home address, phone number, government IDs, photos, or anything about customers.

##### Why we collect it
- To recommend how many cashiers and baristas are needed each hour
- To let the manager see and respond to shift problems
- To check how accurate the AI is, for our IT Elective research paper

##### Who can see it
- The café manager can see reports with your name, so they can reply and fix problems.
- The research team sees the data for the study. In the paper, results are shown as totals and percentages, without names.

##### AI services
Report text is sent to Google Gemini (or Groq as backup) so the AI can tag and summarize it.
These services may process data outside the Philippines. **Staff names are removed before any text is sent.**
Please don't write names, phone numbers, or other personal details in your reports.

##### How long we keep it
Reports stay in the system until {KEEP_UNTIL}, then they are deleted or made anonymous.
Archived reports are deleted automatically after 30 days.

##### How we protect it
Company accounts only, encrypted passwords, automatic logout, an encrypted cloud database, and an activity log.

##### Your rights under the Data Privacy Act
You have the right to be informed, to access your data, to correct it, to object, to have it deleted,
and to file a complaint with the National Privacy Commission (privacy.gov.ph).
You can edit or delete your own reports within 24 hours in My Reports. For anything else, contact {CONTACT}.

##### Taking part is voluntary
Your answers will not affect your work evaluation. If you do not agree, tell the manager and you will not be asked
to use the system.
"""


def needs_notice(user):
    return user.get("privacy_version") != NOTICE_VERSION


def show_notice_text():
    st.markdown(NOTICE)


def consent_page(user):
    ui.page_header("Privacy notice", "Please read this once before using BrewStaffAI.")
    _, mid, _ = st.columns([1, 6, 1])
    with mid:
        with st.container(border=True, height=460):
            show_notice_text()
        agree = st.checkbox("I have read and understood this notice, and I agree to the use of my data as described.",
                            key="privacy_ok")
        c1, c2 = st.columns(2)
        if c1.button("Continue", type="primary", disabled=not agree, width="stretch"):
            db.accept_privacy(user["email"], NOTICE_VERSION)
            st.session_state.user = {**st.session_state.user, "privacy_version": NOTICE_VERSION}
            st.rerun()
        if c2.button("I do not agree", width="stretch"):
            db.log(user["email"], "privacy_declined", f"notice v{NOTICE_VERSION}")
            return "declined"
    return None
