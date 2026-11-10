"""
pages_pilot.py - Pilot Results page for the paper and the defense.
  Tab 1: AI prediction vs. what staff felt, day by day.
  Tab 2: tagging accuracy check (team hand-labels reports without seeing the AI tags).
  Tab 3: demand forecast accuracy (v4.3.0): how close the customer forecast was to what really happened.
"""
import json
from datetime import date, timedelta

import pandas as pd
import streamlit as st

import charts
import db
import demand
import forecaster
import ui
from ai_helper import CATEGORIES, SENTIMENTS
from labels import CLASSES

PILOT_START, PILOT_END = date(2026, 11, 21), date(2026, 11, 28)
CHECK_GOAL = 50
TARGET = 0.80


def pilot_results():
    ui.page_header("Pilot Results",
                   "Our evidence for the paper: did the AI match what really happened during the pilot week?")
    with st.expander("How to use this page", icon=":material/help:", expanded=not any(r["report_type"] == "end_of_shift" for r in db.get_reports())):
        a, b = st.columns(2, gap="large")
        a.markdown("""**Tab 1 · AI vs. staff**
1. Staff send end-of-shift reports and choose how busy the hour *felt*.
2. BrewStaffAI saves what the AI *predicted* for the same hour.
3. This tab compares the two, day by day. A high **agreement %** means the AI matches real shifts.
4. Download the CSV files for Chapter 4 of the paper.""")
        b.markdown(f"""**Tab 2 · Check AI tags** (team members only)
1. Read one staff report at a time. The AI's answer is hidden on purpose.
2. Choose the feeling and topic **you** think is right, then save.
3. After {CHECK_GOAL} reports, the gauges show how often the AI agreed with you (target {TARGET:.0%}).
4. Download the results for the paper.""")
    t1, t2, t3 = st.tabs(["1 · AI vs. staff", "2 · Check AI tags", "3 · Demand forecast"])
    with t1:
        _agreement()
    with t2:
        _tag_check()
    with t3:
        _forecast()


def _default_range():
    today = db.ph_today()
    if today >= PILOT_START:
        return PILOT_START, min(today, PILOT_END)
    return today - timedelta(days=6), today


def _agreement():
    picked = st.date_input("Dates", value=_default_range(), key="pilot_dates",
                           help=f"The pilot week is {PILOT_START:%b %d}–{PILOT_END:%b %d}.")
    if not isinstance(picked, (tuple, list)) or len(picked) < 2:
        st.info("Pick a start and an end date.")
        return
    start, end = picked
    eos = [r for r in db.get_reports()
           if r["report_type"] == "end_of_shift" and r["predicted_level"] and r["reported_level"]
           and r["report_date"] and str(start) <= r["report_date"] <= str(end)]
    if not eos:
        st.info("No end-of-shift reports for these dates yet. Results appear here automatically as staff send "
                "end-of-shift reports. Try a wider date range, or wait for the pilot week to start.")
        return
    df = pd.DataFrame(eos)
    df["agree"] = df.predicted_level == df.reported_level
    rank = {c: i for i, c in enumerate(CLASSES)}
    busier = int((df.predicted_level.map(rank) > df.reported_level.map(rank)).sum())
    calmer = int((df.predicted_level.map(rank) < df.reported_level.map(rank)).sum())

    a, b, c, d = st.columns(4)
    with a:
        ui.kpi("End-of-shift reports", len(df), f"{df.report_date.nunique()} day(s)")
    with b:
        ui.kpi("Agreement", f"{df.agree.mean():.0%}", "AI prediction = what staff felt", color=ui.LIME)
    with c:
        ui.kpi("AI expected busier", busier, "than staff felt", color=ui.AMBER)
    with d:
        ui.kpi("AI expected calmer", calmer, "than staff felt", color=ui.RED if calmer else ui.TEXT)
    st.caption("**Agreement** = the AI predicted the same level the staff felt. **Busier / calmer** shows which way "
               "the AI was off when they disagreed.")

    by_day = (df.groupby("report_date").agg(reports=("agree", "size"), agreed=("agree", "sum"))
              .reset_index().sort_values("report_date"))
    by_day["different"] = by_day.reports - by_day.agreed
    by_day["agreement"] = (by_day.agreed / by_day.reports * 100).round(0)
    by_day["day"] = pd.to_datetime(by_day.report_date).dt.strftime("%a %b %d")
    left, right = st.columns([1.6, 1], gap="large")
    with left:
        ui.plain_chart(charts.agreement_by_day([{"day": r.day, "agree": int(r.agreed), "differ": int(r.different)}
                                                for r in by_day.itertuples()]))
    with right:
        matrix = [[int(((df.reported_level == felt) & (df.predicted_level == ai)).sum()) for ai in CLASSES]
                  for felt in CLASSES]
        ui.plain_chart(charts.confusion({"labels": CLASSES, "matrix": matrix}, "Staff felt vs. AI predicted",
                                        "AI:", "Staff:"))

    st.caption("Left: green bars = AI and staff agreed, amber = they differed; the line is the agreement % per day. "
               "Right: each box counts reports; the diagonal (top-left to bottom-right) means agreement.")
    table = by_day.rename(columns={"day": "Day", "reports": "Reports", "agreed": "Agreed",
                                   "different": "Different", "agreement": "Agreement %"})
    table = table[["Day", "Reports", "Agreed", "Different", "Agreement %"]]
    st.dataframe(table, hide_index=True, width="stretch")
    raw = df[["report_date", "time_slot", "customers", "cashiers", "baristas", "reported_level", "predicted_level",
              "agree"]].rename(columns={"reported_level": "staff_felt", "predicted_level": "ai_predicted"})
    c1, c2, _ = st.columns([1, 1, 2])
    c1.download_button("Day-by-day (CSV)", table.to_csv(index=False).encode("utf-8"),
                       file_name=f"pilot_agreement_by_day_{start}_{end}.csv", mime="text/csv",
                       icon=":material/download:", width="stretch")
    c2.download_button("All pilot reports (CSV)", raw.to_csv(index=False).encode("utf-8"),
                       file_name=f"pilot_reports_{start}_{end}.csv", mime="text/csv",
                       icon=":material/download:", width="stretch")


def _tag_check():
    me = st.session_state.user["email"]
    done = db.checked_reports()
    n = len(done)
    st.caption(f"Read the report below and choose the feeling and topic you think is right. The AI's answer stays "
               f"hidden so your choice is fair. Goal: {CHECK_GOAL} reports, target {TARGET:.0%} match.")
    st.progress(min(n / CHECK_GOAL, 1.0), text=f"{n} of {CHECK_GOAL} reports checked")

    nxt = db.next_report_to_check()
    if nxt:
        with st.container(border=True):
            st.markdown(f"**Report #{nxt['id']}** · "
                        f"{'End of shift' if nxt['report_type'] == 'end_of_shift' else 'Incident'}")
            st.markdown(f"<div style='font-size:1.05rem;margin:6px 0 10px'>{ui.esc(nxt['text'])}</div>",
                        unsafe_allow_html=True)
            with st.form(f"check_{nxt['id']}", border=False):
                c1, c2 = st.columns(2)
                sent = c1.radio("Feeling", SENTIMENTS, index=None, horizontal=True)
                cat = c2.selectbox("Topic", CATEGORIES, index=None, placeholder="Choose a topic")
                if st.form_submit_button("Save and show the next report", type="primary"):
                    if not sent or not cat:
                        st.error("Pick both a feeling and a topic.")
                    else:
                        db.save_check(nxt["id"], sent, cat, me)
                        st.rerun()
    elif n == 0:
        st.info("No reports with text yet. Come back after staff send some reports.")
    else:
        st.success("All reports with text have been checked.")

    if not n:
        return
    df = pd.DataFrame(done)
    df["sentiment_ok"] = df.sentiment == df.check_sentiment
    df["topic_ok"] = df.category == df.check_category
    df["both_ok"] = df.sentiment_ok & df.topic_ok
    st.markdown("#### Results so far")
    a, b, c = st.columns(3)
    with a:
        ui.plain_chart(charts.score_gauge(df.sentiment_ok.mean(), TARGET, "Feeling matches"), key="g_sent")
    with b:
        ui.plain_chart(charts.score_gauge(df.topic_ok.mean(), TARGET, "Topic matches"), key="g_topic")
    with c:
        ui.plain_chart(charts.score_gauge(df.both_ok.mean(), TARGET, "Both match"), key="g_both")
    by_ai = int(df.ai_provider.notna().sum())
    st.caption(f"Green line = {TARGET:.0%} target. {by_ai} of {n} checked report(s) were tagged by Gemini/Groq; "
               "the rest used basic keyword tagging because the AI was unavailable.")

    wrong = df[~df.both_ok]
    if len(wrong):
        with st.expander(f"Reports where the AI and the team disagreed ({len(wrong)})"):
            st.dataframe(wrong[["id", "text", "sentiment", "check_sentiment", "category", "check_category"]]
                         .rename(columns={"id": "#", "text": "Report", "sentiment": "AI feeling",
                                          "check_sentiment": "Team feeling", "category": "AI topic",
                                          "check_category": "Team topic"}), hide_index=True, width="stretch")
    out = df[["id", "created_at", "text", "sentiment", "check_sentiment", "sentiment_ok", "category",
              "check_category", "topic_ok", "ai_provider", "checked_by"]]
    c1, c2 = st.columns([1, 1])
    c1.download_button("Download check results (CSV)", out.to_csv(index=False).encode("utf-8"),
                       file_name=f"tagging_accuracy_{db.ph_today()}.csv", mime="text/csv",
                       icon=":material/download:")
    with c2.popover("Start over", icon=":material/restart_alt:"):
        st.write("This removes all team labels so you can check again.")
        if st.button("Yes, remove all labels", type="primary"):
            db.clear_checks(me)
            st.rerun()


@st.cache_data(ttl=120, show_spinner=False)
def _run_backtest(profile_json, obs):
    return forecaster.backtest(json.loads(profile_json), obs)


def _forecast():
    st.caption("Did the AI forecast the number of customers well? We replay the history day by day: for each day the "
               "AI forecasts using **only earlier days**, then we compare with what really happened. The same hours "
               "are scored three ways so the comparison is fair.")
    obs, rep = demand.clean_data()
    if obs.empty:
        st.info("No customer counts yet. They come from staff end-of-shift reports (customers in the hour) and from "
                "the owner's hourly data (Settings → Demand data). Results appear here automatically.")
        return
    profile = db.get_setting("hourly_profile")
    sm = forecaster.DemandForecaster(profile).fit(obs, loo=False).summary()
    a, b, c, d = st.columns(4)
    with a:
        ui.kpi("Hourly counts used", sm["n_obs"], f"after cleaning ({rep['invalid']} removed)")
    with b:
        ui.kpi("Days covered", sm["n_days"], f"{sm['first']:%b %d} – {sm['last']:%b %d}")
    with c:
        ui.kpi("Sources", f"{sm['n_staff']} staff · {sm['n_owner']} owner", "owner numbers win if both exist")
    with d:
        ui.kpi("Overall confidence", sm["confidence"],
               "Low: under 5 days or 40 counts", color={"High": ui.LEVEL_COLOR["Okay"], "Medium": ui.AMBER,
                                                         "Low": ui.RED}[sm["confidence"]])
    st.write("")
    res, sc = _run_backtest(json.dumps(profile, sort_keys=True), obs)
    if sc is None:
        st.info("The test needs counts from **at least 2 different days**. Come back after a second day of reports, "
                "or import the owner's data in Settings → Demand data.")
        return

    gain = sc["gain_vs_table"]
    if gain >= 0.05:
        st.success(f"The AI forecast was **{gain:.0%} more accurate** than the café default table "
                   f"(average mistake {sc['forecast']['mae']:.1f} vs. {sc['table']['mae']:.1f} customers per hour).")
    elif gain <= -0.05:
        st.warning(f"The AI forecast was not better than the café default table yet (average mistake "
                   f"{sc['forecast']['mae']:.1f} vs. {sc['table']['mae']:.1f}). This usually means there are too few "
                   "days of data. It improves as more days arrive.")
    else:
        st.info(f"The AI forecast and the café default table were about equally accurate (average mistake "
                f"{sc['forecast']['mae']:.1f} vs. {sc['table']['mae']:.1f}).")
    if sc["n"] < 100 or sc["days"] < 5:
        st.caption(f"Small sample: {sc['n']} hours over {sc['days']} tested day(s). Treat this result as early evidence.")

    k1, k2, k3, k4 = st.columns(4)
    with k1:
        ui.kpi("AI forecast: average mistake", f"{sc['forecast']['mae']:.1f}", "customers per hour (MAE)", color=ui.LIME)
    with k2:
        ui.kpi("Café table: average mistake", f"{sc['table']['mae']:.1f}", "customers per hour (MAE)")
    with k3:
        ui.kpi("AI forecast: within 20%", f"{sc['forecast']['within20']:.0%}", "of hours were close enough")
    with k4:
        ui.kpi("AI forecast: % error", f"{sc['forecast']['mape']:.0%}", "average (MAPE)")
    left, right = st.columns(2, gap="large")
    with left:
        ui.plain_chart(charts.forecast_error(sc), key="fc_err")
    with right:
        ui.plain_chart(charts.forecast_by_hour(res), key="fc_hour")
    st.caption("Left: the average mistake of each method (shorter is better). Right: bars = what really happened on "
               "average in each hour; the dotted amber line = the café default table; the green line = the AI forecast.")

    by_day = (res.assign(err_table=(res["table"] - res["actual"]).abs(), err_old=(res["old_avg"] - res["actual"]).abs(),
                         err_ai=(res["forecast"] - res["actual"]).abs())
              .groupby(["date", "weekday"], as_index=False)
              .agg(hours=("actual", "size"), table=("err_table", "mean"), old=("err_old", "mean"), ai=("err_ai", "mean")))
    by_day = by_day.rename(columns={"date": "Date", "weekday": "Day", "hours": "Hours tested", "table": "Café table mistake",
                                    "old": "Old average mistake", "ai": "AI forecast mistake"}).round(1)
    st.dataframe(by_day, hide_index=True, width="stretch")
    raw = res.rename(columns={"actual": "actual_customers", "table": "cafe_table", "old_avg": "old_same_weekday_avg",
                              "forecast": "ai_forecast"})
    c1, c2, _ = st.columns([1, 1, 2])
    c1.download_button("Day-by-day (CSV)", by_day.to_csv(index=False).encode("utf-8"),
                       file_name=f"forecast_accuracy_by_day_{db.ph_today()}.csv", mime="text/csv",
                       icon=":material/download:", width="stretch")
    c2.download_button("Every hour tested (CSV)", raw.to_csv(index=False).encode("utf-8"),
                       file_name=f"forecast_accuracy_hours_{db.ph_today()}.csv", mime="text/csv",
                       icon=":material/download:", width="stretch")
    st.caption("**Average mistake (MAE)**: how many customers off the forecast was, on average, in one hour. "
               "**Within 20%**: share of hours where the forecast was within 20% of the real count. "
               "**% error (MAPE)**: the average mistake as a percentage of the real count.")
