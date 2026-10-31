"""
pages_manager.py — Manager pages: Dashboard, Staffing Planner, Staff Reports, How the AI Works.
Results are shown as visuals first (gauges, colored timelines, charts) and short AI cards second.
"""
import json
import os
from datetime import date, datetime

import pandas as pd
import streamlit as st

import charts
import db
import ui
from ai_helper import explain_day, explain_hour, weekly_summary
from recommender import load_model, plan_day, predict, recommend, sim_check

HERE = os.path.dirname(os.path.abspath(__file__))


@st.cache_resource
def get_model():
    return load_model()


def slots_for(d):
    wd = d.weekday()
    if wd == 6:
        return []
    return [f"{h:02d}:00-{h + 1:02d}:00" for h in range(11 if wd == 5 else 8, 22)]


def expected_customers(d, slots):
    prof = db.get_setting("hourly_profile")
    out, src = {}, {}
    for s in slots:
        avg, n = db.avg_reported_customers(d.strftime("%A"), s)
        out[s] = int(round(avg)) if avg else int(prof.get(str(int(s[:2])), 15))
        src[s] = f"staff reports ({n})" if avg else "café defaults"
    return out, src


def base_condition(p_simple=None):
    svc = db.get_setting("service_times")
    return dict(p_simple=svc["p_simple"] if p_simple is None else p_simple, cashier_mean=svc["cashier"],
                simple_prep=svc["simple"], complex_prep=svc["complex"])


# ================================================================== DASHBOARD
def dashboard():
    user = st.session_state.user
    hour = datetime.now().hour
    greet = "Good morning" if hour < 12 else "Good afternoon" if hour < 18 else "Good evening"
    ui.page_header("🏠", f"{greet}, {user['full_name'].split()[0]}!",
                   "Today at a glance. Start with the Staffing Planner, then check what your staff reported.")
    today = date.today()
    plans = db.get_plans(str(today))
    reps7 = db.get_reports(days=7)
    eos = [r for r in db.get_reports() if r["report_type"] == "end_of_shift" and r["predicted_level"]]
    match = sum(r["predicted_level"] == r["reported_level"] for r in eos)

    a, b, c, d = st.columns(4)
    with a:
        ui.kpi("Today's plan", f"{len(plans)} hrs" if plans else "Not yet", "hours planned by the AI",
               color=ui.LIME if plans else ui.AMBER)
    with b:
        ui.kpi("Open issues", sum(r["status"] == "Open" for r in reps7), "from staff, last 7 days",
               color=ui.RED if any(r["status"] == "Open" for r in reps7) else ui.TEXT)
    with c:
        ui.kpi("Staff reports", len(reps7), "last 7 days")
    with d:
        ui.kpi("AI vs. real shifts", f"{match / len(eos):.0%}" if eos else "—",
               f"agreement on {len(eos)} end-of-shift report(s)")
    st.write("")

    left, right = st.columns([1.6, 1], gap="large")
    with left:
        st.markdown("#### 📅 Today's staffing plan")
        if plans:
            rows = [{"slot": p["time_slot"], "level": p["predicted_level"], "wait": p["expected_wait"] or 0,
                     "customers": p["customers"], "cashiers": p["cashiers"], "baristas": p["baristas"]} for p in plans]
            st.plotly_chart(charts.day_strip(rows), width="stretch", config={"displayModeBar": False})
            ui.legend()
            st.plotly_chart(charts.day_chart(rows), width="stretch", config={"displayModeBar": False})
        else:
            st.info("No plan for today yet. The AI can build one in a few seconds.")
            st.page_link(st.session_state.pages["planner"], label="Open the Staffing Planner", icon="➡️")
    with right:
        st.markdown("#### 🗂️ Latest staff reports")
        if not reps7:
            st.caption("No reports in the last 7 days.")
        for r in reps7[:5]:
            st.markdown(f"<div class='bs-card' style='margin-bottom:8px;padding:12px 14px'>"
                        f"{ui.SENT_ICON.get(r['sentiment'], '')} <b>{r['ai_summary'] or r['text']}</b><br>"
                        f"{ui.chip(ui.CAT_ICON.get(r['category'], '') + ' ' + r['category'])}"
                        f"{ui.chip(r['status'])}<span style='color:{ui.MUTED};font-size:.8rem'> {r['created_at'][:16]}"
                        f"</span></div>", unsafe_allow_html=True)


# ================================================================== PLANNER
def planner():
    ui.page_header("📅", "Staffing Planner",
                   "The AI predicts how busy each hour will be and recommends the smallest crew that keeps waits short.")
    day_tab, hour_tab = st.tabs(["📆 Plan the whole day", "🔍 Check one hour in detail"])
    with day_tab:
        _plan_day()
    with hour_tab:
        _plan_hour()


def _plan_day():
    model = get_model()
    ui.steps(["Pick the day", "AI plans every hour", "Review the visuals", "Publish to staff"])
    c1, c2, c3 = st.columns(3)
    d = c1.date_input("Day to plan", value=date.today(), key="day_date")
    max_staff = c2.slider("Most counter staff available", 2, 6, int(db.get_setting("max_counter_staff")), key="day_max")
    p_simple = c3.slider("Simple drinks (%)", 0, 100, int(db.get_setting("service_times")["p_simple"] * 100), 5,
                         key="day_ps") / 100
    slots = slots_for(d)
    if not slots:
        st.warning("Jungle Brew is closed on Sundays. Pick another day.")
        return
    cust, src = expected_customers(d, slots)
    with st.expander("👥 Expected customers per hour (edit if you expect a promo or a slow day)"):
        df = pd.DataFrame({"Hour": slots, "Customers": [cust[s] for s in slots], "Source": [src[s] for s in slots]})
        edited = st.data_editor(df, hide_index=True, disabled=["Hour", "Source"], width="stretch", key="day_edit")
        cust = dict(zip(edited.Hour, edited.Customers))

    if st.button("✨ Generate AI plan for the day", type="primary", key="day_go"):
        with st.spinner("The AI is planning every hour and checking each one with the simulator..."):
            rows = plan_day(model, slots, cust, base_condition(p_simple), max_staff)
            insight, provider = explain_day(d.strftime("%A, %B %d"), rows)
        st.session_state.day_result = {"date": str(d), "rows": rows, "insight": insight, "provider": provider}

    res = st.session_state.get("day_result")
    if not res or res["date"] != str(d):
        return
    rows, ins = res["rows"], res["insight"]
    st.divider()
    ui.ai_card("AI plan summary", res["provider"], ins["headline"], [ins["peak"]] + list(ins["actions"]))

    st.markdown("#### 🚦 How busy each hour will be (with the recommended crew)")
    st.plotly_chart(charts.day_strip(rows), width="stretch", config={"displayModeBar": False})
    ui.legend()
    st.markdown("#### 👥 Recommended crew vs. expected customers")
    st.plotly_chart(charts.day_chart(rows), width="stretch", config={"displayModeBar": False})

    peak = max(rows, key=lambda r: r["customers"])
    a, b, c = st.columns(3)
    with a:
        ui.kpi("Busiest hour", peak["slot"], f"about {peak['customers']} customers", color=ui.AMBER)
    with b:
        ui.kpi("Most staff needed", max(r["cashiers"] + r["baristas"] for r in rows), "counter staff at one time")
    with c:
        ui.kpi("Hours that reach Okay", f"{sum(r['level'] == 'Okay' for r in rows)} / {len(rows)}",
               "with the available staff", color=ui.LEVEL_COLOR["Okay"])
    with st.expander("📋 Hour-by-hour table"):
        t = pd.DataFrame(rows)
        t["Crew"] = t.apply(lambda r: "🧾" * r.cashiers + " " + "☕" * r.baristas, axis=1)
        t["Level"] = t.level.map(lambda l: f"{ui.LEVEL_ICON[l]} {l}")
        st.dataframe(t.rename(columns={"slot": "Hour", "customers": "Customers", "wait": "Expected wait (min)"})
                     [["Hour", "Customers", "Crew", "Level", "Expected wait (min)"]], hide_index=True, width="stretch")
    if not all(r["reached"] for r in rows):
        st.warning("Some hours cannot reach 'Okay' even with all available staff. Consider extra help or a simpler menu.")
    if st.button("📢 Publish this plan to staff", type="primary", key="day_pub"):
        db.save_plans(rows, res["date"], st.session_state.user["email"])
        st.success("Published! Staff will see it on their 'My Shift Today' page.")


def _plan_hour():
    model = get_model()
    ui.steps(["Describe the hour", "AI predicts", "AI recommends", "Simulator double-checks", "AI explains"])
    c1, c2, c3 = st.columns(3)
    d = c1.date_input("Date", value=date.today(), key="hr_date")
    slots = slots_for(d)
    if not slots:
        st.warning("Jungle Brew is closed on Sundays.")
        return
    slot = c1.selectbox("Time slot", slots, index=min(4, len(slots) - 1), key="hr_slot")
    cust, src = expected_customers(d, [slot])
    customers = c2.number_input("Expected customers this hour", 1, 100, cust[slot], key="hr_cust")
    c2.caption(f"Suggested from {src[slot]}")
    max_staff = c2.slider("Most counter staff available", 2, 6, int(db.get_setting("max_counter_staff")), key="hr_max")
    cur_c = c3.number_input("Current plan: cashiers 🧾", 1, 2, 1, key="hr_c")
    cur_b = c3.number_input("Current plan: baristas ☕", 1, 4, 1, key="hr_b")

    if st.button("✨ Ask BrewStaffAI", type="primary", key="hr_go"):
        cond = {**base_condition(), "arr_rate": customers / 60}
        with st.spinner("AI is analyzing..."):
            cur_level, cur_probs = predict(model, {**cond, "num_cashier": cur_c, "num_barista": cur_b})
            cur_sim = sim_check(cond, cur_c, cur_b)
            best, reached, sim, opts = recommend(model, cond, max_staff)
            ctx = dict(slot=slot, day=d.strftime("%A"), customers=customers, p_simple=cond["p_simple"],
                       cur_c=cur_c, cur_b=cur_b, cur_level=cur_level, cur_wait=cur_sim["avg_wait"],
                       cur_walkout=cur_sim["balk_rate"], rec_c=best["cashiers"], rec_b=best["baristas"],
                       rec_level=best["level"], rec_conf=best["p_okay"], rec_wait=sim["avg_wait"],
                       rec_walkout=sim["balk_rate"], rec_util=sim["util_barista"], reached=reached)
            insight, provider = explain_hour(ctx)
        st.session_state.hour_result = dict(ctx=ctx, cur_probs=cur_probs, best=best, sim=sim, opts=opts,
                                            insight=insight, provider=provider, cur_sim=cur_sim, date=str(d))

    res = st.session_state.get("hour_result")
    if not res:
        return
    ctx, ins = res["ctx"], res["insight"]
    st.divider()
    ui.ai_card("AI Insight", res["provider"], ins["headline"], list(ins["why"]),
               f"<div style='margin-top:10px'>{ui.chip('⚠️ If you keep the current plan: ' + ins['risk'])}</div>"
               f"<div>{ui.chip('💡 Tip: ' + ins['tip'])}</div>")

    left, right = st.columns(2, gap="large")
    for col, title, c, b, lvl, wait, walk in (
            (left, "Current plan", ctx["cur_c"], ctx["cur_b"], ctx["cur_level"], ctx["cur_wait"], ctx["cur_walkout"]),
            (right, "✨ AI recommendation", ctx["rec_c"], ctx["rec_b"], ctx["rec_level"], ctx["rec_wait"],
             ctx["rec_walkout"])):
        with col:
            with st.container(border=True):
                st.markdown(f"#### {title}")
                st.markdown(ui.people(c, b), unsafe_allow_html=True)
                st.markdown(f"AI prediction: {ui.badge(lvl, '1.05rem')}", unsafe_allow_html=True)
                st.plotly_chart(charts.wait_gauge(wait, "Expected average wait"), width="stretch",
                                config={"displayModeBar": False}, key=f"g_{title}")
                st.caption(f"🚶 About {walk:.0%} of customers would walk out because of the line.")

    st.markdown("#### 🎯 How sure is the AI about the current plan?")
    st.plotly_chart(charts.confidence_bar(res["cur_probs"]), width="stretch", config={"displayModeBar": False})
    st.plotly_chart(charts.options_bar(res["opts"], res["best"]), width="stretch", config={"displayModeBar": False})
    with st.expander("🧠 How did the AI decide? (simple explanation)"):
        st.markdown(f"""
1. **Prediction (Decision Tree):** the AI learned from 4,000 simulated café hours. For {ctx['customers']} customers,
   it predicted every crew option above as Okay, Congested, or Overloaded.
2. **Recommendation:** it picked the **smallest crew** predicted as **Okay** →
   {ctx['rec_c']} cashier(s) + {ctx['rec_b']} barista(s).
3. **Double-check (Simulator):** the queueing simulator ran that crew 10 times → about **{ctx['rec_wait']:.1f} min** wait.
4. **Explanation (Gemini):** the language model turned these numbers into the short advice above.
""")
    if st.button("📢 Publish this hour to staff", key="hr_pub"):
        existing = [{"slot": p["time_slot"], "customers": p["customers"], "cashiers": p["cashiers"],
                     "baristas": p["baristas"], "level": p["predicted_level"], "wait": p["expected_wait"]}
                    for p in db.get_plans(res["date"]) if p["time_slot"] != ctx["slot"]]
        existing.append({"slot": ctx["slot"], "customers": ctx["customers"], "cashiers": ctx["rec_c"],
                         "baristas": ctx["rec_b"], "level": ctx["rec_level"], "wait": round(ctx["rec_wait"], 1),
                         "insight": ins["headline"]})
        db.save_plans(sorted(existing, key=lambda r: r["slot"]), res["date"], st.session_state.user["email"])
        st.success("Published to staff.")


# ================================================================== REPORTS
def reports():
    ui.page_header("🗂️", "Staff Reports",
                   "What your team reported about their shifts. The AI tags every report and can summarize the week.")
    all_reps = db.get_reports()
    if not all_reps:
        st.info("No reports yet. Staff can send them from their 'End-of-Shift Report' and 'Report an Incident' pages.")
        return
    f1, f2, f3, f4 = st.columns(4)
    days = f1.selectbox("Period", [7, 14, 30, 365], format_func=lambda x: f"Last {x} days" if x < 365 else "All time")
    sent = f2.multiselect("Feeling", ["Positive", "Neutral", "Negative"], placeholder="All")
    cats = f3.multiselect("Topic", sorted({r["category"] for r in all_reps}), placeholder="All")
    status = f4.selectbox("Status", ["All", "Open", "Resolved"])
    reps = [r for r in db.get_reports(days=days)
            if (not sent or r["sentiment"] in sent) and (not cats or r["category"] in cats)
            and (status == "All" or r["status"] == status)]
    if not reps:
        st.warning("No reports match these filters.")
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
    g1.plotly_chart(charts.sentiment_donut(df), width="stretch", config={"displayModeBar": False})
    g2.plotly_chart(charts.category_bar(df), width="stretch", config={"displayModeBar": False})
    g3.plotly_chart(charts.trend(df), width="stretch", config={"displayModeBar": False})

    if st.button("✨ Generate AI weekly summary", type="primary"):
        with st.spinner("The AI is reading the reports..."):
            st.session_state.week = weekly_summary(reps, db.staff_names())
    if st.session_state.get("week") and st.session_state.week[0]:
        s, provider = st.session_state.week
        issues = "".join(ui.chip(f"🔴 {i.get('issue')} · {i.get('count', '')}") for i in s.get("top_issues", []))
        good = "".join(ui.chip(f"🟢 {g}") for g in s.get("went_well", []))
        ui.ai_card("AI Weekly Summary", provider, s["headline"], list(s.get("actions", [])),
                   f"<div style='margin-top:10px'><b>Top issues</b><br>{issues}</div>"
                   f"<div style='margin-top:8px'><b>What went well</b><br>{good}</div>")

    st.markdown("#### 📋 All reports")
    st.download_button("⬇️ Download as Excel-friendly CSV", df.to_csv(index=False).encode("utf-8"),
                       file_name=f"brewstaff_reports_{date.today()}.csv", mime="text/csv")
    names = {u["email"]: u["full_name"] for u in db.list_users()}
    for r in reps:
        with st.container(border=True):
            top, act = st.columns([5, 1])
            with top:
                st.markdown(f"{ui.SENT_ICON.get(r['sentiment'], '')} **{r['ai_summary'] or r['text']}**")
                st.markdown(ui.chip(f"{ui.CAT_ICON.get(r['category'], '')} {r['category']}") +
                            ui.chip("📝 End of shift" if r["report_type"] == "end_of_shift" else "⚠️ Incident") +
                            ui.chip(f"👤 {names.get(r['user_email'], r['user_email'])}") +
                            ui.chip(f"🕒 {r['created_at'][:16]}") +
                            (ui.chip("🟢 Resolved") if r["status"] == "Resolved" else ui.chip("🟠 Open")),
                            unsafe_allow_html=True)
                if r["report_type"] == "end_of_shift" and r["predicted_level"]:
                    st.markdown(f"{r['time_slot']} · {r['customers']} customers · staff felt "
                                f"{ui.badge(r['reported_level'])} · AI predicted {ui.badge(r['predicted_level'])}",
                                unsafe_allow_html=True)
                with st.expander("Original text"):
                    st.write(r["text"] or "—")
                    st.caption(f"Tagged by {r['ai_provider'] or 'offline keyword fallback'}")
            with act:
                if r["status"] == "Open":
                    if st.button("✅ Resolve", key=f"res{r['id']}", width="stretch"):
                        db.set_status(r["id"], "Resolved"); st.rerun()
                elif st.button("↩️ Reopen", key=f"reo{r['id']}", width="stretch"):
                    db.set_status(r["id"], "Open"); st.rerun()


# ================================================================== HOW THE AI WORKS
def how_ai_works():
    ui.page_header("🧠", "How the AI Works",
                   "A simple, visual explanation of the two AI parts of BrewStaffAI and how accurate they are.")
    steps = [("🧪", "Simulator", "The COMP 014 queueing simulator plays 4,000 practice café hours."),
             ("🏷️", "Labels", "Each hour is labeled Okay, Congested, or Overloaded by its average wait."),
             ("🌳", "Decision Tree", "The AI learns rules like “IF barista workload is high → Overloaded”."),
             ("📅", "Recommendation", "It picks the smallest crew predicted as Okay, then the simulator checks it."),
             ("💬", "Gemini", "A language model explains the result and reads staff reports.")]
    cols = st.columns(len(steps))
    for col, (ic, t, d) in zip(cols, steps):
        col.markdown(f"<div class='bs-card' style='text-align:center'><div style='font-size:2rem'>{ic}</div>"
                     f"<b>{t}</b><div class='bs-kpi-sub' style='margin-top:6px'>{d}</div></div>",
                     unsafe_allow_html=True)
    m = json.load(open(os.path.join(HERE, "model", "metrics.json")))
    st.write("")
    a, b, c = st.columns(3)
    a.plotly_chart(charts.accuracy_gauge(m["test_accuracy"], m["baseline_accuracy"]), width="stretch",
                   config={"displayModeBar": False})
    b.plotly_chart(charts.confusion(m["confusion_matrix"]), width="stretch", config={"displayModeBar": False})
    c.plotly_chart(charts.importance(m["feature_importance"]), width="stretch", config={"displayModeBar": False})
    st.markdown(f"""
<div class='bs-card'><b>In simple words:</b> out of {m['test_rows']} café hours the AI had never seen,
it guessed the right congestion level <b>{m['test_accuracy']:.1%}</b> of the time. Always guessing “Okay” would only be
right {m['baseline_accuracy']:.0%} of the time. The AI pays the most attention to <b>barista workload</b>,
because the barista station is the café's main bottleneck.</div>""", unsafe_allow_html=True)

    st.markdown("#### 🔎 Real-world check: AI prediction vs. what staff felt")
    eos = [r for r in db.get_reports() if r["report_type"] == "end_of_shift" and r["predicted_level"]]
    if not eos:
        st.info("This fills in during the pilot week, from staff end-of-shift reports.")
        return
    match = sum(r["predicted_level"] == r["reported_level"] for r in eos)
    l, r_ = st.columns([1, 1.4])
    l.plotly_chart(charts.donut(["Agreed", "Different"], [match, len(eos) - match],
                                [ui.LEVEL_COLOR["Okay"], ui.AMBER], f"{match / len(eos):.0%}<br>agree"),
                   width="stretch", config={"displayModeBar": False})
    t = pd.DataFrame(eos)[["report_date", "time_slot", "customers", "reported_level", "predicted_level"]]
    r_.dataframe(t.rename(columns={"report_date": "Date", "time_slot": "Hour", "customers": "Customers",
                                   "reported_level": "Staff felt", "predicted_level": "AI predicted"}),
                 hide_index=True, width="stretch")
