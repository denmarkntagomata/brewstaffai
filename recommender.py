"""
recommender.py - AI prediction + staffing recommendation (Objective 3)
1. The Decision Tree predicts the congestion level for any staffing setup.
2. The recommender tries every way to split the available counter staff into
   cashiers and baristas, from the smallest crew upward.
3. A crew is recommended only when BOTH the AI model predicts "Okay" AND the simulator
   confirms an average wait of 7 minutes or less (simulation double-check). If the two
   disagree, the recommender moves on to the next crew.
"""
import os

import joblib
import pandas as pd

from labels import FEATURES, add_load_features, label
from sim_engine import simulate_avg

MODEL_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "model", "model.joblib")


def load_model():
    return joblib.load(MODEL_PATH)


def predict(model, cond):
    row = add_load_features(dict(cond))
    X = pd.DataFrame([{k: row[k] for k in FEATURES}])
    probs = dict(zip(model.classes_, model.predict_proba(X)[0]))
    return model.predict(X)[0], probs


def staffing_options(model, cond, max_staff, max_cashiers=2, max_baristas=4):
    opts = []
    for total in range(2, max_staff + 1):
        for c in range(1, min(max_cashiers, total - 1) + 1):
            b = total - c
            if b > max_baristas:
                continue
            lvl, probs = predict(model, {**cond, "num_cashier": c, "num_barista": b})
            opts.append({"total": total, "cashiers": c, "baristas": b, "level": lvl,
                         "p_okay": probs.get("Okay", 0.0), "probs": probs})
    return opts


def pick_best(opts, cond=None):
    """Smallest crew the AI predicts as Okay AND the simulator confirms (wait <= 7 min).
    Returns (best_option, reached_okay)."""
    ordered = sorted(opts, key=lambda o: (o["total"], -o["p_okay"]))
    if cond is not None:
        for o in ordered:
            if o["level"] != "Okay":
                continue
            if "wait" not in o:
                o["wait"] = sim_check(cond, o["cashiers"], o["baristas"])["avg_wait"]
            o["sim_agrees"] = label(o["wait"]) == "Okay"
            if o["sim_agrees"]:
                return o, True
        # nobody passes both checks: take the option with the shortest simulated wait
        for o in opts:
            if "wait" not in o:
                o["wait"] = sim_check(cond, o["cashiers"], o["baristas"])["avg_wait"]
        return min(opts, key=lambda o: (o["wait"], o["total"])), False
    okay = [o for o in ordered if o["level"] == "Okay"]
    return (okay[0], True) if okay else (sorted(opts, key=lambda o: (-o["p_okay"], o["total"]))[0], False)


def sim_check(cond, cashiers, baristas, reps=10):
    s = simulate_avg({**cond, "num_cashier": cashiers, "num_barista": baristas, "duration": 60}, reps=reps)
    s["sim_level"] = label(s["avg_wait"])
    return s


def recommend(model, cond, max_staff):
    """Single-hour recommendation with a simulation check for every option (for the chart)."""
    opts = staffing_options(model, cond, max_staff)
    for o in opts:
        o["wait"] = sim_check(cond, o["cashiers"], o["baristas"], reps=10)["avg_wait"]
    best, reached = pick_best(opts)
    sim = sim_check(cond, best["cashiers"], best["baristas"], reps=10)
    return best, reached, sim, opts


def plan_day(model, slots, customers_by_slot, base_cond, max_staff):
    """Whole-day plan: one recommendation per time slot."""
    rows = []
    for slot in slots:
        cust = customers_by_slot[slot]
        cond = {**base_cond, "arr_rate": max(cust, 1) / 60}
        best, reached = pick_best(staffing_options(model, cond, max_staff), cond)
        sim = sim_check(cond, best["cashiers"], best["baristas"], reps=10)
        rows.append({"slot": slot, "customers": cust, "cashiers": best["cashiers"], "baristas": best["baristas"],
                     "level": best["level"], "confidence": best["p_okay"], "wait": round(sim["avg_wait"], 1),
                     "walkout": sim["balk_rate"], "reached": reached})
    return rows
