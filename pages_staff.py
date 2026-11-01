"""
pages_staff.py - Staff pages: My Shift Today, End-of-Shift Report, Report an Incident, My Reports.
Built for phones: big buttons, few fields, and a clear AI result after every report.
"""
import time

import streamlit as st

import charts
import db
import ui
from ai_helper import tag_feedback
from labels import CLASSES
from pages_manager import base_condition, current_slot_index, get_model, slots_for
from recommender import predict
from timefmt import dt_label, slot_label
from ui import esc


def _ai_result(tags, felt=None, predicted=None):
    st.success("Report saved. Thank you!")
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
           f"<b>{esc(str(tags['summary']))}</b></div></div>")
    ui.ai_card("AI read your report", tags.get("provider"), None, None, big + extra)


def _already_sent(key, text):
    sig = (key, (text or "").strip())
    if st.session_state.get("last_submit") == sig:
        st.warning("You already sent this exact report.")
        return True
    st.session_state.last_submit = sig
    return False


def _predict_level(customers, cashiers, baristas):
    level, _ = predict(get_model(), {**base_condition(), "arr_rate": max(customers, 1) / 60,
                                     "num_cashier": cashiers, "num_barista": baristas})
    return level


def _tag(text):
    t0 = time.perf_counter()
    tags = tag_feedback(text, db.staff_names())
    if tags.get("provider"):
        db.record_timing("Tag a staff report (Gemini/Groq)", time.perf_counter() - t0)
    return tags


def _level_label(level):
    return f"{ui.LEVEL_ICON[level]} {level} – {ui.LEVEL_TEXT[level]}"


# Home
def home():
    user = st.session_state.user
    ui.page_header(f"Hi, {user['full_name'].split()[0]}!", "Your crew plan for today and quick buttons for your reports.")
    plans = db.get_plans(str(db.ph_today()))
    hour = db.ph_now().hour
    now_slot = f"{hour:02d}:00-{hour + 1:02d}:00"

    b1, b2 = st.columns(2)
    actions = [
        (b1, "End-of-shift report", "About 1 minute. Tell us how busy your busiest hour was.", "eos", "Start my report"),
        (b2, "Report an incident", "Something broke, ran out, or went really well? Tell the manager.", "incident",
         "Report now"),
    ]
    for col, title, desc, page, cta in actions:
        with col.container(border=True):
            st.markdown(f"<div style='font-size:1.25rem;font-weight:700'>{title}</div>"
                        f"<div class='bs-kpi-sub' style='margin:4px 0 10px'>{desc}</div>", unsafe_allow_html=True)
            if st.button(cta, key=f"go_{page}", type="primary", width="stretch"):
                st.switch_page(st.session_state.pages[page])
    st.write("")
    st.markdown("#### Today's crew plan")
    if not plans:
        st.info("The manager has not published today's plan yet. Check again later.")
        return
    rows = [{"slot": p["time_slot"], "level": p["predicted_level"], "wait": p["expected_wait"] or 0} for p in plans]
    ui.plain_chart(charts.day_strip(rows))
    ui.legend()
    for p in plans:
        color = ui.LEVEL_COLOR.get(p["predicted_level"], ui.MUTED)
        now = f" · <b style='color:{ui.LIME}'>NOW</b>" if p["time_slot"] == now_slot else ""
        st.markdown(f"<div class='bs-slot' style='border-left-color:{color}'><b>{slot_label(p['time_slot'])}</b>{now}"
                    f"<span style='float:right'>{ui.badge(p['predicted_level'])}</span>"
                    f"{ui.people(p['cashiers'], p['baristas'])}"
                    f"<span class='bs-kpi-sub'>about {p['customers']} customers</span></div>",
                    unsafe_allow_html=True)


# End of shift
def end_of_shift():
    user = st.session_state.user
    ui.page_header("End-of-Shift Report",
                   "Takes about 1 minute. Tell us about the busiest hour of your shift. The AI reads it for the manager.")
    st.caption("Only about shift conditions (workload, equipment, customers, supplies, process). "
               "Please don't name or rate coworkers.")
    d = st.date_input("Date of your shift", value=db.ph_today(), max_value=db.ph_today(), key="eos_date")
    slots = slots_for(d)
    if not slots:
        st.warning("Jungle Brew is closed on Sundays. Pick the date of your shift.")
        return
    with st.form("eos", clear_on_submit=True):
        slot = st.selectbox("Busiest hour of your shift", slots, index=current_slot_index(slots), format_func=slot_label)
        c3, c4, c5 = st.columns(3)
        customers = c3.number_input("About how many customers in that hour?", 0, 150, 20)
        cashiers = c4.number_input("Cashiers on duty", 1, 2, 1)
        baristas = c5.number_input("Baristas on duty", 1, 4, 1)
        level = st.radio("How busy did it feel?", CLASSES, horizontal=True, format_func=_level_label)
        text = st.text_area("Anything to share? (good or bad)", max_chars=1000,
                            placeholder="Example: Rush at 12 PM, only 1 barista, the line reached the door.")
        sent = st.form_submit_button("Send report", type="primary", width="stretch")
    if sent and not _already_sent("eos", f"{d}{slot}{customers}{text}"):
        with st.spinner("The AI is reading your report..."):
            pred = _predict_level(customers, cashiers, baristas)
            tags = _tag(text or f"Shift felt {level}.")
        db.add_report(user_email=user["email"], report_type="end_of_shift", report_date=str(d), time_slot=slot,
                      customers=customers, cashiers=cashiers, baristas=baristas, reported_level=level,
                      predicted_level=pred, text=text, sentiment=tags["sentiment"], category=tags["category"],
                      ai_summary=tags["summary"], ai_provider=tags["provider"])
        _ai_result(tags, felt=level, predicted=pred)


# Incident
def incident():
    user = st.session_state.user
    ui.page_header("Report an Incident", "Something broke, ran out, or went really well? Tell the manager right away.")
    st.caption("Only about shift conditions. Please don't name or rate coworkers.")
    with st.form("inc", clear_on_submit=True):
        text = st.text_area("What happened?", height=130, max_chars=1000,
                            placeholder="Example: Espresso machine stopped working at 3 PM.")
        sent = st.form_submit_button("Send to manager", type="primary", width="stretch")
    if sent:
        if not text.strip():
            st.error("Please describe what happened.")
        elif not _already_sent("inc", text):
            with st.spinner("The AI is reading your report..."):
                tags = _tag(text)
            db.add_report(user_email=user["email"], report_type="incident", report_date=str(db.ph_today()),
                          text=text, sentiment=tags["sentiment"], category=tags["category"],
                          ai_summary=tags["summary"], ai_provider=tags["provider"])
            _ai_result(tags)


# My reports
def my_reports():
    user = st.session_state.user
    ui.page_header("My Reports", "Everything you have sent, the AI's tags, and replies from the manager.")
    if db.count_unseen_replies(user["email"]):
        st.session_state.fresh_replies = {r["id"] for r in db.get_reports(email=user["email"]) if not r["reply_seen"]}
        db.mark_replies_seen(user["email"])
        st.rerun()
    fresh = st.session_state.get("fresh_replies", set())
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
        ui.kpi("Replies", sum(bool(r["reply"]) for r in reps), color=ui.LIME)
    st.caption(f"You can edit or delete a report within {db.EDIT_HOURS} hours, while it is open and "
               "before the manager replies.")
    for r in reps:
        _my_card(r, user, r["id"] in fresh)


def _my_card(r, user, new_reply):
    with st.container(border=True):
        chips = (ui.chip(f"{ui.CAT_ICON.get(r['category'], '')} {r['category']}") +
                 ui.chip("End of shift" if r["report_type"] == "end_of_shift" else "Incident") +
                 ui.chip("Resolved" if r["status"] == "Resolved" else "Open") +
                 ui.chip(dt_label(r["created_at"])) + (ui.chip("Edited") if r["edited_at"] else ""))
        st.markdown(f"{ui.SENT_ICON.get(r['sentiment'], '')} <b>{esc(r['ai_summary'] or r['text'] or '')}</b><br>"
                    f"{chips}", unsafe_allow_html=True)
        if r["reply"]:
            st.markdown(f"<div class='bs-reply'>{ui.chip('New', 'bs-new') if new_reply else ''}"
                        f"<b>Manager's reply</b> · {dt_label(r['replied_at'])}<br>{esc(r['reply'])}</div>",
                        unsafe_allow_html=True)
        if not db.can_staff_change(r):
            return
        with st.expander("Edit or delete"):
            _edit_form(r, user)


def _edit_form(r, user):
    eos = r["report_type"] == "end_of_shift"
    with st.form(f"edit{r['id']}", border=False):
        if eos:
            c1, c2 = st.columns(2)
            customers = c1.number_input("Customers in that hour", 0, 150, int(r["customers"] or 0))
            level = c2.selectbox("How busy did it feel?", CLASSES, index=CLASSES.index(r["reported_level"])
                                 if r["reported_level"] in CLASSES else 0, format_func=_level_label)
        text = st.text_area("Your report", value=r["text"] or "", max_chars=1000)
        save = st.form_submit_button("Save changes", type="primary")
    if save:
        if not eos and not text.strip():
            st.error("The report can't be empty.")
            return
        with st.spinner("The AI is reading your updated report..."):
            fields = {"text": text}
            if eos:
                fields.update(customers=customers, reported_level=level,
                              predicted_level=_predict_level(customers, r["cashiers"] or 1, r["baristas"] or 1))
            tags = _tag(text or f"Shift felt {fields.get('reported_level')}.")
            fields.update(sentiment=tags["sentiment"], category=tags["category"], ai_summary=tags["summary"],
                          ai_provider=tags["provider"])
            ok = db.edit_report(r["id"], user["email"], **fields)
        if ok:
            st.toast("Report updated.")
            st.rerun()
        st.error("This report can no longer be changed (it was replied to, resolved, or is older than 24 hours).")
    if st.button("Delete report", key=f"del{r['id']}", icon=":material/delete:"):
        _delete_dialog(r, user)


@st.dialog("Delete this report?")
def _delete_dialog(r, user):
    st.markdown(f"**{esc(r['ai_summary'] or r['text'] or '')}**", unsafe_allow_html=True)
    st.warning("Are you sure you want to delete this report? Once deleted, it **cannot be recovered**. "
               "If you change your mind, you will need to send a new report.")
    c1, c2 = st.columns(2)
    if c1.button("Cancel", width="stretch"):
        st.rerun()
    if c2.button("Yes, delete", type="primary", icon=":material/delete:", width="stretch"):
        if db.delete_own_report(r["id"], user["email"]):
            st.toast("Report deleted.")
            st.rerun()
        st.error("This report can no longer be deleted (it was replied to, resolved, or is older than 24 hours).")
