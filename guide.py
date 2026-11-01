"""
guide.py - built-in User Guide (manager and staff) and the simple "How the AI works" for staff.
Visual cards and short steps.
"""
import re

import streamlit as st

import ui

SUPPORT_NAME = "Denmark Nercua Tagomata"
SUPPORT_EMAIL = "denmarkntagomata.pup@gmail.com"

CSS = f"""
<style>
.g-grid {{ display:grid; grid-template-columns:repeat(auto-fit, minmax(190px, 1fr)); gap:12px; margin:6px 0 14px; }}
.g-card {{ background:{ui.CARD}; border:1px solid {ui.BORDER}; border-radius:14px; padding:14px 16px; }}
.g-card .ic {{ font-size:1.6rem; line-height:1.1; }}
.g-card b {{ display:block; margin:6px 0 2px; font-size:1.02rem; }}
.g-card span {{ color:{ui.MUTED}; font-size:.88rem; }}
.g-flow {{ display:flex; flex-wrap:wrap; align-items:stretch; gap:8px; margin:6px 0 14px; }}
.g-flow .s {{ flex:1 1 150px; background:{ui.CARD}; border:1px solid {ui.BORDER}; border-radius:14px; padding:12px 14px; position:relative; }}
.g-flow .n {{ width:26px; height:26px; border-radius:50%; background:{ui.GREEN}; color:#fff; font-weight:800; font-size:.85rem;
  display:flex; align-items:center; justify-content:center; margin-bottom:6px; }}
.g-flow .s b {{ display:block; font-size:.98rem; }}
.g-flow .s span {{ color:{ui.MUTED}; font-size:.85rem; }}
.g-flow .ar {{ align-self:center; color:{ui.LIME}; font-size:1.3rem; font-weight:800; }}
.g-lv {{ display:grid; grid-template-columns:repeat(auto-fit, minmax(170px, 1fr)); gap:10px; margin:6px 0 14px; }}
.g-lv div {{ border-radius:12px; padding:12px 14px; font-size:.9rem; }}
.g-tip {{ border-left:4px solid {ui.LIME}; background:rgba(166,206,57,.08); border-radius:8px; padding:9px 12px; margin:8px 0 12px; font-size:.92rem; }}
.g-warn {{ border-left:4px solid {ui.AMBER}; background:rgba(240,167,58,.10); border-radius:8px; padding:9px 12px; margin:8px 0 12px; font-size:.92rem; }}
.g-help {{ border:1.5px solid {ui.LIME}55; background:linear-gradient(135deg, rgba(166,206,57,.10), rgba(46,125,79,.10));
  border-radius:16px; padding:16px 18px; margin:10px 0; }}
.g-help b {{ font-size:1.05rem; }}
.g-crew {{ display:inline-block; width:14px; height:14px; border-radius:50%; vertical-align:middle; margin:0 2px; }}
</style>"""


def _b(text):
    return re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)


def _css():
    st.markdown(CSS, unsafe_allow_html=True)


def cards(items):
    st.markdown('<div class="g-grid">' + "".join(
        f'<div class="g-card"><div class="ic">{ic}</div><b>{t}</b><span>{_b(d)}</span></div>' for ic, t, d in items) + "</div>",
        unsafe_allow_html=True)


def flow(items):
    parts = []
    for i, (t, d) in enumerate(items, 1):
        parts.append(f'<div class="s"><div class="n">{i}</div><b>{t}</b><span>{_b(d)}</span></div>')
        if i < len(items):
            parts.append('<div class="ar">›</div>')
    st.markdown('<div class="g-flow">' + "".join(parts) + "</div>", unsafe_allow_html=True)


def tip(text, warn=False):
    st.markdown(f'<div class="{"g-warn" if warn else "g-tip"}">{_b(text)}</div>', unsafe_allow_html=True)


def levels():
    c = ui.LEVEL_COLOR
    st.markdown(
        '<div class="g-lv">'
        f'<div style="background:{c["Okay"]}22;border:1px solid {c["Okay"]}"><b style="color:{c["Okay"]}">✅ Okay</b><br>Short waits, 7 minutes or less</div>'
        f'<div style="background:{c["Congested"]}22;border:1px solid {c["Congested"]}"><b style="color:{c["Congested"]}">⚠️ Congested</b><br>Long waits, 7–15 minutes</div>'
        f'<div style="background:{c["Overloaded"]}22;border:1px solid {c["Overloaded"]}"><b style="color:{c["Overloaded"]}">⛔ Overloaded</b><br>Very long waits, over 15 minutes</div>'
        "</div>", unsafe_allow_html=True)


def crew_legend():
    st.markdown(f'<div class="g-tip"><span class="g-crew" style="background:{ui.CASHIER_COLOR}"></span> amber dot = 1 cashier '
                f'&nbsp;·&nbsp; <span class="g-crew" style="background:{ui.BARISTA_COLOR}"></span> green dot = 1 barista '
                f'&nbsp;·&nbsp; Example: <span class="g-crew" style="background:{ui.CASHIER_COLOR}"></span>'
                f'<span class="g-crew" style="background:{ui.BARISTA_COLOR}"></span><span class="g-crew" style="background:{ui.BARISTA_COLOR}"></span>'
                ' = 1 cashier and 2 baristas</div>', unsafe_allow_html=True)


def faq(items):
    for q, a in items:
        with st.expander(q):
            st.markdown(a.replace("<b>", "**").replace("</b>", "**"))


def glossary(rows):
    st.markdown("| Term | Meaning |\n|---|---|\n" + "\n".join(f"| **{t}** | {m} |" for t, m in rows))


def help_box():
    st.markdown(f'<div class="g-help"><b>Need help?</b><br>Contact the BrewStaffAI team leader, <b>{SUPPORT_NAME}</b>, at '
                f'<b>{SUPPORT_EMAIL}</b>, or ask the café manager.</div>', unsafe_allow_html=True)


COMMON_TROUBLE = [
    ("“Incorrect email, password, or role”", "Check that **Staff** or **Manager** at the top matches your account, then retype your password (tap the eye icon to see it)."),
    ("“Too many wrong attempts… locked”", "Wait 5 minutes and try again, or ask the manager to reset your password."),
    ("I forgot my password", "Ask the manager: **Settings → Team accounts → Reset password**. You'll get a new temporary password."),
    ("I was logged out", "This happens after 30 minutes without activity, or after a password reset. Just log in again."),
    ("“Yes, get this app back up!”", "The free server was sleeping. Tap it and wait about 30 seconds."),
    ("“Can't reach the database right now”", "Check your internet, wait a few seconds, then tap **Try again**."),
    ("The AI box says “Basic summary”", "The AI service didn't answer in time. Your work is still saved; nothing else to do."),
]

COMMON_TERMS = [
    ("Crew", "Number of cashiers and baristas working in one hour."),
    ("Okay / Congested / Overloaded", "How long customers wait: 7 min or less / 7–15 min / over 15 min."),
    ("Published plan", "The crew plan the manager sends to staff for the day."),
    ("End-of-shift report", "Short form about the busiest hour of your shift."),
    ("Incident report", "Report about something unusual: broken, ran out, or went really well."),
    ("AI tag", "The feeling (Positive / Neutral / Negative) and topic the AI gives a report."),
    ("Temporary password", "One-time password from the manager. You set your own at first login."),
]


# ------------------------------------------------------------------ manager
def manager_guide():
    _css()
    st.caption("Everything you need to use BrewStaffAI as a manager. Pick a topic below.")
    topic = st.segmented_control(
        "Topic", ["Daily routine", "Staffing Planner", "Staff Reports", "Pilot Results", "Settings", "Colors & AI",
                  "Troubleshooting", "Glossary & help"], default="Daily routine", key="mg_topic",
        label_visibility="collapsed") or "Daily routine"

    if topic == "Daily routine":
        st.markdown("#### Your 5–10 minute routine")
        flow([("Log in", "Choose **Manager**, then your work email and password."),
              ("Plan the day", "**Staffing Planner → Generate AI plan**."),
              ("Check and adjust", "Look at the colors. Change any hour if needed."),
              ("Publish", "Staff see it on **My Shift Today**."),
              ("Read reports", "**Staff Reports**: reply, resolve, or archive.")])
        st.markdown("#### What each page is for")
        cards([("🏠", "Dashboard", "Today's plan, open issues, latest reports. Edit or delete today's plan here."),
               ("📅", "Staffing Planner", "Let the AI plan every hour, or test one hour."),
               ("📥", "Staff Reports", "What staff reported, with AI tags and a weekly summary."),
               ("📈", "Pilot Results", "Evidence for the paper: AI vs. what staff felt."),
               ("🧠", "How the AI Works", "Accuracy and charts for the panel, plus this guide."),
               ("⚙️", "Settings", "Accounts, café numbers, AI status, backup, activity log.")])
        tip("The sidebar badge <b>Staff Reports (2)</b> means 2 new reports. <b>Refresh</b> (top right) loads the latest data "
            "without logging you out.")

    elif topic == "Staffing Planner":
        st.markdown("#### Plan the day")
        flow([("Pick the day", "Sundays are closed; Saturdays start at 11:00 AM."),
              ("Customers (optional)", "Open <i>Expected customers per hour</i> for a promo or slow day."),
              ("Generate", "Press <b>Generate AI plan for the day</b>."),
              ("Adjust (optional)", "Open the hour-by-hour table, change crew, press <b>Check my changes</b>."),
              ("Publish", "Press <b>Publish this plan to staff</b>.")])
        tip("The AI recommends; <b>you decide</b>. Your changes are re-checked by the AI and saved next to the AI's original crew.")
        st.markdown("#### Test a specific hour")
        cards([("🕐", "When to use", "A promo, a big order, or someone absent."),
               ("🎯", "What you get", "The recommended crew, expected wait gauge, and every crew option (★ best)."),
               ("📋", "Details for the panel", "Your crew vs. the AI's, confidence, and why."),
               ("📢", "Publish this hour", "Updates only that hour in today's plan.")])
        st.markdown("#### Change today's plan later")
        cards([("✏️", "Edit plan", "Dashboard → <b>Edit plan</b> → change customers or crew → <b>Save changes</b>."),
               ("🗑️", "Delete plan", "Dashboard → <b>Delete plan</b> → confirm. Make a new one anytime.")])

    elif topic == "Staff Reports":
        st.markdown("#### Handle a report")
        flow([("New report", "A green <b>New</b> chip and a sidebar badge."),
              ("Read", "Open <i>Original text and reply</i> to see the full text."),
              ("Reply", "Write a message → <b>Send reply</b>. Staff see it in My Reports."),
              ("Resolve", "Press <b>Resolve</b> when it's handled. <b>Reopen</b> if needed.")])
        st.markdown("#### Archive")
        cards([("📦", "Archive a report", "Press <b>Archive</b> on the card and give a reason (e.g., duplicate, test)."),
               ("🗂️", "Find archived reports", "Press <b>Archive (n)</b> under Refresh at the top right."),
               ("↩️", "Restore or delete", "<b>Restore</b> brings it back. <b>Delete now</b> removes it for good (asks first)."),
               ("⏳", "Auto-delete", "Archived reports are deleted automatically 30 days after archiving.")])
        st.markdown("#### Summaries and exports")
        cards([("✨", "AI weekly summary", "Top issues, what went well, suggested actions."),
               ("⬇️", "Download CSV", "Summary CSV and full reports CSV for Excel."),
               ("🔎", "Filters", "Status, period, feeling, and topic.")])

    elif topic == "Pilot Results":
        st.markdown("#### Tab 1 · AI vs. staff")
        flow([("Staff report", "Staff choose how busy the hour <i>felt</i>."),
              ("AI prediction", "The system saved what the AI <i>predicted</i>."),
              ("Compare", "Agreement % per day, plus a staff-vs-AI grid."),
              ("Export", "Download the CSVs for Chapter 4.")])
        st.markdown("#### Tab 2 · Check AI tags (team only)")
        flow([("Read", "One report at a time; the AI's answer is hidden."),
              ("Label", "Choose the feeling and topic you think is right."),
              ("Repeat", "Do 50 reports."),
              ("Results", "Gauges show how often the AI matched (target 80%).")])
        tip("Higher agreement means the AI's predictions match real shifts at Jungle Brew.")

    elif topic == "Settings":
        cards([("👤", "My account", "Your profile, privacy notice, change password."),
               ("👥", "Team accounts", "Add a person (shows a one-time temporary password), reset password, deactivate."),
               ("☕", "Café defaults", "Customers per hour, service times, most staff per hour. Keep these accurate."),
               ("🤖", "AI services", "Shows if Gemini and Groq are connected. Press <b>Test AI connection</b>."),
               ("🗄️", "Data & backup", "Cloud · Online status and the full backup ZIP. Download daily during the pilot."),
               ("📜", "Activity log", "Who did what, and when.")])
        tip("Give temporary passwords <b>privately</b>. Never post them in a group chat.", warn=True)

    elif topic == "Colors & AI":
        st.markdown("#### What the colors mean")
        levels()
        crew_legend()
        st.markdown("#### How a recommendation is made")
        flow([("Expected customers", "From staff reports or café defaults."),
              ("AI predicts", "The Decision Tree checks every crew option."),
              ("Smallest Okay crew", "It picks the smallest crew with short waits."),
              ("Double-check", "The queue simulator confirms the wait (10 runs)."),
              ("Explain", "Gemini writes the summary in plain words.")])
        cards([("🎯", "AI confidence", "How sure the AI is. Lower means the hour is near a limit."),
               ("⏱️", "Expected wait", "Average minutes in line, from the simulator."),
               ("💬", "“Generated by Gemini / Groq”", "Written by the AI service (Groq is the backup)."),
               ("🧩", "“Basic summary”", "The AI service didn't answer; plans still work.")])

    elif topic == "Troubleshooting":
        faq(COMMON_TROUBLE + [
            ("The planner shows a warning about some hours", "Even with all available staff, those hours can't reach short waits. Consider extra help or a simpler menu, or raise <b>Most counter staff</b> in Café defaults."),
            ("“Setup is locked”", "The SETUP_CODE is missing in the app's Secrets. Only the system owner can fix this."),
            ("The plan looks wrong", "Check <b>Settings → Café defaults</b>. The AI uses those numbers."),
        ])

    else:
        st.markdown("#### Glossary")
        glossary(COMMON_TERMS + [("Archive", "Hide a report with a reason; deleted after 30 days."),
                                 ("Agreement %", "Share of reports where the AI predicted the same level staff felt.")])
        help_box()


# ------------------------------------------------------------------ staff
def staff_guide():
    _css()
    st.caption("How to use BrewStaffAI as staff. Pick a topic below.")
    topic = st.segmented_control(
        "Topic", ["Get started", "Send a report", "Report an incident", "My Reports", "Troubleshooting", "Glossary & help"],
        default="Get started", key="st_topic", label_visibility="collapsed") or "Get started"

    if topic == "Get started":
        flow([("Open the link", "https://brewstaffai.streamlit.app"),
              ("Log in as Staff", "Your @junglebrewpq.com email and password."),
              ("First time only", "Set your own password, then read the privacy notice."),
              ("Home", "See today's crew plan and two big buttons.")])
        cards([("🏠", "My Shift Today", "Today's plan. <b>NOW</b> marks the current hour."),
               ("📝", "End-of-Shift Report", "About 1 minute, after your shift."),
               ("⚠️", "Report an Incident", "Something broke, ran out, or went well."),
               ("📄", "My Reports", "Your reports, AI tags, and manager replies.")])
        tip("On a phone, tap <b>»</b> at the top left to open the menu. Add the app to your home screen for quick access.")

    elif topic == "Send a report":
        flow([("Date and hour", "Pick your shift date and busiest hour."),
              ("Customers and crew", "Your best guess of customers, cashiers, baristas."),
              ("How busy?", "Okay, Congested, or Overloaded. Be honest."),
              ("Comment (optional)", "What went well or wrong."),
              ("Send", "See the AI result right away.")])
        levels()
        tip("Write about shift conditions only (workload, equipment, customers, supplies, process). Don't name or rate coworkers.",
            warn=True)

    elif topic == "Report an incident":
        flow([("Open", "<b>Report an Incident</b> from the menu or home."),
              ("Describe", "One or two sentences. Example: <i>Espresso machine stopped at 3:00 PM.</i>"),
              ("Send", "The manager sees it as <b>New</b>.")])
        tip("Good news counts too! Example: <i>Great teamwork during the lunch rush.</i>")

    elif topic == "My Reports":
        cards([("💬", "Manager replies", "Shown in a green box. The menu says <b>My Reports (1)</b> when there's a new reply."),
               ("✏️", "Edit", "Within 24 hours, while the report is open and has no reply yet."),
               ("🗑️", "Delete", "Same time limit. A pop-up asks you to confirm; deleted reports can't be recovered.")])

    elif topic == "Troubleshooting":
        faq(COMMON_TROUBLE + [
            ("“Edit or delete” is missing", "The report is older than 24 hours, already resolved, or the manager replied. Ask the manager."),
            ("“You already sent this exact report”", "You tapped Send twice. It was saved once; nothing to do."),
            ("No crew plan today", "The manager hasn't published it yet. Check again later."),
        ])

    else:
        st.markdown("#### Glossary")
        glossary(COMMON_TERMS)
        help_box()


def staff_ai_simple():
    _css()
    st.caption("A quick, simple look at what the AI does in BrewStaffAI.")
    st.markdown("#### From your report to a better plan")
    flow([("You report", "You send how busy your shift felt."),
          ("AI reads it", "It tags the feeling and topic and writes a short summary."),
          ("Manager acts", "The manager sees it, replies, and fixes problems."),
          ("Better plans", "The AI uses this to plan the right crew each hour.")])
    st.markdown("#### What the colors mean")
    levels()
    crew_legend()
    cards([("✅", "The AI helps", "Predicts busy hours and suggests the smallest crew that keeps waits short."),
           ("🧑‍💼", "The manager decides", "The AI only recommends. The manager can change any hour."),
           ("🔒", "Your privacy", "Names are removed before text goes to the AI. Taking part is voluntary."),
           ("🤝", "Your honesty helps", "If you felt busier than the AI predicted, say so. It helps the team improve the AI.")])
    help_box()
