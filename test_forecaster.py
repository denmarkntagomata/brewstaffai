"""
test_forecaster.py - checks the Customer Demand Forecaster without Streamlit or a database.

Run (inside the brewstaffai folder):
    python test_forecaster.py

Each line prints PASS or FAIL. These are the test cases for the forecaster (use them in Chapter 4).
"""
import io
import sys

import numpy as np
import pandas as pd

import forecaster as fc

PROFILE = {"8": 15, "9": 15, "10": 12, "11": 12, "12": 24, "13": 24, "14": 14, "15": 14,
           "16": 20, "17": 20, "18": 22, "19": 22, "20": 12, "21": 12}
RESULTS = []


def check(name, ok, detail=""):
    RESULTS.append(ok)
    print(f"{'PASS' if ok else 'FAIL'}  {name}" + (f"   ({detail})" if detail else ""))


def synthetic(days=28, weekend_boost=1.5, noise=2.0, seed=7, start="2026-09-07", source="owner"):
    """Pretend the real café is busier on Fri/Sat than the default table says."""
    rng = np.random.default_rng(seed)
    rows = []
    for d in pd.date_range(start, periods=days):
        if d.dayofweek == 6:
            continue
        boost = weekend_boost if d.dayofweek >= 4 else 1.0
        for h in range(8, 22):
            rows.append({"date": d, "hour": h, "customers": max(1, round(PROFILE[str(h)] * boost + rng.normal(0, noise))),
                         "source": source})
    return pd.DataFrame(rows)


def main():
    # 1 no data -> same as the café table
    f = fc.DemandForecaster(PROFILE).fit(fc.empty_observations())
    p = f.predict(0, 12)
    check("No data: forecast equals the café default", p["customers"] == 24 and p["confidence"] == "Low", str(p["customers"]))

    # 2 cleaning
    raw = pd.DataFrame({
        "date": ["2026-11-02", "2026-11-02", "2026-11-02", "bad date", "2026-11-03", "2026-11-03", "2026-12-30"],
        "hour": [9, 9, 10, 9, 25, 11, 9],
        "customers": [10, 20, 0, 12, 12, 400, 15],
        "source": ["staff", "staff", "staff", "staff", "staff", "staff", "staff"]})
    clean, rep = fc.clean_observations(raw, max_date="2026-11-10")
    check("Cleaning removes invalid rows (bad date, hour 25, 0 and 400 customers)", rep["invalid"] == 4, str(rep))
    check("Cleaning removes future dates", rep["future"] == 1, str(rep))
    check("Cleaning merges two staff values for the same hour into their average",
          len(clean) == 1 and clean.iloc[0]["customers"] == 15.0, str(clean.to_dict("records")))
    mix = pd.DataFrame({"date": ["2026-11-02"] * 2, "hour": [9, 9], "customers": [10, 30], "source": ["staff", "owner"]})
    c2, _ = fc.clean_observations(mix)
    check("Owner number wins over staff estimate for the same hour", len(c2) == 1 and c2.iloc[0]["customers"] == 30)
    e, r0 = fc.clean_observations(pd.DataFrame(columns=["date", "hour", "customers", "source"]))
    check("Empty input does not crash", e.empty and r0["kept"] == 0)

    # 3 learning: a busier weekend is learned
    data, _ = fc.clean_observations(synthetic(28))
    f = fc.DemandForecaster(PROFILE).fit(data)
    fri12, mon12 = f.predict(4, 12)["customers"], f.predict(0, 12)["customers"]
    check("Learns that Friday noon is busier than the default (24 -> about 36)", 31 <= fri12 <= 40, str(fri12))
    check("Keeps Monday noon close to the default (about 24)", 21 <= mon12 <= 27, str(mon12))
    check("Forecast is always inside 1..150", all(1 <= f.predict(w, h)["customers"] <= 150
                                                   for w in range(7) for h in range(0, 24)))
    p = f.predict(4, 12)
    check("Range brackets the forecast", p["low"] <= p["customers"] <= p["high"] and p["high"] - p["low"] >= 4, str(p))

    # 4 shrinkage: little data -> stays near the default
    tiny, _ = fc.clean_observations(synthetic(2, weekend_boost=3.0, start="2026-11-06"))
    f1 = fc.DemandForecaster(PROFILE).fit(tiny)
    p1 = f1.predict(4, 12)
    check("With only 2 days of data the forecast moves only part-way from the default",
          24 < p1["customers"] < 24 * 3 * 0.8, str(p1["customers"]))
    check("Low confidence when an hour has fewer than 3 observations", p1["confidence"] == "Low")
    check("High confidence once an hour has 8+ observations", f.predict(0, 12)["confidence"] == "High")
    check("Summary reports days and sources", f.summary()["n_days"] == 24 and f.summary()["n_owner"] == len(data))

    # 5 backtest: new method beats the table when the table is wrong
    res, s = fc.backtest(PROFILE, data)
    check("Backtest runs and scores every hour after day 1", s is not None and s["n"] == len(data) - 14, str(s and s["n"]))
    check("Forecaster beats the café table in the backtest", s["forecast"]["mae"] < s["table"]["mae"],
          f"MAE {s['forecast']['mae']:.2f} vs {s['table']['mae']:.2f}")
    check("Forecaster is at least as good as the old same-weekday average", s["forecast"]["mae"] <= s["old_avg"]["mae"] + 0.25,
          f"MAE {s['forecast']['mae']:.2f} vs {s['old_avg']['mae']:.2f}")
    check("Gain vs table is positive", s["gain_vs_table"] > 0.1, f"{s['gain_vs_table']:.0%}")

    # 5b a one-week pilot where the café is simply busier than the table says
    wk = synthetic(6, weekend_boost=1.0, noise=3, seed=11, start="2026-11-21")
    wk["customers"] = (wk["customers"] * 1.3).round()
    wk_clean, _ = fc.clean_observations(wk)
    _, s_wk = fc.backtest(PROFILE, wk_clean)
    check("One-week pilot (café 30% busier than the table): forecaster beats the table",
          s_wk["forecast"]["mae"] < s_wk["table"]["mae"], f"MAE {s_wk['forecast']['mae']:.2f} vs {s_wk['table']['mae']:.2f}")
    one_bad = synthetic(24, weekend_boost=1.0, noise=2, seed=1)
    one_bad.loc[one_bad["date"] == one_bad["date"].unique()[5], "customers"] *= 3
    f_bad = fc.DemandForecaster(PROFILE).fit(fc.clean_observations(one_bad)[0])
    check("One freak day (3x busy) among 24 days does not distort a normal Monday", 21 <= f_bad.predict(0, 12)["customers"] <= 28,
          str(f_bad.predict(0, 12)["customers"]))

    # 6 no leakage: changing the last day's numbers must not change that day's forecasts
    d2 = data.copy()
    last = d2["date"].max()
    d2.loc[d2["date"] == last, "customers"] = 99
    res2, _ = fc.backtest(PROFILE, d2)
    a = res[res["date"] == last.date()]["forecast"].tolist()
    b = res2[res2["date"] == last.date()]["forecast"].tolist()
    check("Backtest has no leakage (a day is forecast only from earlier days)", a == b and len(a) > 0)

    # 7 backtest with too little history
    res3, s3 = fc.backtest(PROFILE, data[data["date"] == data["date"].min()])
    check("Backtest with one day returns no score instead of crashing", s3 is None and res3.empty)

    # 8 honest when the table is already right
    right, _ = fc.clean_observations(synthetic(28, weekend_boost=1.0, noise=2.0, seed=3))
    _, s_ok = fc.backtest(PROFILE, right)
    check("When the table is already right, the forecaster is not much worse", s_ok["forecast"]["mae"] <= s_ok["table"]["mae"] + 0.5,
          f"MAE {s_ok['forecast']['mae']:.2f} vs {s_ok['table']['mae']:.2f}")

    # 9 hour parsing
    cases = {13: 13, "13": 13, "13:00": 13, "13:00-14:00": 13, "1 PM": 13, "1:00 PM": 13, "1pm": 13, "12 AM": 0,
             "12 PM": 12, "8:00 AM - 9:00 AM": 8, 9.0: 9, "25": None, "abc": None, "13:00:00": 13, 24: None}
    bad = {k: fc.parse_hour(k) for k, v in cases.items() if fc.parse_hour(k) != v}
    check("Hour formats are understood (13, 13:00, 1 PM, 8:00 AM - 9:00 AM ...)", not bad, str(bad))
    check("A time object gives its hour", fc.parse_hour(pd.Timestamp("2026-11-02 15:30")) == 15)

    # 10 importing the owner's file
    csv1 = "Date,Hour,Customers\n11/02/2026,8:00 AM,14\n11/02/2026,9:00 AM,17\n11/03/2026,8:00 AM,x\n"
    obs, info = fc.parse_owner_table(pd.read_csv(io.StringIO(csv1)))
    check("Counts file: reads rows and skips the bad one", len(obs) == 2 and info["bad_rows"] == 1 and info["shape"] == "counts", str(info))
    csv2 = "date,time,sales\n2026-11-02,08:00,\"₱1,500.00\"\n2026-11-02,09:00,2400\n"
    try:
        fc.parse_owner_table(pd.read_csv(io.StringIO(csv2)))
        check("Sales file without average spend asks for it", False)
    except fc.NeedsAverageSpend:
        check("Sales file without average spend asks for it", True)
    obs, info = fc.parse_owner_table(pd.read_csv(io.StringIO(csv2)), avg_spend=150)
    check("Sales file: pesos / average spend = customers (1500/150 = 10, 2400/150 = 16)",
          obs["customers"].tolist() == [10, 16], str(obs["customers"].tolist()))
    csv3 = "timestamp,receipt_no\n2026-11-02 08:05:00,1\n2026-11-02 08:40:00,2\n2026-11-02 09:10:00,3\n"
    obs, info = fc.parse_owner_table(pd.read_csv(io.StringIO(csv3)))
    check("Receipt-per-row file: receipts are counted per hour", obs["customers"].tolist() == [2, 1] and info["shape"] == "transactions", str(obs.to_dict("records")))
    obs, _ = fc.parse_owner_table(pd.read_csv(io.StringIO("date,hour,customers\n02/11/2026,9,5\n")), dayfirst=True)
    check("Day/Month/Year option reads 02/11/2026 as 2 November", obs.iloc[0]["date"] == pd.Timestamp("2026-11-02"))
    try:
        fc.parse_owner_table(pd.read_csv(io.StringIO("name,age\nA,3\n")))
        check("Unknown columns give a friendly error", False)
    except ValueError as ex:
        check("Unknown columns give a friendly error", "date column" in str(ex))
    check("The downloadable template can be read back by the importer",
          len(fc.parse_owner_table(pd.read_csv(io.StringIO(fc.TEMPLATE_CSV)))[0]) == 5)
    big = pd.DataFrame({"date": ["2026-01-01"] * 3, "hour": [8, 9, 10], "customers": [1, 2, 3]})
    check("Duplicate rows for the same hour are added together", fc.parse_owner_table(pd.concat([big, big]))[0]["customers"].tolist() == [2, 4, 6])

    print(f"\n{sum(RESULTS)} of {len(RESULTS)} checks passed.")
    return 0 if all(RESULTS) else 1


if __name__ == "__main__":
    sys.exit(main())
