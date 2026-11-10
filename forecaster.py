"""
forecaster.py - Customer Demand Forecaster (new in v4.3.0)

What it does
  Predicts how many customers Jungle Brew will have in a given hour (weekday + hour of day),
  so the Staffing Planner no longer depends on a fixed placeholder table.

How it learns (Level 2 machine learning: regression)
  * The café's default table (Settings -> Café defaults) is the starting guess ("prior").
  * A Ridge regression learns CORRECTIONS to that guess from real counts, as a percentage of the default:
        customers / default - 1  =  overall effect + hour-of-day effect + weekday effect
    (Busier-than-expected days tend to be busier by a percentage, not by a fixed number of people.)
  * Ridge shrinks the corrections toward zero when there is little data, so with only a few days of
    counts the forecast stays close to the café defaults, and it moves toward the real pattern as
    more days arrive. This is how it stays safe with a one-week pilot.

Data it learns from (cleaned first: out-of-range values removed, duplicates merged)
  * Staff end-of-shift reports ("about how many customers in that hour?")
  * The owner's hourly counts or sales, imported in Settings -> Demand data
  If both exist for the same date and hour, the owner's number is used.

How it is tested
  backtest() replays history day by day. For every day it forecasts using ONLY earlier days, then
  compares with what really happened. It scores three methods on the same hours:
  the café default table, the old same-weekday average (v4.2.1), and this forecaster.

This file does not need Streamlit or a database, so it can be tested on its own (test_forecaster.py).
"""
import re

import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge

ALPHA = 4.0                 # how strongly the forecast is pulled toward the café defaults
MIN_VALID, MAX_VALID = 1, 300       # a count outside this range is treated as a typing mistake
PLANNER_MAX = 150           # the planner never uses more than this many customers in an hour
DEFAULT_PRIOR = 15
MAX_IMPORT_HOURS = 6000     # one import file can hold up to about 1 year of hourly rows
LEVELS = ("Low", "Medium", "High")


# ---------------------------------------------------------------- cleaning
def empty_observations():
    return pd.DataFrame({"date": pd.Series(dtype="datetime64[ns]"), "hour": pd.Series(dtype="int64"),
                         "customers": pd.Series(dtype="float64"), "source": pd.Series(dtype="object")})


def clean_observations(df, max_date=None):
    """Input columns: date, hour, customers, source ('staff' or 'owner').
    Returns (clean_df, report). Rows that are invalid are dropped, duplicates for the same date and hour are
    merged (owner numbers win over staff estimates; several values from the same source are averaged)."""
    report = {"received": 0 if df is None else len(df), "invalid": 0, "future": 0, "merged": 0, "kept": 0}
    if df is None or len(df) == 0:
        return empty_observations(), report
    d = df[["date", "hour", "customers", "source"]].copy()
    d["date"] = pd.to_datetime(d["date"], errors="coerce").dt.normalize()
    d["hour"] = pd.to_numeric(d["hour"], errors="coerce")
    d["customers"] = pd.to_numeric(d["customers"], errors="coerce")
    ok = (d["date"].notna() & d["hour"].between(0, 23) & (d["hour"] == d["hour"].round())
          & d["customers"].between(MIN_VALID, MAX_VALID))
    report["invalid"] = int((~ok).sum())
    d = d[ok]
    if max_date is not None:
        future = d["date"] > pd.Timestamp(max_date)
        report["future"] = int(future.sum())
        d = d[~future]
    d = d.assign(hour=d["hour"].astype(int))
    keys = ["date", "hour"]
    owner = d[d["source"] == "owner"].groupby(keys)["customers"].mean().reset_index().assign(source="owner")
    staff = d[d["source"] != "owner"].groupby(keys)["customers"].mean().reset_index().assign(source="staff")
    if len(owner) and len(staff):
        taken = pd.MultiIndex.from_frame(owner[keys])
        staff = staff[~pd.MultiIndex.from_frame(staff[keys]).isin(taken)]
    out = pd.concat([owner, staff], ignore_index=True)
    report["merged"] = int(len(d) - len(out))
    report["kept"] = int(len(out))
    if out.empty:
        return empty_observations(), report
    out = out.sort_values(keys).reset_index(drop=True)
    return out[["date", "hour", "customers", "source"]], report


# ---------------------------------------------------------------- model
# Day-level effects (overall level and weekday) are learned from whole days, and one day is one piece of
# evidence however many hours it has (one rainy Friday is not "all Fridays"). A smaller column scale means a
# stronger pull toward the café defaults, so these effects need several days of data before they count much.
SCALE_GLOBAL, SCALE_HOUR, SCALE_WEEKDAY = 0.35, 0.6, 0.5


def _features(weekdays, hours):
    weekdays = np.asarray(weekdays, dtype=int)
    hours = np.asarray(hours, dtype=int)
    x = np.zeros((len(hours), 1 + 24 + 7))
    rows = np.arange(len(hours))
    x[:, 0] = SCALE_GLOBAL
    x[rows, 1 + hours] = SCALE_HOUR
    x[rows, 25 + weekdays] = SCALE_WEEKDAY
    return x


class DemandForecaster:
    def __init__(self, profile=None, alpha=ALPHA):
        self.profile = {}
        for k, v in (profile or {}).items():
            try:
                self.profile[int(k)] = float(v)
            except (TypeError, ValueError):
                continue
        self.alpha = alpha
        self.obs = empty_observations()
        self.model = None
        self.loo_abs = np.array([])
        self.n_by_hour = {}

    def prior(self, hour):
        """The café's default guess for this hour (nearest listed hour if this one is not in the table)."""
        hour = int(hour)
        if hour in self.profile:
            return self.profile[hour]
        if self.profile:
            return self.profile[min(self.profile, key=lambda h: abs(h - hour))]
        return float(DEFAULT_PRIOR)

    def fit(self, obs, loo=True):
        self.obs = obs.reset_index(drop=True) if obs is not None else empty_observations()
        self.model, self.loo_abs, self.n_by_hour = None, np.array([]), {}
        if self.obs.empty:
            return self
        hours = self.obs["hour"].astype(int).values
        x = _features(self.obs["date"].dt.dayofweek.values, hours)
        prior = np.array([self.prior(h) for h in hours])
        y = self.obs["customers"].values / prior - 1.0          # how far above/below the default, in %
        self.model = Ridge(alpha=self.alpha, fit_intercept=False).fit(x, y)
        self.n_by_hour = self.obs.groupby("hour").size().to_dict()
        if loo:
            # Leave-one-out error of a ridge model has a closed form: residual / (1 - leverage).
            inv = np.linalg.inv(x.T @ x + self.alpha * np.eye(x.shape[1]))
            leverage = np.einsum("ij,jk,ik->i", x, inv, x)
            resid = y - x @ self.model.coef_
            self.loo_abs = np.abs(resid / (1.0 - leverage)) * prior      # back to "customers"
        return self

    def predict(self, weekday, hour):
        """Forecast for one weekday (Mon=0 ... Sun=6) and hour (0-23)."""
        hour, weekday = int(hour), int(weekday)
        base = self.prior(hour)
        raw = base
        if self.model is not None:
            raw = base * (1.0 + float(self.model.predict(_features([weekday], [hour]))[0]))
        pred = int(min(PLANNER_MAX, max(1, round(raw))))
        n_hour = int(self.n_by_hour.get(hour, 0))
        conf = "High" if n_hour >= 8 else "Medium" if n_hour >= 3 else "Low"
        if len(self.loo_abs) >= 8:
            margin = float(np.quantile(self.loo_abs, 0.8))
        else:
            margin = 0.30 * pred
        if conf == "Low":
            margin = max(margin, 0.25 * pred)
        margin = int(np.ceil(max(2.0, margin)))
        return {"customers": pred, "low": max(1, pred - margin), "high": min(PLANNER_MAX, pred + margin),
                "prior": int(round(base)), "n_hour": n_hour, "confidence": conf,
                "learned": n_hour > 0, "change": pred - int(round(base))}

    def summary(self):
        o = self.obs
        if o.empty:
            return {"n_obs": 0, "n_days": 0, "n_owner": 0, "n_staff": 0, "first": None, "last": None,
                    "confidence": "Low"}
        n, days = len(o), int(o["date"].nunique())
        conf = "High" if n >= 150 and days >= 14 else "Medium" if n >= 40 and days >= 5 else "Low"
        return {"n_obs": n, "n_days": days, "n_owner": int((o["source"] == "owner").sum()),
                "n_staff": int((o["source"] != "owner").sum()), "first": o["date"].min().date(),
                "last": o["date"].max().date(), "confidence": conf}


# ---------------------------------------------------------------- backtest (the evidence for Chapter 4)
METHODS = {"table": "Café default table", "old_avg": "Same-weekday average (v4.2.1)", "forecast": "Demand forecaster (v4.3.0)"}


def backtest(profile, obs):
    """Day-ahead walk-forward test. Returns (per-hour DataFrame, summary dict or None).
    The first day only trains the model; every later day is forecast from earlier days alone."""
    if obs is None or obs.empty or obs["date"].nunique() < 2:
        return pd.DataFrame(), None
    dates = sorted(obs["date"].unique())
    rows = []
    for d in dates[1:]:
        train, test = obs[obs["date"] < d], obs[obs["date"] == d]
        f = DemandForecaster(profile).fit(train, loo=False)
        same_wd = (train.assign(wd=train["date"].dt.dayofweek).groupby(["wd", "hour"])["customers"].mean())
        wd = pd.Timestamp(d).dayofweek
        for r in test.itertuples():
            table = int(round(f.prior(r.hour)))
            old = int(round(same_wd.get((wd, r.hour), table)))
            rows.append({"date": pd.Timestamp(d).date(), "weekday": pd.Timestamp(d).strftime("%a"), "hour": int(r.hour),
                         "actual": float(r.customers), "table": table, "old_avg": old,
                         "forecast": f.predict(wd, r.hour)["customers"], "source": r.source})
    res = pd.DataFrame(rows)
    return res, score(res)


def score(res):
    if res is None or res.empty:
        return None
    out = {"n": int(len(res)), "days": int(res["date"].nunique())}
    for m in METHODS:
        err = (res[m] - res["actual"]).abs()
        out[m] = {"mae": float(err.mean()), "rmse": float(np.sqrt(((res[m] - res["actual"]) ** 2).mean())),
                  "mape": float((err / res["actual"]).mean()), "within20": float((err <= 0.2 * res["actual"]).mean())}
    t, o, f = out["table"]["mae"], out["old_avg"]["mae"], out["forecast"]["mae"]
    out["gain_vs_table"] = (1 - f / t) if t > 0 else 0.0
    out["gain_vs_old"] = (1 - f / o) if o > 0 else 0.0
    return out


# ---------------------------------------------------------------- importing the owner's file
class NeedsAverageSpend(ValueError):
    """The file has peso sales but no customer counts, so an average spend per customer is needed."""


def _norm(name):
    return re.sub(r"[^a-z0-9]", "", str(name).lower())


_DATE = {"date", "day", "saledate", "salesdate", "businessdate", "transactiondate", "orderdate"}
_HOUR = {"hour", "time", "timeslot", "hourslot", "hr", "timeperiod", "hourofday"}
_COUNT = {"customers", "customer", "customercount", "transactions", "transaction", "orders", "order",
          "ordercount", "count", "guests", "pax", "covers", "receipts", "tickets", "numberofcustomers"}
_SALES = {"sales", "amount", "revenue", "totalsales", "grosssales", "netsales", "salesphp", "salesamount",
          "totalamount", "total"}
_STAMP = {"datetime", "timestamp", "datetimeofsale", "createdat", "ordertime", "transactiontime", "saletime"}


def _find(cols, names):
    for c in cols:
        if _norm(c) in names:
            return c
    return None


def parse_hour(value):
    """13, '13', '13:00', '13:00-14:00', '1 PM', '1:00 PM' -> 13. Anything else -> None."""
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return None
    if isinstance(value, (pd.Timestamp,)) or hasattr(value, "hour") and not isinstance(value, (int, float, str)):
        return int(value.hour)
    if isinstance(value, (int, np.integer)):
        return int(value) if 0 <= value <= 23 else None
    if isinstance(value, (float, np.floating)):
        return int(value) if float(value).is_integer() and 0 <= value <= 23 else None
    s = re.split(r"\s*[-–—]\s*|\s+to\s+", str(value).strip().lower())[0].strip()
    m = re.match(r"^(\d{1,2})(?::\d{2}(?::\d{2})?)?\s*([ap])\.?m?\.?$", s) or re.match(r"^(\d{1,2})(?::\d{2}(?::\d{2})?)?$", s)
    if not m:
        return None
    h = int(m.group(1))
    if len(m.groups()) > 1 and m.group(2):
        if not 1 <= h <= 12:
            return None
        h = h % 12 + (12 if m.group(2) == "p" else 0)
    return h if 0 <= h <= 23 else None


def parse_owner_table(df, avg_spend=None, dayfirst=False):
    """Turns the owner's file into hourly customer counts.
    Accepted shapes (column names are matched loosely, upper or lower case):
      1. date + hour + customers/transactions/orders      -> used as counts
      2. date + hour + sales (pesos)                       -> needs avg_spend (pesos per customer)
      3. one date-and-time column, one row per receipt     -> receipts are counted per hour
    Returns (observations DataFrame[date, hour, customers], info dict). Raises ValueError with a plain message."""
    if df is None or df.empty:
        raise ValueError("The file is empty.")
    cols = list(df.columns)
    c_date, c_hour = _find(cols, _DATE), _find(cols, _HOUR)
    c_count, c_sales, c_stamp = _find(cols, _COUNT), _find(cols, _SALES), _find(cols, _STAMP)
    info = {"rows_in": int(len(df)), "bad_rows": 0, "shape": "", "avg_spend": None}

    if c_date is not None and c_hour is not None and (c_count is not None or c_sales is not None):
        use_count = c_count is not None
        info["shape"] = "counts" if use_count else "sales"
        if not use_count:
            if not avg_spend or avg_spend <= 0:
                raise NeedsAverageSpend("This file has sales in pesos but no customer counts.")
            info["avg_spend"] = float(avg_spend)
        value = pd.to_numeric(df[c_count if use_count else c_sales].astype(str).str.replace(r"[₱,\s]|php", "", regex=True,
                                                                                       case=False), errors="coerce")
        work = pd.DataFrame({"date": pd.to_datetime(df[c_date], errors="coerce", dayfirst=dayfirst),
                             "hour": df[c_hour].map(parse_hour), "value": value})
        good = work["date"].notna() & work["hour"].notna() & work["value"].notna() & (work["value"] >= 0)
        info["bad_rows"] = int((~good).sum())
        work = work[good]
        work = work.assign(date=work["date"].dt.normalize())
        agg = work.groupby(["date", "hour"])["value"].sum().reset_index()
        agg["customers"] = agg["value"] if use_count else (agg["value"] / float(avg_spend))
    elif c_stamp is not None or (c_hour is None and c_date is not None and
                                 pd.to_datetime(df[c_date], errors="coerce").dt.hour.gt(0).any()):
        col = c_stamp if c_stamp is not None else c_date
        info["shape"] = "transactions"
        stamp = pd.to_datetime(df[col], errors="coerce", dayfirst=dayfirst)
        info["bad_rows"] = int(stamp.isna().sum())
        stamp = stamp.dropna()
        agg = (pd.DataFrame({"date": stamp.dt.normalize(), "hour": stamp.dt.hour}).groupby(["date", "hour"])
               .size().rename("customers").reset_index())
    else:
        raise ValueError("I could not find the columns I need. The file needs a date column, an hour column, and a "
                         "customers column (or a sales column). Use the template below.")

    agg = agg[["date", "hour", "customers"]].copy()
    agg["customers"] = agg["customers"].round().astype(int)
    agg["hour"] = agg["hour"].astype(int)
    if agg.empty:
        raise ValueError("No usable rows were found. Check that the dates and hours are written clearly.")
    if len(agg) > MAX_IMPORT_HOURS:
        raise ValueError(f"The file has {len(agg):,} hours. Please import at most {MAX_IMPORT_HOURS:,} hours at a time.")
    info["hours"] = int(len(agg))
    return agg.sort_values(["date", "hour"]).reset_index(drop=True), info


TEMPLATE_CSV = ("date,hour,customers\n2026-11-02,08:00,14\n2026-11-02,09:00,17\n2026-11-02,10:00,12\n"
                "2026-11-02,11:00,13\n2026-11-02,12:00,26\n")
