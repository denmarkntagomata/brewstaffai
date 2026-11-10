"""
demand.py - the shared Customer Demand Forecaster for the pages (Streamlit side of forecaster.py).

The fitted forecaster is cached for 2 minutes, so the Staffing Planner does not read the database on every click.
It is rebuilt automatically when the café defaults change, and right away after the owner's data is imported.
"""
import json

import streamlit as st

import db
import forecaster


def clean_data():
    """All counts (staff reports + owner import), cleaned. Returns (DataFrame, cleaning report)."""
    return forecaster.clean_observations(db.get_demand_observations(), max_date=db.ph_today())


@st.cache_data(ttl=120, show_spinner=False)
def _build(profile_json):
    obs, _ = clean_data()
    return forecaster.DemandForecaster(json.loads(profile_json)).fit(obs)


def get_forecaster():
    return _build(json.dumps(db.get_setting("hourly_profile"), sort_keys=True))


def refresh():
    _build.clear()
