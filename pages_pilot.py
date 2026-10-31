"""
pages_pilot.py - Pilot Results page for the paper and the defense.
  Tab 1: AI prediction vs. what staff felt, day by day.
  Tab 2: tagging accuracy check (team hand-labels reports without seeing the AI tags).
"""
from datetime import date, timedelta

import pandas as pd
import streamlit as st

import charts
import db
import ui
from ai_helper import CATEGORIES, SENTIMENTS
from labels import CLASSES

PILOT_START, PILOT_END = date(2026, 11, 21), date(2026, 11, 28)
CHECK_GOAL = 50
TARGET = 0.80


def pilot_results():
    ui.page_header("Pilot Results",
                   "How well the AI matched real shifts during the pilot week, and how accurate its report tags are.")
    t1, t2 = st.tabs(["AI vs. staff", "Check AI tags"])
    with t1:
        _agreement()
    with t2:
        _tag_check()


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
        st.info("No end-of-shift reports for these dates yet. This page fills in as staff send reports.")
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
    st.write("")

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
    st.caption(f"A teammate reads each report **without seeing the AI's tags** and picks the right feeling and "
               f"topic. The app then compares the two. Goal: {CHECK_GOAL} reports, target {TARGET:.0%} match.")
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
