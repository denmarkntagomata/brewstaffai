"""
pages_staff.py — Staff pages: My Shift Today, End-of-Shift Report, Report an Incident, My Reports.
Designed for phones: big buttons, few fields, and a clear AI result card after every report.
"""
from datetime import date, datetime

import streamlit as st

import charts
import db
import ui
from ai_helper import tag_feedback
from labels import CLASSES
from pages_manager import base_condition, get_model, slots_for
from recommender import predict


def _ai_result(tags, felt=None, predicted=None):
    """Infographic-style AI result shown right after a staff report is saved."""
    st.success("✅ Report saved. Thank you!")
    extra = ""
    if felt and predicted:
        same = felt == predicted
        extra = (f"<div style='margin-top:12px;display:flex;gap:18px;flex-wrap:wrap;align-items:center'>"
                 f"<div>You felt<br>{ui.badge(felt, '1.05rem')}</div>"
                 f"<div style='font-size:1.4rem'>{'=' if same else '≠'}</div>"
                 f"<div>The AI predicted<br>{ui.badge(predicted, '1.05rem')}</div>"
                 f"<div class='bs-kpi-sub' style='max-width:340px'>"
                 f"{'The AI agrees with you.' if same else 'This helps the team check and improve the AI.'}</div></div>")
    big = (f"<div style='display:flex;gap:26px;flex-wrap:wrap;align-items:center;margin:4px 0 6px'>"
           f"<div style='text-align:center'><div style='font-size:2.6rem'>{ui.SENT_ICON[tags['sentiment']]}</div>"
           f"<div class='bs-kpi-sub'>{tags['sentiment']}</div></div>"
           f"<div style='text-align:center'><div style='font-size:2.6rem'>{ui.CAT_ICON[tags['category']]}</div>"
           f"<div class='bs-kpi-sub'>{tags['category']}</div></div>"
           f"<div style='flex:1;min-width:220px'><div class='bs-kpi-sub'>Summary for the manager</div>"
           f"<b>{tags['summary']}</b></div></div>")
    ui.ai_card("AI read your report", tags.get("provider"), None, None, big + extra)


def _already_sent(key, text):
    sig = (key, (text or "").strip())
    if st.session_state.get("last_submit") == sig:
        st.warning("You already sent this exact report.")
        return True
    st.session_state.last_submit = sig
    return False


# ================================================================== HOME
def home():
    user = st.session_state.user
    ui.page_header("🏠", f"Hi, {user['full_name'].split()[0]}!", "Your crew plan for today and quick buttons for your reports.")
    plans = db.get_plans(str(date.today()))
    now_slot = f"{datetime.now().hour:02d}:00-{datetime.now().hour + 1:02d}:00"

    st.markdown("#### What would you like to do?")
    b1, b2 = st.columns(2)
    actions = [
        (b1, "📝", "End-of-shift report", "About 1 minute. Tell us how busy your busiest hour was.", "eos", "Start my report"),
        (b2, "⚠️", "Report an incident", "Something broke, ran out, or went really well? Tell the manager.", "incident", "Report now"),
    ]
    for col, icon, title, desc, page, cta in actions:
        with col.container(border=True):
            st.markdown(f"<div style='font-size:2.2rem;line-height:1'>{icon}</div>"
                        f"<div style='font-size:1.25rem;font-weight:700;margin-top:6px'>{title}</div>"
                        f"<div class='bs-kpi-sub' style='margin:4px 0 10px'>{desc}</div>", unsafe_allow_html=True)
            if st.button(cta, key=f"go_{page}", type="primary", width="stretch"):
                st.switch_page(st.session_state.pages[page])
    st.write("")
    st.markdown("#### 📅 Today's crew plan (made by the AI, published by the manager)")
    if not plans:
        st.info("The manager has not published today's plan yet. Check again later.")
        return
    rows = [{"slot": p["time_slot"], "level": p["predicted_level"], "wait": p["expected_wait"] or 0} for p in plans]
    st.plotly_chart(charts.day_strip(rows), width="stretch", config={"displayModeBar": False})
    ui.legend()
    for p in plans:
        color = ui.LEVEL_COLOR.get(p["predicted_level"], ui.MUTED)
        now = " · <b style='color:#A6CE39'>NOW</b>" if p["time_slot"] == now_slot else ""
        st.markdown(f"<div class='bs-slot' style='border-left-color:{color}'><b>{p['time_slot']}</b>{now}"
                    f"<span style='float:right'>{ui.badge(p['predicted_level'])}</span><br>"
                    f"<span style='font-size:1.4rem'>{'🧾' * p['cashiers']} {'☕' * p['baristas']}</span>"
                    f"<span class='bs-kpi-sub'> {p['cashiers']} cashier(s), {p['baristas']} barista(s) · "
                    f"about {p['customers']} customers</span></div>", unsafe_allow_html=True)


# ================================================================== END OF SHIFT
def end_of_shift():
    user = st.session_state.user
    ui.page_header("📝", "End-of-Shift Report",
                   "Takes about 1 minute. Tell us about the busiest hour of your shift. The AI reads it for the manager.")
    st.caption("Only about shift conditions (workload, equipment, customers, supplies, process). "
               "Please don't name or rate coworkers.")
    with st.form("eos", clear_on_submit=True):
        c1, c2 = st.columns(2)
        d = c1.date_input("Date of your shift", value=date.today())
        slots = slots_for(d) or ["(closed)"]
        slot = c2.selectbox("Busiest hour of your shift", slots)
        c3, c4, c5 = st.columns(3)
        customers = c3.number_input("About how many customers in that hour?", 0, 150, 20)
        cashiers = c4.number_input("Cashiers on duty 🧾", 1, 2, 1)
        baristas = c5.number_input("Baristas on duty ☕", 1, 4, 1)
        level = st.radio("How busy did it feel?", CLASSES, horizontal=True,
                         format_func=lambda l: f"{ui.LEVEL_ICON[l]} {l} – {ui.LEVEL_TEXT[l]}")
        text = st.text_area("Anything to share? (good or bad)",
                            placeholder="Example: Rush at 12 PM, only 1 barista, the line reached the door.")
        sent = st.form_submit_button("Send report", type="primary", width="stretch")
    if sent and not _already_sent("eos", f"{d}{slot}{customers}{text}"):
        with st.spinner("The AI is reading your report..."):
            pred, _ = predict(get_model(), {**base_condition(), "arr_rate": max(customers, 1) / 60,
                                            "num_cashier": cashiers, "num_barista": baristas})
            tags = tag_feedback(text or f"Shift felt {level}.", db.staff_names())
        db.add_report(user_email=user["email"], report_type="end_of_shift", report_date=str(d), time_slot=slot,
                      customers=customers, cashiers=cashiers, baristas=baristas, reported_level=level,
                      predicted_level=pred, text=text, sentiment=tags["sentiment"], category=tags["category"],
                      ai_summary=tags["summary"], ai_provider=tags["provider"])
        _ai_result(tags, felt=level, predicted=pred)


# ================================================================== INCIDENT
def incident():
    user = st.session_state.user
    ui.page_header("⚠️", "Report an Incident",
                   "Something broke, ran out, or went really well? Tell the manager right away.")
    st.caption("Only about shift conditions. Please don't name or rate coworkers.")
    with st.form("inc", clear_on_submit=True):
        text = st.text_area("What happened?", height=130,
                            placeholder="Example: Espresso machine stopped working at 3 PM.")
        sent = st.form_submit_button("Send to manager", type="primary", width="stretch")
    if sent:
        if not text.strip():
            st.error("Please describe what happened.")
        elif not _already_sent("inc", text):
            with st.spinner("The AI is reading your report..."):
                tags = tag_feedback(text, db.staff_names())
            db.add_report(user_email=user["email"], report_type="incident", report_date=str(date.today()),
                          text=text, sentiment=tags["sentiment"], category=tags["category"],
                          ai_summary=tags["summary"], ai_provider=tags["provider"])
            _ai_result(tags)


# ================================================================== MY REPORTS
def my_reports():
    user = st.session_state.user
    ui.page_header("📄", "My Reports", "Everything you have sent, with the AI's tags and whether the manager resolved it.")
    reps = db.get_reports(email=user["email"])
    if not reps:
        st.info("You have not sent any reports yet.")
        return
    a, b, c = st.columns(3)
    with a:
        ui.kpi("Sent", len(reps))
    with b:
        ui.kpi("Resolved by manager", sum(r["status"] == "Resolved" for r in reps), color=ui.LEVEL_COLOR["Okay"])
    with c:
        ui.kpi("Still open", sum(r["status"] == "Open" for r in reps), color=ui.AMBER)
    st.write("")
    for r in reps:
        st.markdown(f"<div class='bs-card' style='margin-bottom:8px'>{ui.SENT_ICON.get(r['sentiment'], '')} "
                    f"<b>{r['ai_summary'] or r['text']}</b><br>"
                    f"{ui.chip(ui.CAT_ICON.get(r['category'], '') + ' ' + r['category'])}"
                    f"{ui.chip('📝 End of shift' if r['report_type'] == 'end_of_shift' else '⚠️ Incident')}"
                    f"{ui.chip('🟢 Resolved' if r['status'] == 'Resolved' else '🟠 Open')}"
                    f"{ui.chip('🕒 ' + r['created_at'][:16])}"
                    f"<div class='bs-kpi-sub' style='margin-top:4px'>AI tags by {r['ai_provider'] or 'offline fallback'}"
                    f"</div></div>", unsafe_allow_html=True)
