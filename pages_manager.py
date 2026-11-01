"""
pages_manager.py - Manager pages: Dashboard, Staffing Planner, Staff Reports, How the AI Works.
"""
import json
import os
import time

import pandas as pd
import streamlit as st

import charts
import db
import ui
from ai_helper import CATEGORIES, explain_day, explain_hour, weekly_summary
from recommender import load_model, plan_day, predict, recommend, sim_check
from timefmt import dt_label, slot_label
from ui import esc

HERE = os.path.dirname(os.path.abspath(__file__))


@st.cache_resource
def get_model():
    return load_model()


def slots_for(d):
    wd = d.weekday()
    if wd == 6:
        return []
    return [f"{h:02d}:00-{h + 1:02d}:00" for h in range(11 if wd == 5 else 8, 22)]


def current_slot_index(slots):
    """Index of the hour happening now (or the nearest open hour)."""
    if not slots:
        return 0
    hour = db.ph_now().hour
    starts = [int(s[:2]) for s in slots]
    if hour in starts:
        return starts.index(hour)
    return 0 if hour < starts[0] else len(slots) - 1


def expected_customers(d, slots):
    prof = db.get_setting("hourly_profile")
    out, src = {}, {}
    for s in slots:
        avg, n = db.avg_reported_customers(d.strftime("%A"), s)
        out[s] = int(round(avg)) if avg else int(prof.get(str(int(s[:2])), 15))
        src[s] = f"staff reports ({n})" if avg else "café defaults"
    return out, src


def base_condition():
    svc = db.get_setting("service_times")
    return dict(p_simple=svc["p_simple"], cashier_mean=svc["cashier"],
                simple_prep=svc["simple"], complex_prep=svc["complex"])


def max_staff():
    return int(db.get_setting("max_counter_staff"))


def staff_lookup():
    return {u["email"]: u["full_name"] for u in db.list_users()}


# Dashboard
def dashboard():
    user = st.session_state.user
    hour = db.ph_now().hour
    greet = "Good morning" if hour < 12 else "Good afternoon" if hour < 18 else "Good evening"
    ui.page_header(f"{greet}, {user['full_name'].split()[0]}!",
                   "Today at a glance. Start with the Staffing Planner, then check what your staff reported.")
    plans = db.get_plans(str(db.ph_today()))
    reps7 = db.get_reports(days=7)
    eos = [r for r in db.get_reports() if r["report_type"] == "end_of_shift" and r["predicted_level"]]
    match = sum(r["predicted_level"] == r["reported_level"] for r in eos)
    open_n = sum(r["status"] == "Open" for r in reps7)

    a, b, c, d = st.columns(4)
    with a:
        ui.kpi("Today's plan", f"{len(plans)} hrs" if plans else "Not yet", "hours planned by the AI",
               color=ui.LIME if plans else ui.AMBER)
    with b:
        ui.kpi("Open issues", open_n, "from staff, last 7 days", color=ui.RED if open_n else ui.TEXT)
    with c:
        ui.kpi("Staff reports", len(reps7), "last 7 days")
    with d:
        ui.kpi("AI vs. real shifts", f"{match / len(eos):.0%}" if eos else "—",
               f"agreement on {len(eos)} end-of-shift report(s)")
    st.write("")

    left, right = st.columns([1.6, 1], gap="large")
    with left:
        st.markdown("#### Today's staffing plan")
        if plans:
            rows = [{"slot": p["time_slot"], "level": p["predicted_level"], "wait": p["expected_wait"] or 0,
                     "customers": p["customers"], "cashiers": p["cashiers"], "baristas": p["baristas"]} for p in plans]
            ui.plain_chart(charts.day_strip(rows))
            ui.legend()
            ui.plain_chart(charts.day_chart(rows))
            c1, c2, _ = st.columns([1, 1, 2])
            editing = st.session_state.get("edit_plan", False)
            if c1.button("Close editor" if editing else "Edit plan", icon=":material/edit:", key="plan_edit",
                         width="stretch"):
                st.session_state.edit_plan = not editing
                st.rerun()
            if c2.button("Delete plan", icon=":material/delete:", key="plan_delete", width="stretch"):
                _delete_plan_dialog(str(db.ph_today()))
        else:
            st.info("No plan for today yet. The AI can build one in a few seconds.")
            st.page_link(st.session_state.pages["planner"], label="Open the Staffing Planner",
                         icon=":material/arrow_forward:")
    with right:
        st.markdown("#### Latest staff reports")
        if not reps7:
            st.caption("No reports in the last 7 days.")
        for r in reps7[:5]:
            st.markdown(f"<div class='bs-card' style='margin-bottom:8px;padding:12px 14px'>"
                        f"{ui.SENT_ICON.get(r['sentiment'], '')} <b>{esc(r['ai_summary'] or r['text'] or '')}</b><br>"
                        f"{ui.chip(ui.CAT_ICON.get(r['category'], '') + ' ' + (r['category'] or ''))}"
                        f"{ui.chip(r['status'])}<span style='color:{ui.MUTED};font-size:.8rem'> {dt_label(r['created_at'])}"
                        f"</span></div>", unsafe_allow_html=True)
    if plans and st.session_state.get("edit_plan"):
        _edit_published_plan(plans, str(db.ph_today()))


def _edit_published_plan(plans, plan_date):
    with st.container(border=True):
        st.markdown("**Edit today's published plan**")
        st.caption("Change the customers or crew for any hour, then press Save changes. Changed hours are re-checked "
                   "by the AI, and staff see the update right away.")
        t = pd.DataFrame({
            "Hour": [slot_label(p["time_slot"]) for p in plans],
            "Customers": [p["customers"] for p in plans],
            "Cashiers": [p["cashiers"] for p in plans],
            "Baristas": [p["baristas"] for p in plans],
            "Level": [f"{ui.LEVEL_ICON.get(p['predicted_level'], '')} {p['predicted_level']}" for p in plans],
            "Expected wait (min)": [p["expected_wait"] for p in plans],
        })
        edited = st.data_editor(
            t, hide_index=True, width="stretch", key=f"pub_edit_{plan_date}",
            disabled=["Hour", "Level", "Expected wait (min)"],
            column_config={"Customers": st.column_config.NumberColumn(min_value=1, max_value=150, step=1),
                           "Cashiers": st.column_config.NumberColumn(min_value=1, max_value=2, step=1),
                           "Baristas": st.column_config.NumberColumn(min_value=1, max_value=4, step=1)})
        if st.button("Save changes", type="primary", icon=":material/save:", key="pub_save"):
            model, base = get_model(), base_condition()
            rows, changed = [], 0
            with st.spinner("Re-checking the hours you changed..."):
                for p, cu, ca, ba in zip(plans, edited.Customers, edited.Cashiers, edited.Baristas):
                    cu = int(cu) if pd.notna(cu) else p["customers"]
                    ca = int(ca) if pd.notna(ca) else p["cashiers"]
                    ba = int(ba) if pd.notna(ba) else p["baristas"]
                    row = {"slot": p["time_slot"], "customers": cu, "cashiers": ca, "baristas": ba,
                           "level": p["predicted_level"], "wait": p["expected_wait"] or 0,
                           "insight": p["ai_insight"] or "", "ai_cashiers": p["ai_cashiers"] or p["cashiers"],
                           "ai_baristas": p["ai_baristas"] or p["baristas"]}
                    if (cu, ca, ba) != (p["customers"], p["cashiers"], p["baristas"]):
                        cond = {**base, "arr_rate": max(cu, 1) / 60}
                        row["level"], _ = predict(model, {**cond, "num_cashier": ca, "num_barista": ba})
                        row["wait"] = round(sim_check(cond, ca, ba)["avg_wait"], 1)
                        changed += 1
                    rows.append(row)
            if changed:
                db.save_plans(rows, plan_date, st.session_state.user["email"], action="plan_edited")
                st.session_state.edit_plan = False
                st.toast(f"Plan updated ({changed} hour(s) changed).")
                st.rerun()
            st.info("No changes to save.")


@st.dialog("Delete today's plan?")
def _delete_plan_dialog(plan_date):
    st.write("Staff will no longer see today's crew plan on **My Shift Today**. You can make and publish a new plan "
             "anytime in the **Staffing Planner**.")
    c1, c2 = st.columns(2)
    if c1.button("Cancel", width="stretch"):
        st.rerun()
    if c2.button("Yes, delete plan", type="primary", icon=":material/delete:", width="stretch"):
        db.delete_plans(plan_date, st.session_state.user["email"])
        st.session_state.edit_plan = False
        st.toast("Today's plan was deleted.")
        st.rerun()


# Planner
def planner():
    ui.page_header("Staffing Planner",
                   "The AI predicts how busy each hour will be and recommends the smallest crew that keeps waits short.")
    day_tab, hour_tab = st.tabs(["Plan the day", "Test a specific hour"])
    with day_tab:
        _plan_day()
    with hour_tab:
        _plan_hour()


def _plan_day():
    model = get_model()
    ui.steps(["Pick the day", "AI plans every hour", "Review", "Publish to staff"])
    d = st.date_input("Day to plan", value=db.ph_today(), key="day_date")
    slots = slots_for(d)
    if not slots:
        st.warning("Jungle Brew is closed on Sundays. Pick another day.")
        return
    if db.get_plans(str(d)):
        st.caption("A plan for this day is already published. Publishing again replaces it. "
                   "To change it without re-planning, use Edit plan on the Dashboard.")
    cust, src = expected_customers(d, slots)
    with st.expander("Expected customers per hour (edit if you expect a promo or a slow day)"):
        df = pd.DataFrame({"Hour": [slot_label(s) for s in slots], "Customers": [cust[s] for s in slots], "Source": [src[s] for s in slots]})
        edited = st.data_editor(df, hide_index=True, disabled=["Hour", "Source"], width="stretch", key=f"edit_{d}",
                                column_config={"Customers": st.column_config.NumberColumn(min_value=1, max_value=150,
                                                                                          step=1)})
        cust = {h: int(c) if pd.notna(c) else cust[h] for h, c in zip(slots, edited.Customers)}
    st.caption(f"Uses the café defaults in Settings (up to {max_staff()} counter staff per hour).")

    if st.button("Generate AI plan for the day", icon=":material/auto_awesome:", type="primary", key="day_go"):
        with st.spinner("The AI is planning every hour and double-checking each one..."):
            t0 = time.perf_counter()
            rows = plan_day(model, slots, cust, base_condition(), max_staff())
            db.record_timing("Plan the whole day (AI + double-check)", time.perf_counter() - t0)
            t0 = time.perf_counter()
            insight, provider = explain_day(d.strftime("%A, %B %d"), rows)
            if provider:
                db.record_timing("AI explanation (Gemini/Groq)", time.perf_counter() - t0)
        for r in rows:
            r.update(ai_cashiers=r["cashiers"], ai_baristas=r["baristas"], ai_level=r["level"], changed=False)
        st.session_state.day_result = {"date": str(d), "rows": rows, "insight": insight, "provider": provider,
                                       "edit": 0}

    res = st.session_state.get("day_result")
    if not res or res["date"] != str(d):
        return
    rows, ins = res["rows"], res["insight"]
    st.divider()
    ui.ai_card("AI plan summary", res["provider"], ins["headline"], [ins["peak"]] + list(ins["actions"]))

    changed = sum(r["changed"] for r in rows)
    title = "with your changes" if changed else "with the recommended crew"
    st.markdown(f"#### How busy each hour will be ({title})")
    ui.plain_chart(charts.day_strip(rows))
    ui.legend()
    st.markdown("#### Crew vs. expected customers")
    ui.plain_chart(charts.day_chart(rows))

    peak = max(rows, key=lambda r: r["customers"])
    a, b, c = st.columns(3)
    with a:
        ui.kpi("Busiest hour", slot_label(peak["slot"]), f"about {peak['customers']} customers", color=ui.AMBER)
    with b:
        ui.kpi("Most staff needed", max(r["cashiers"] + r["baristas"] for r in rows), "counter staff at one time")
    with c:
        ui.kpi("Hours with short waits", f"{sum(r['level'] == 'Okay' for r in rows)} / {len(rows)}",
               "with this plan", color=ui.LEVEL_COLOR["Okay"])
    if not all(r["reached"] for r in rows):
        st.warning("Some hours cannot reach short waits even with all available staff. "
                   "Consider extra help or a simpler menu for those hours.")

    _adjust_crew(res)

    if changed:
        st.info(f"You changed {changed} hour(s). The AI's original crew is saved too, so we can compare later.")
    if st.button("Publish this plan to staff", icon=":material/campaign:", type="primary", key="day_pub"):
        db.save_plans(rows, res["date"], st.session_state.user["email"])
        st.success("Published. Staff will see it on their 'My Shift Today' page.")


def _adjust_crew(res):
    """The AI recommends; the manager decides. Any hour can be changed before publishing."""
    rows = res["rows"]
    with st.expander("Hour-by-hour table · change the crew if needed", expanded=any(r["changed"] for r in rows)):
        st.caption("Change the cashiers or baristas for any hour, then press **Check my changes**. "
                   "The AI re-checks those hours so you can see the expected wait before publishing.")
        t = pd.DataFrame({
            "Hour": [slot_label(r["slot"]) for r in rows],
            "Customers": [r["customers"] for r in rows],
            "AI crew": [f"{r['ai_cashiers']}C + {r['ai_baristas']}B" for r in rows],
            "Cashiers": [r["cashiers"] for r in rows],
            "Baristas": [r["baristas"] for r in rows],
            "Level": [f"{ui.LEVEL_ICON[r['level']]} {r['level']}" for r in rows],
            "Expected wait (min)": [r["wait"] for r in rows],
            "AI confidence": [f"{r['confidence']:.0%}" for r in rows],
            "Changed": ["Yes" if r["changed"] else "" for r in rows],
        })
        edited = st.data_editor(
            t, hide_index=True, width="stretch", key=f"crew_edit_{res['date']}_{res['edit']}",
            disabled=[c for c in t.columns if c not in ("Cashiers", "Baristas")],
            column_config={"Cashiers": st.column_config.NumberColumn(min_value=1, max_value=2, step=1),
                           "Baristas": st.column_config.NumberColumn(min_value=1, max_value=4, step=1)})
        c1, c2, _ = st.columns([1, 1, 2])
        if c1.button("Check my changes", icon=":material/fact_check:", key="crew_apply", width="stretch"):
            model, base = get_model(), base_condition()
            with st.spinner("Re-checking the hours you changed..."):
                for r, cash, bar in zip(rows, edited.Cashiers, edited.Baristas):
                    cash = int(cash) if pd.notna(cash) else r["cashiers"]
                    bar = int(bar) if pd.notna(bar) else r["baristas"]
                    if (cash, bar) == (r["cashiers"], r["baristas"]):
                        continue
                    cond = {**base, "arr_rate": max(r["customers"], 1) / 60}
                    level, probs = predict(model, {**cond, "num_cashier": cash, "num_barista": bar})
                    sim = sim_check(cond, cash, bar)
                    r.update(cashiers=cash, baristas=bar, level=level, confidence=probs.get(level, 0.0),
                             wait=round(sim["avg_wait"], 1), walkout=sim["balk_rate"],
                             changed=(cash, bar) != (r["ai_cashiers"], r["ai_baristas"]))
            res["edit"] += 1
            st.rerun()
        if any(r["changed"] for r in rows) and c2.button("Undo my changes", icon=":material/undo:",
                                                         key="crew_undo", width="stretch"):
            model, base = get_model(), base_condition()
            for r in rows:
                if r["changed"]:
                    cond = {**base, "arr_rate": max(r["customers"], 1) / 60}
                    level, probs = predict(model, {**cond, "num_cashier": r["ai_cashiers"],
                                                   "num_barista": r["ai_baristas"]})
                    sim = sim_check(cond, r["ai_cashiers"], r["ai_baristas"])
                    r.update(cashiers=r["ai_cashiers"], baristas=r["ai_baristas"], level=level,
                             confidence=probs.get(level, 0.0), wait=round(sim["avg_wait"], 1), changed=False)
            res["edit"] += 1
            st.rerun()


def _plan_hour():
    model = get_model()
    st.caption("Use this to test one hour, for example during a promo or when someone is absent.")
    c1, c2, c3 = st.columns(3)
    d = c1.date_input("Date", value=db.ph_today(), key="hr_date")
    slots = slots_for(d)
    if not slots:
        st.warning("Jungle Brew is closed on Sundays.")
        return
    slot = c1.selectbox("Hour", slots, index=current_slot_index(slots), key=f"hr_slot_{d}", format_func=slot_label)
    cust, src = expected_customers(d, [slot])
    customers = c2.number_input("Expected customers this hour", 1, 150, cust[slot], key=f"hr_cust_{d}_{slot}")
    c2.caption(f"Suggested from {src[slot]}")
    cur_c = c3.number_input("Cashiers you have now", 1, 2, 1, key="hr_c")
    cur_b = c3.number_input("Baristas you have now", 1, 4, 1, key="hr_b")

    if st.button("Test this hour", icon=":material/science:", key="hr_go"):
        cond = {**base_condition(), "arr_rate": customers / 60}
        with st.spinner("The AI is checking every crew option..."):
            t0 = time.perf_counter()
            cur_level, cur_probs = predict(model, {**cond, "num_cashier": cur_c, "num_barista": cur_b})
            cur_sim = sim_check(cond, cur_c, cur_b)
            best, reached, sim, opts = recommend(model, cond, max_staff())
            ctx = dict(slot=slot, day=d.strftime("%A"), customers=customers, p_simple=cond["p_simple"],
                       cur_c=cur_c, cur_b=cur_b, cur_level=cur_level, cur_wait=cur_sim["avg_wait"],
                       cur_walkout=cur_sim["balk_rate"], rec_c=best["cashiers"], rec_b=best["baristas"],
                       rec_level=best["level"], rec_conf=best["p_okay"], rec_wait=sim["avg_wait"],
                       rec_walkout=sim["balk_rate"], rec_util=sim["util_barista"], reached=reached)
            db.record_timing("Test a specific hour (all crew options)", time.perf_counter() - t0)
            insight, provider = explain_hour(ctx)
        st.session_state.hour_result = dict(ctx=ctx, cur_probs=cur_probs, best=best, opts=opts,
                                            insight=insight, provider=provider, date=str(d))

    res = st.session_state.get("hour_result")
    if not res:
        return
    ctx, ins = res["ctx"], res["insight"]
    st.divider()
    ui.ai_card("AI Insight", res["provider"], ins["headline"], None,
               f"<div>{ui.chip('Tip: ' + str(ins['tip']))}</div>")

    left, right = st.columns([1, 1.6], gap="large")
    with left:
        with st.container(border=True):
            st.markdown("**Recommended crew**")
            st.markdown(ui.people(ctx["rec_c"], ctx["rec_b"]), unsafe_allow_html=True)
            st.markdown(ui.badge(ctx["rec_level"], "1.05rem"), unsafe_allow_html=True)
            ui.plain_chart(charts.wait_gauge(ctx["rec_wait"], "Expected average wait"), key="hr_gauge")
    with right:
        ui.plain_chart(charts.options_bar(res["opts"], res["best"]), key="hr_opts")

    with st.expander("Details for the panel"):
        a, b = st.columns(2)
        with a:
            st.markdown("**Your current crew**")
            st.markdown(ui.people(ctx["cur_c"], ctx["cur_b"]), unsafe_allow_html=True)
            st.markdown(f"{ui.badge(ctx['cur_level'])} · about **{ctx['cur_wait']:.1f} min** wait · "
                        f"{ctx['cur_walkout']:.0%} of customers may walk out", unsafe_allow_html=True)
        with b:
            st.markdown("**Recommended crew**")
            st.markdown(ui.people(ctx["rec_c"], ctx["rec_b"]), unsafe_allow_html=True)
            st.markdown(f"{ui.badge(ctx['rec_level'])} · about **{ctx['rec_wait']:.1f} min** wait · "
                        f"{ctx['rec_walkout']:.0%} of customers may walk out · AI confidence "
                        f"**{ctx['rec_conf']:.0%}**", unsafe_allow_html=True)
        st.markdown("**How sure the AI is about your current crew**")
        ui.plain_chart(charts.confidence_bar(res["cur_probs"]), key="hr_conf")
        st.markdown("**Why (AI explanation)**")
        for w in ins["why"]:
            st.markdown(f"- {esc(str(w))}")
        st.markdown(f"**If you keep the current crew:** {esc(str(ins['risk']))}")
        st.markdown(f"""
**How the AI decided**
1. The AI model learned from 4,000 practice café hours. It predicted every crew option above as Okay, Congested, or Overloaded.
2. It picked the **smallest crew** predicted as Okay → {ui.crew_text(ctx['rec_c'], ctx['rec_b'])}.
3. That crew was **double-checked** with the queueing simulator → about **{ctx['rec_wait']:.1f} min** wait.
4. Gemini turned these numbers into the short advice above.
""")
    if st.button("Publish this hour to staff", icon=":material/campaign:", key="hr_pub"):
        existing = [{"slot": p["time_slot"], "customers": p["customers"], "cashiers": p["cashiers"],
                     "baristas": p["baristas"], "level": p["predicted_level"], "wait": p["expected_wait"] or 0,
                     "insight": p["ai_insight"] or "", "ai_cashiers": p["ai_cashiers"] or p["cashiers"],
                     "ai_baristas": p["ai_baristas"] or p["baristas"]}
                    for p in db.get_plans(res["date"]) if p["time_slot"] != ctx["slot"]]
        existing.append({"slot": ctx["slot"], "customers": ctx["customers"], "cashiers": ctx["rec_c"],
                         "baristas": ctx["rec_b"], "level": ctx["rec_level"], "wait": round(ctx["rec_wait"], 1),
                         "insight": str(ins["headline"])})
        db.save_plans(sorted(existing, key=lambda r: r["slot"]), res["date"], st.session_state.user["email"])
        st.success("Published to staff.")


# Reports
def _summary_csv(summary, provider, period):
    rows = [{"section": "Headline", "item": summary.get("headline", ""), "count": ""}]
    rows += [{"section": "Top issue", "item": i.get("issue", ""), "count": i.get("count", "")}
             for i in summary.get("top_issues", []) if isinstance(i, dict)]
    rows += [{"section": "Went well", "item": g, "count": ""} for g in summary.get("went_well", [])]
    rows += [{"section": "Suggested action", "item": a, "count": ""} for a in summary.get("actions", [])]
    rows += [{"section": "Made by", "item": provider or "Basic summary (AI unavailable)", "count": ""},
             {"section": "Period", "item": period, "count": ""},
             {"section": "Generated", "item": db.now(), "count": ""}]
    return pd.DataFrame(rows).to_csv(index=False).encode("utf-8")


def reports():
    archived = st.session_state.get("show_archive", False)
    archived_n = len(db.get_reports(archived=True))

    def archive_button():
        label = "Back to reports" if archived else f"Archive ({archived_n})"
        icon = ":material/arrow_back:" if archived else ":material/archive:"
        if st.button(label, icon=icon, key="archive_toggle", width="content",
                     help="Reports you archived. They are deleted automatically after 30 days."):
            st.session_state.show_archive = not archived
            st.rerun()

    ui.page_header("Archived Reports" if archived else "Staff Reports",
                   f"Reports you archived. Restore them, or they are deleted automatically {db.ARCHIVE_DAYS} days "
                   "after archiving." if archived else
                   "What your team reported about their shifts. The AI tags every report and can summarize the week.",
                   extra=archive_button)
    if db.count_new_reports():
        st.session_state.fresh_ids = {r["id"] for r in db.get_reports() if not r["seen_by_manager"]}
        db.mark_reports_seen()
        st.rerun()
    fresh = st.session_state.get("fresh_ids", set())
    me = st.session_state.user["email"]

    names = staff_lookup()
    if archived:
        reps = db.get_reports(archived=True)
        if not reps:
            st.info("The archive is empty. To archive a report, press Archive on the report card.")
        for r in reps:
            _archived_card(r, names, me)
        return

    f1, f2, f3, f4 = st.columns(4)
    status = f1.selectbox("Status", ["All", "Open", "Resolved"])
    days = f2.selectbox("Period", [7, 14, 30, 365], format_func=lambda x: f"Last {x} days" if x < 365 else "All time")
    sent = f3.multiselect("Feeling", ["Positive", "Neutral", "Negative"], placeholder="All")
    cats = f4.multiselect("Topic", CATEGORIES, placeholder="All")
    reps = [r for r in db.get_reports(days=days)
            if (not sent or r["sentiment"] in sent) and (not cats or r["category"] in cats)
            and (status == "All" or r["status"] == status)]
    if not reps:
        st.info("No reports match these filters. Staff send them from 'End-of-Shift Report' and 'Report an Incident'.")
        return

    df = pd.DataFrame(reps)
    a, b, c, d = st.columns(4)
    with a:
        ui.kpi("Reports", len(df))
    with b:
        ui.kpi("Negative", int((df.sentiment == "Negative").sum()), color=ui.RED)
    with c:
        ui.kpi("Positive", int((df.sentiment == "Positive").sum()), color=ui.LEVEL_COLOR["Okay"])
    with d:
        ui.kpi("Open issues", int((df.status == "Open").sum()), color=ui.AMBER)

    g1, g2, g3 = st.columns(3)
    with g1:
        ui.plain_chart(charts.sentiment_donut(df))
    with g2:
        ui.plain_chart(charts.category_bar(df))
    with g3:
        ui.plain_chart(charts.trend(df))

    period = f"last {days} days" if days < 365 else "all time"
    if st.button("Generate AI weekly summary", icon=":material/auto_awesome:", type="primary"):
        with st.spinner("The AI is reading the reports..."):
            st.session_state.week = (*weekly_summary(reps, db.staff_names()), period)
    week = st.session_state.get("week")
    if week and week[0]:
        s, provider, wperiod = week
        issues = "".join(ui.chip(f"{i.get('issue')} · {i.get('count', '')}")
                         for i in s.get("top_issues", []) if isinstance(i, dict))
        good = "".join(ui.chip(g) for g in s.get("went_well", []))
        ui.ai_card("AI Weekly Summary", provider, s["headline"], list(s.get("actions", [])),
                   f"<div style='margin-top:10px'><b>Top issues</b><br>{issues}</div>"
                   f"<div style='margin-top:8px'><b>What went well</b><br>{good}</div>")
        st.download_button("Download summary (CSV)", _summary_csv(s, provider, wperiod),
                           file_name=f"brewstaff_weekly_summary_{db.ph_today()}.csv", mime="text/csv",
                           icon=":material/download:")

    head, dl = st.columns([3, 1], vertical_alignment="bottom")
    head.markdown("#### All reports")
    export = df.drop(columns=[c for c in df.columns if c.startswith("check_") or c in ("checked_by", "checked_at",
                                                                                         "seen_by_manager",
                                                                                         "reply_seen")])
    dl.download_button("Download reports (CSV)", export.to_csv(index=False).encode("utf-8"),
                       file_name=f"brewstaff_reports_{db.ph_today()}.csv", mime="text/csv",
                       icon=":material/download:", width="stretch")
    for r in reps:
        _report_card(r, names, me, r["id"] in fresh)


def _chips(r, names, is_new=False):
    return ((ui.chip("New", "bs-new") if is_new else "") +
            ui.chip(f"{ui.CAT_ICON.get(r['category'], '')} {r['category']}") +
            ui.chip("End of shift" if r["report_type"] == "end_of_shift" else "Incident") +
            ui.chip(names.get(r["user_email"], r["user_email"])) +
            ui.chip(dt_label(r["created_at"])) +
            (ui.chip("Edited") if r["edited_at"] else "") +
            ui.chip("Resolved" if r["status"] == "Resolved" else "Open"))


def _report_card(r, names, me, is_new):
    with st.container(border=True):
        top, act = st.columns([5, 1])
        with top:
            st.markdown(f"{ui.SENT_ICON.get(r['sentiment'], '')} **{esc(r['ai_summary'] or r['text'] or '')}**",
                        unsafe_allow_html=True)
            st.markdown(_chips(r, names, is_new), unsafe_allow_html=True)
            if r["report_type"] == "end_of_shift" and r["predicted_level"]:
                st.markdown(f"{slot_label(r['time_slot'])} · {r['customers']} customers · staff felt "
                            f"{ui.badge(r['reported_level'])} · AI predicted {ui.badge(r['predicted_level'])}",
                            unsafe_allow_html=True)
            if r["reply"]:
                st.markdown(f"<div class='bs-reply'><b>Your reply</b> · {dt_label(r['replied_at'])}<br>"
                            f"{esc(r['reply'])}</div>", unsafe_allow_html=True)
        with act:
            if r["status"] == "Open":
                if st.button("Resolve", key=f"res{r['id']}", icon=":material/check:", width="stretch"):
                    db.set_status(r["id"], "Resolved", by=me)
                    st.rerun()
            elif st.button("Reopen", key=f"reo{r['id']}", icon=":material/undo:", width="stretch"):
                db.set_status(r["id"], "Open", by=me)
                st.rerun()
            if st.button("Archive", key=f"arc{r['id']}", icon=":material/archive:", width="stretch"):
                _archive_dialog(r, me)
        with st.expander("Original text and reply"):
            st.write(r["text"] or "—")
            st.caption(f"Tagged by {r['ai_provider'] or 'basic keyword tagging (AI unavailable)'}")
            reply = st.text_area("Reply to the staff member", value=r["reply"] or "", max_chars=500,
                                 key=f"rep{r['id']}", placeholder="Example: Thanks! We'll add a second barista at noon.")
            if st.button("Send reply", key=f"rep_btn{r['id']}", icon=":material/send:"):
                if reply.strip():
                    db.reply_to_report(r["id"], reply, me)
                    st.toast("Reply sent. The staff member will see it in My Reports.")
                    st.rerun()
                else:
                    st.error("Please write a reply first.")


@st.dialog("Archive this report?")
def _archive_dialog(r, me):
    st.markdown(f"**{esc(r['ai_summary'] or r['text'] or '')}**", unsafe_allow_html=True)
    reason = st.text_input("Reason for archiving", max_chars=200, placeholder="Example: duplicate, test report")
    st.caption(f"The report is hidden from the list and charts. You can restore it from **Archive** (top right). "
               f"It is deleted automatically {db.ARCHIVE_DAYS} days after archiving.")
    c1, c2 = st.columns(2)
    if c1.button("Cancel", width="stretch"):
        st.rerun()
    if c2.button("Archive", type="primary", icon=":material/archive:", width="stretch"):
        if not reason.strip():
            st.error("Please give a reason for archiving.")
            return
        db.archive_report(r["id"], reason, me)
        st.toast("Report archived. Find it under Archive at the top right.")
        st.rerun()


@st.dialog("Delete this report permanently?")
def _delete_archived_dialog(r, me):
    st.markdown(f"**{esc(r['ai_summary'] or r['text'] or '')}**", unsafe_allow_html=True)
    st.warning("This cannot be undone. The report will be removed from BrewStaffAI for good.")
    c1, c2 = st.columns(2)
    if c1.button("Cancel", width="stretch"):
        st.rerun()
    if c2.button("Yes, delete", type="primary", icon=":material/delete:", width="stretch"):
        db.delete_report(r["id"], me)
        st.rerun()


def _archived_card(r, names, me):
    with st.container(border=True):
        st.markdown(f"{ui.SENT_ICON.get(r['sentiment'], '')} **{esc(r['ai_summary'] or r['text'] or '')}**",
                    unsafe_allow_html=True)
        st.markdown(_chips(r, names), unsafe_allow_html=True)
        purge = db.purge_date(r)
        st.caption(f"Archived {dt_label(r['archived_at'])} by {names.get(r['archived_by'], r['archived_by'])} · "
                   f"Reason: {r['archive_reason']} · Deletes automatically on {purge:%B} {purge.day}, {purge.year}")
        c1, c2, _ = st.columns([1, 1, 3])
        if c1.button("Restore", key=f"rst{r['id']}", icon=":material/unarchive:", width="stretch"):
            db.restore_report(r["id"], me)
            st.rerun()
        if c2.button("Delete now", key=f"del{r['id']}", icon=":material/delete:", width="stretch"):
            _delete_archived_dialog(r, me)


# How the ai works
def how_ai_works():
    ui.page_header("How the AI Works",
                   "A simple, visual explanation of the two AI parts of BrewStaffAI and how accurate they are.")
    steps = [("1", "Simulator", "The COMP 014 queueing simulator plays 4,000 practice café hours."),
             ("2", "Labels", "Each hour is labeled Okay, Congested, or Overloaded by its average wait."),
             ("3", "Decision Tree", "The AI learns rules like “IF barista workload is high → Overloaded”."),
             ("4", "Recommendation", "It picks the smallest crew predicted as Okay, then double-checks it."),
             ("5", "Gemini", "A language model explains the result and reads staff reports.")]
    cols = st.columns(len(steps))
    for col, (n, t, d) in zip(cols, steps):
        col.markdown(f"<div class='bs-card' style='text-align:center'><div class='bs-step' style='justify-content:"
                     f"center;margin:0 0 6px'><span class='dot'>{n}</span></div>"
                     f"<b>{t}</b><div class='bs-kpi-sub' style='margin-top:6px'>{d}</div></div>",
                     unsafe_allow_html=True)
    with open(os.path.join(HERE, "model", "metrics.json")) as f:
        m = json.load(f)
    st.write("")
    a, b, c = st.columns(3)
    with a:
        ui.plain_chart(charts.accuracy_gauge(m["test_accuracy"], m["baseline_accuracy"]))
    with b:
        ui.plain_chart(charts.confusion(m["confusion_matrix"]))
    with c:
        ui.plain_chart(charts.importance(m["feature_importance"]))
    st.markdown(f"""
<div class='bs-card'><b>In simple words:</b> out of {m['test_rows']} café hours the AI had never seen,
it guessed the right congestion level <b>{m['test_accuracy']:.1%}</b> of the time. Always guessing “Okay” would only be
right {m['baseline_accuracy']:.0%} of the time. The AI pays the most attention to <b>barista workload</b>,
because the barista station is the café's main bottleneck.</div>""", unsafe_allow_html=True)

    st.markdown("#### Accuracy per level")
    st.caption("Precision: when the AI says this level, how often it is right. "
               "Recall: of the hours that really are this level, how many the AI caught.")
    rep = m["report"]
    pr = pd.DataFrame([{"Level": f"{ui.LEVEL_ICON[l]} {l}", "Precision": f"{rep[l]['precision']:.1%}",
                        "Recall": f"{rep[l]['recall']:.1%}", "F1-score": f"{rep[l]['f1-score']:.1%}",
                        "Test hours": int(rep[l]["support"])} for l in ("Okay", "Congested", "Overloaded")])
    left, right = st.columns([1.3, 1], gap="large")
    with left:
        st.dataframe(pr, hide_index=True, width="stretch")
    with right:
        weakest = min(("Okay", "Congested", "Overloaded"), key=lambda l: rep[l]["f1-score"])
        st.markdown(f"<div class='bs-card'><b>Where the AI makes mistakes:</b> the hardest level is "
                    f"<b>{weakest}</b> ({rep[weakest]['f1-score']:.0%} F1). Most mistakes happen in hours close to "
                    f"the 7-minute or 15-minute limit, where a small change in customers moves the hour to the next "
                    f"level. The AI almost never confuses Okay with Overloaded.</div>", unsafe_allow_html=True)

    st.markdown("#### Response time")
    model = get_model()
    cond = {**base_condition(), "arr_rate": 20 / 60, "num_cashier": 1, "num_barista": 2}
    t0 = time.perf_counter()
    for _ in range(50):
        predict(model, cond)
    one = (time.perf_counter() - t0) / 50 * 1000
    stats = db.timing_stats()
    a, b = st.columns([1, 2], gap="large")
    with a:
        ui.kpi("One AI prediction", f"{one:.1f} ms", "measured just now (average of 50)", color=ui.LIME)
    with b:
        if stats:
            st.dataframe(pd.DataFrame([{"Task": s_["kind"], "Times measured": int(s_["n"]),
                                        "Average (sec)": round(s_["avg_s"], 2), "Fastest": round(s_["min_s"], 2),
                                        "Slowest": round(s_["max_s"], 2)} for s_ in stats]),
                         hide_index=True, width="stretch")
        else:
            st.caption("Times for planning, testing an hour, and AI tagging appear here after they are used.")
    st.write("")
    st.page_link(st.session_state.pages["pilot"], label="See how the AI did in real shifts (Pilot Results)",
                 icon=":material/arrow_forward:")
