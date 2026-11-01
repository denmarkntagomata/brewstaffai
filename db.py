"""
db.py - BrewStaffAI database layer.

Cloud mode: DATABASE_URL in Streamlit secrets -> shared Neon PostgreSQL database.
Local mode: no DATABASE_URL -> data/brewstaff.db (SQLite) on this computer only.

Passwords are salted PBKDF2-SHA256 hashes. All times are Philippine time (UTC+8).
"""
import hashlib
import io
import json
import os
import secrets
import shutil
import zipfile
from datetime import datetime, timedelta, timezone

import pandas as pd
import sqlalchemy as sa

import auth

BASE = os.path.dirname(os.path.abspath(__file__))
SQLITE_PATH = os.path.join(BASE, "data", "brewstaff.db")
PH_TZ = timezone(timedelta(hours=8))
FMT = "%Y-%m-%d %H:%M:%S"

ARCHIVE_DAYS = 30
EDIT_HOURS = 24

DEFAULT_SETTINGS = {
    # Placeholder until the re-observation (about 24 customers/hour at the observed noon peak)
    "hourly_profile": {"8": 15, "9": 15, "10": 12, "11": 12, "12": 24, "13": 24, "14": 14, "15": 14,
                       "16": 20, "17": 20, "18": 22, "19": 22, "20": 12, "21": 12},
    "service_times": {"cashier": 1.0, "simple": 2.0, "complex": 4.5, "p_simple": 0.40},
    "max_counter_staff": 4,
}


# time
def ph_now():
    return datetime.now(PH_TZ).replace(tzinfo=None)


def ph_today():
    return ph_now().date()


def now():
    return ph_now().strftime(FMT)


def _ago(**kw):
    return (ph_now() - timedelta(**kw)).strftime(FMT)


# connection
def secret(name):
    try:
        import streamlit as st
        if name in st.secrets:
            return st.secrets[name]
    except Exception:
        pass
    return os.environ.get(name)


def _database_url():
    url = (secret("DATABASE_URL") or "").strip()
    if not url:
        return None
    for prefix in ("postgres://", "postgresql://"):
        if url.startswith(prefix):
            return "postgresql+psycopg2://" + url[len(prefix):]
    return url


_ENGINE = None
_READY = False
_LAST_CLEANUP = None


def engine():
    global _ENGINE
    if _ENGINE is None:
        url = _database_url()
        if url:
            # Neon sleeps after 5 idle minutes; pre_ping reconnects quietly.
            _ENGINE = sa.create_engine(url, pool_pre_ping=True, pool_recycle=240, pool_size=3, max_overflow=2,
                                       connect_args={"connect_timeout": 10})
        else:
            os.makedirs(os.path.dirname(SQLITE_PATH), exist_ok=True)
            _ENGINE = sa.create_engine(f"sqlite:///{SQLITE_PATH}", connect_args={"check_same_thread": False})
    return _ENGINE


def backend():
    return "cloud" if engine().dialect.name == "postgresql" else "local"


def backend_info():
    e = engine()
    if e.dialect.name == "postgresql":
        host = e.url.host or ""
        return {"mode": "cloud", "label": "Cloud database (shared)",
                "where": host.split(".")[0] + "…" if host else "cloud"}
    return {"mode": "local", "label": "Local database (this computer only)", "where": "data/brewstaff.db"}


def friendly_error(exc):
    """Turns a database exception into a message a non-programmer can act on."""
    msg = str(exc).lower()
    if "password authentication failed" in msg:
        return ("Can't connect to the database: wrong password. Copy the connection string from Neon again "
                "(click **Show password** first) and paste it as DATABASE_URL in Secrets.")
    if "could not translate host name" in msg or "name or service not known" in msg or "nodename" in msg:
        return ("Can't connect to the database: the address in DATABASE_URL is wrong. "
                "Copy the full connection string from Neon again.")
    if "does not exist" in msg and "database" in msg:
        return "Can't connect to the database: the database name at the end of DATABASE_URL is wrong."
    if "timeout" in msg or "timed out" in msg or "connection refused" in msg or "server closed" in msg:
        return ("Can't reach the database right now. Check your internet connection. "
                "If Neon was asleep, wait a few seconds and press Try again.")
    if isinstance(exc, sa.exc.ArgumentError) or "could not parse" in msg or "invalid dsn" in msg:
        return ("DATABASE_URL is not written correctly. It should start with postgresql:// and be inside quotes "
                "in Secrets.")
    if "ssl" in msg:
        return "Secure connection to the database failed. Make sure DATABASE_URL ends with ?sslmode=require."
    return "Something went wrong with the database. Please try again in a moment."


def _rows(sql, **params):
    with engine().connect() as c:
        return [dict(r._mapping) for r in c.execute(sa.text(sql), params)]


def _one(sql, **params):
    rows = _rows(sql, **params)
    return rows[0] if rows else None


def _exec(sql, **params):
    with engine().begin() as c:
        return c.execute(sa.text(sql), params).rowcount


def ping():
    start = datetime.now()
    try:
        with engine().connect() as c:
            c.execute(sa.text("SELECT 1"))
        return True, int((datetime.now() - start).total_seconds() * 1000)
    except Exception:
        return False, None


# passwords
def hash_pw(password, salt=None):
    salt = salt or secrets.token_hex(16)
    h = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 200_000).hex()
    return f"{salt}${h}"


def check_pw(password, stored):
    salt, _ = stored.split("$", 1)
    return secrets.compare_digest(hash_pw(password, salt), stored)


# setup
# Columns added after v3. Existing databases get them through ALTER TABLE.
NEW_COLS = {
    "reports": {
        "edited_at": "TEXT",
        "seen_by_manager": "INTEGER DEFAULT 0",
        "reply": "TEXT", "replied_by": "TEXT", "replied_at": "TEXT",
        "reply_seen": "INTEGER DEFAULT 1",
        "archived_at": "TEXT", "archived_by": "TEXT", "archive_reason": "TEXT",
        "check_sentiment": "TEXT", "check_category": "TEXT", "checked_by": "TEXT", "checked_at": "TEXT",
    },
    "plans": {"ai_cashiers": "INTEGER", "ai_baristas": "INTEGER"},
    "users": {"privacy_version": "TEXT", "privacy_at": "TEXT"},
}


def init_db():
    global _READY
    if _READY:
        return
    e = engine()
    if e.dialect.name == "sqlite" and os.path.exists(SQLITE_PATH):
        cols = [r["name"] for r in _rows("PRAGMA table_info(users)")]
        if cols and "email" not in cols:
            e.dispose()
            shutil.move(SQLITE_PATH, SQLITE_PATH.replace(".db", "_v1_backup.db"))
    serial = "SERIAL PRIMARY KEY" if e.dialect.name == "postgresql" else "INTEGER PRIMARY KEY AUTOINCREMENT"
    ddl = [
        """CREATE TABLE IF NOT EXISTS users(
            email TEXT PRIMARY KEY, full_name TEXT NOT NULL,
            role TEXT NOT NULL CHECK(role IN ('manager','staff')),
            pw_hash TEXT NOT NULL, active INTEGER DEFAULT 1, must_change INTEGER DEFAULT 0,
            failed INTEGER DEFAULT 0, locked_until TEXT, created_at TEXT, last_login TEXT)""",
        f"""CREATE TABLE IF NOT EXISTS reports(
            id {serial}, user_email TEXT NOT NULL, created_at TEXT NOT NULL,
            report_type TEXT NOT NULL, report_date TEXT, time_slot TEXT, customers INTEGER,
            cashiers INTEGER, baristas INTEGER, reported_level TEXT, predicted_level TEXT,
            text TEXT, sentiment TEXT, category TEXT, ai_summary TEXT, ai_provider TEXT,
            status TEXT DEFAULT 'Open')""",
        f"""CREATE TABLE IF NOT EXISTS plans(
            id {serial}, created_at TEXT, plan_date TEXT, time_slot TEXT,
            customers INTEGER, cashiers INTEGER, baristas INTEGER, predicted_level TEXT,
            expected_wait REAL, ai_insight TEXT, created_by TEXT)""",
        "CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY, value TEXT)",
        f"""CREATE TABLE IF NOT EXISTS audit(
            id {serial}, at TEXT NOT NULL, actor TEXT, action TEXT NOT NULL, detail TEXT)""",
        f"""CREATE TABLE IF NOT EXISTS timings(
            id {serial}, at TEXT NOT NULL, kind TEXT NOT NULL, seconds REAL NOT NULL)""",
        """CREATE TABLE IF NOT EXISTS sessions(
            token_hash TEXT PRIMARY KEY, email TEXT NOT NULL, created_at TEXT, last_seen TEXT)""",
        "CREATE INDEX IF NOT EXISTS idx_reports_created ON reports(created_at)",
        "CREATE INDEX IF NOT EXISTS idx_plans_date ON plans(plan_date)",
        "CREATE INDEX IF NOT EXISTS idx_audit_at ON audit(at)",
    ]
    with e.begin() as c:
        for stmt in ddl:
            c.execute(sa.text(stmt))
    inspector = sa.inspect(e)
    with e.begin() as c:
        for table, cols in NEW_COLS.items():
            existing = {col["name"] for col in inspector.get_columns(table)}
            for name, kind in cols.items():
                if name not in existing:
                    c.execute(sa.text(f"ALTER TABLE {table} ADD COLUMN {name} {kind}"))
                    if name == "seen_by_manager":
                        c.execute(sa.text("UPDATE reports SET seen_by_manager=1"))
    _READY = True
    cleanup()


def cleanup(force=False):
    """Deletes archived reports older than ARCHIVE_DAYS and stale login sessions. Runs at most hourly."""
    global _LAST_CLEANUP
    if not force and _LAST_CLEANUP and datetime.now() - _LAST_CLEANUP < timedelta(hours=1):
        return 0
    _LAST_CLEANUP = datetime.now()
    n = _exec("DELETE FROM reports WHERE archived_at IS NOT NULL AND archived_at < :c", c=_ago(days=ARCHIVE_DAYS))
    if n:
        log("system", "archive_auto_deleted", f"{n} report(s) archived more than {ARCHIVE_DAYS} days ago")
    _exec("DELETE FROM sessions WHERE last_seen < :c", c=_ago(days=1))
    return n


# activity log
def log(actor, action, detail=""):
    try:
        _exec("INSERT INTO audit(at, actor, action, detail) VALUES(:at, :actor, :action, :detail)",
              at=now(), actor=actor or "-", action=action, detail=detail)
    except Exception:
        pass


def get_audit(limit=300):
    return _rows("SELECT at, actor, action, detail FROM audit ORDER BY id DESC LIMIT :n", n=int(limit))


# accounts
def has_manager():
    r = _one("SELECT COUNT(*) AS n FROM users WHERE role='manager' AND active=1")
    return bool(r and r["n"] > 0)


def create_user(email, full_name, role, password, must_change=False, by=None):
    email = auth.normalize_email(email)
    if auth.email_problem(email):
        raise ValueError(auth.email_problem(email))
    if not auth.password_ok(password, email):
        raise ValueError("Password is not strong enough.")
    if _one("SELECT 1 AS x FROM users WHERE email=:e", e=email):
        raise ValueError("An account with this email already exists.")
    _exec("""INSERT INTO users(email, full_name, role, pw_hash, must_change, created_at)
             VALUES(:e, :n, :r, :h, :m, :t)""",
          e=email, n=full_name.strip(), r=role, h=hash_pw(password), m=int(must_change), t=now())
    log(by or email, "account_created", f"{email} ({role})")


def login(email, password, role):
    """Returns (user, None) on success or (None, error message)."""
    email = auth.normalize_email(email)
    generic = "Incorrect email, password, or role."
    u = _one("SELECT * FROM users WHERE email=:e", e=email)
    if not u:
        log(email, "login_failed", "unknown email")
        return None, generic
    if u["locked_until"] and datetime.strptime(u["locked_until"], FMT) > ph_now():
        left = datetime.strptime(u["locked_until"], FMT) - ph_now()
        return None, f"Too many wrong attempts. Try again in {int(left.total_seconds() // 60) + 1} minute(s)."
    if not u["active"]:
        return None, "This account is deactivated. Please contact the manager."
    if not check_pw(password, u["pw_hash"]) or u["role"] != role:
        failed = (u["failed"] or 0) + 1
        lock = (ph_now() + timedelta(minutes=auth.LOCK_MINUTES)).strftime(FMT) if failed >= auth.MAX_FAILED else None
        _exec("UPDATE users SET failed=:f, locked_until=:l WHERE email=:e", f=0 if lock else failed, l=lock, e=email)
        if lock:
            log(email, "account_locked", f"{auth.MAX_FAILED} wrong attempts")
            return None, f"Too many wrong attempts. This account is locked for {auth.LOCK_MINUTES} minutes."
        log(email, "login_failed", "wrong password or role")
        return None, f"{generic} ({auth.MAX_FAILED - failed} attempt(s) left)"
    _exec("UPDATE users SET failed=0, locked_until=NULL, last_login=:t WHERE email=:e", t=now(), e=email)
    log(email, "login", role)
    u.pop("pw_hash", None)
    return u, None


def check_password(email, password):
    u = _one("SELECT pw_hash FROM users WHERE email=:e", e=auth.normalize_email(email))
    return bool(u and check_pw(password, u["pw_hash"]))


def change_password(email, new_password, must_change=False, by=None):
    _exec("UPDATE users SET pw_hash=:h, must_change=:m, failed=0, locked_until=NULL WHERE email=:e",
          h=hash_pw(new_password), m=int(must_change), e=email)
    if must_change:
        end_all_sessions(email)
    log(by or email, "password_reset" if must_change else "password_changed", email)


def set_active(email, active, by=None):
    _exec("UPDATE users SET active=:a WHERE email=:e", a=int(active), e=email)
    if not active:
        end_all_sessions(email)
    log(by, "account_activated" if active else "account_deactivated", email)


def list_users():
    return _rows("""SELECT email, full_name, role, active, must_change, last_login, created_at
                    FROM users ORDER BY role, full_name""")


def staff_names():
    return [u["full_name"] for u in list_users()]


def get_user(email):
    return _one("""SELECT email, full_name, role, active, must_change, privacy_version, privacy_at
                   FROM users WHERE email=:e""", e=email)


def accept_privacy(email, version):
    _exec("UPDATE users SET privacy_version=:v, privacy_at=:t WHERE email=:e", v=version, t=now(), e=email)
    log(email, "privacy_accepted", f"notice v{version}")


# login sessions (cookie)
def _token_hash(token):
    return hashlib.sha256(token.encode()).hexdigest()


def start_session(email):
    token = secrets.token_urlsafe(32)
    _exec("INSERT INTO sessions(token_hash, email, created_at, last_seen) VALUES(:h, :e, :t, :t)",
          h=_token_hash(token), e=email, t=now())
    return token


def session_user(token):
    """The user for a cookie token, or None if the token is unknown, idle too long, or the account is off."""
    if not token or len(token) > 100:
        return None
    s = _one("SELECT email, last_seen FROM sessions WHERE token_hash=:h", h=_token_hash(token))
    if not s or s["last_seen"] < _ago(minutes=auth.IDLE_MINUTES):
        return None
    u = get_user(s["email"])
    return u if u and u["active"] else None


def touch_session(token):
    _exec("UPDATE sessions SET last_seen=:t WHERE token_hash=:h", t=now(), h=_token_hash(token))


def end_session(token):
    if token:
        _exec("DELETE FROM sessions WHERE token_hash=:h", h=_token_hash(token))


def end_all_sessions(email):
    _exec("DELETE FROM sessions WHERE email=:e", e=email)


# settings
def get_setting(key):
    r = _one("SELECT value FROM settings WHERE key=:k", k=key)
    return json.loads(r["value"]) if r else DEFAULT_SETTINGS[key]


def set_setting(key, value, by=None):
    _exec("""INSERT INTO settings(key, value) VALUES(:k, :v)
             ON CONFLICT(key) DO UPDATE SET value=excluded.value""", k=key, v=json.dumps(value))
    log(by, "settings_changed", key)


# reports
REPORT_COLS = {"user_email", "created_at", "report_type", "report_date", "time_slot", "customers", "cashiers",
               "baristas", "reported_level", "predicted_level", "text", "sentiment", "category", "ai_summary",
               "ai_provider", "status"}


def add_report(**f):
    f.setdefault("created_at", now())
    f = {k: v for k, v in f.items() if k in REPORT_COLS}
    cols = ", ".join(f)
    vals = ", ".join(f":{k}" for k in f)
    _exec(f"INSERT INTO reports({cols}) VALUES({vals})", **f)


def get_reports(email=None, days=None, archived=False):
    q = "SELECT * FROM reports WHERE " + ("archived_at IS NOT NULL" if archived else "archived_at IS NULL")
    p = {}
    if email:
        q += " AND user_email=:e"
        p["e"] = email
    if days:
        q += " AND created_at >= :since"
        p["since"] = _ago(days=days)
    return _rows(q + " ORDER BY id DESC", **p)


def get_report(report_id):
    return _one("SELECT * FROM reports WHERE id=:i", i=int(report_id))


def can_staff_change(r):
    """Staff may edit/delete their own report within 24 hours, while it is open and has no reply yet."""
    return (r["status"] == "Open" and not r["archived_at"] and not r["reply"]
            and r["created_at"] >= _ago(hours=EDIT_HOURS))


_STAFF_GUARD = ("id=:i AND user_email=:e AND status='Open' AND archived_at IS NULL AND reply IS NULL "
                "AND created_at >= :since")


def edit_report(report_id, email, **f):
    allowed = {"text", "customers", "reported_level", "predicted_level", "sentiment", "category", "ai_summary",
               "ai_provider"}
    f = {k: v for k, v in f.items() if k in allowed}
    if not f:
        return False
    sets = ", ".join(f"{k}=:{k}" for k in f)
    n = _exec(f"""UPDATE reports SET {sets}, edited_at=:t, seen_by_manager=0,
                  check_sentiment=NULL, check_category=NULL, checked_by=NULL, checked_at=NULL
                  WHERE {_STAFF_GUARD}""", **f, t=now(), i=int(report_id), e=email, since=_ago(hours=EDIT_HOURS))
    if n:
        log(email, "report_edited", f"#{report_id}")
    return bool(n)


def delete_own_report(report_id, email):
    n = _exec(f"DELETE FROM reports WHERE {_STAFF_GUARD}", i=int(report_id), e=email, since=_ago(hours=EDIT_HOURS))
    if n:
        log(email, "report_deleted", f"#{report_id} (by the sender)")
    return bool(n)


def set_status(report_id, status, by=None):
    _exec("UPDATE reports SET status=:s WHERE id=:i", s=status, i=int(report_id))
    log(by, "report_status", f"#{report_id} -> {status}")


def reply_to_report(report_id, text, by):
    _exec("UPDATE reports SET reply=:r, replied_by=:b, replied_at=:t, reply_seen=0 WHERE id=:i",
          r=text.strip(), b=by, t=now(), i=int(report_id))
    log(by, "report_reply", f"#{report_id}")


def archive_report(report_id, reason, by):
    _exec("UPDATE reports SET archived_at=:t, archived_by=:b, archive_reason=:r WHERE id=:i",
          t=now(), b=by, r=reason.strip(), i=int(report_id))
    log(by, "report_archived", f"#{report_id}: {reason.strip()}")


def restore_report(report_id, by):
    _exec("UPDATE reports SET archived_at=NULL, archived_by=NULL, archive_reason=NULL WHERE id=:i", i=int(report_id))
    log(by, "report_restored", f"#{report_id}")


def delete_report(report_id, by):
    """Permanent delete. Only archived reports can be deleted this way."""
    n = _exec("DELETE FROM reports WHERE id=:i AND archived_at IS NOT NULL", i=int(report_id))
    if n:
        log(by, "report_deleted", f"#{report_id} (deleted from archive)")
    return bool(n)


def purge_date(r):
    return (datetime.strptime(r["archived_at"], FMT) + timedelta(days=ARCHIVE_DAYS)).date()


# notification counts
def count_new_reports():
    r = _one("SELECT COUNT(*) AS n FROM reports WHERE seen_by_manager=0 AND archived_at IS NULL")
    return r["n"] if r else 0


def mark_reports_seen():
    _exec("UPDATE reports SET seen_by_manager=1 WHERE seen_by_manager=0")


def count_unseen_replies(email):
    r = _one("SELECT COUNT(*) AS n FROM reports WHERE user_email=:e AND reply_seen=0", e=email)
    return r["n"] if r else 0


def mark_replies_seen(email):
    _exec("UPDATE reports SET reply_seen=1 WHERE user_email=:e AND reply_seen=0", e=email)


# tagging accuracy check
def next_report_to_check():
    """Oldest report with text that nobody has hand-labeled yet."""
    return _one("""SELECT id, report_type, text FROM reports
                   WHERE archived_at IS NULL AND check_sentiment IS NULL AND text IS NOT NULL AND text <> ''
                   ORDER BY id LIMIT 1""")


def save_check(report_id, sentiment, category, by):
    _exec("UPDATE reports SET check_sentiment=:s, check_category=:c, checked_by=:b, checked_at=:t WHERE id=:i",
          s=sentiment, c=category, b=by, t=now(), i=int(report_id))
    log(by, "tag_checked", f"#{report_id}")


def checked_reports():
    return _rows("""SELECT id, created_at, text, sentiment, category, ai_provider, check_sentiment, check_category,
                    checked_by FROM reports WHERE check_sentiment IS NOT NULL ORDER BY checked_at""")


def clear_checks(by):
    _exec("UPDATE reports SET check_sentiment=NULL, check_category=NULL, checked_by=NULL, checked_at=NULL")
    log(by, "tag_checks_cleared", "")


def avg_reported_customers(weekday, time_slot):
    """Average customers staff reported for this weekday and hour (used to improve the planner)."""
    rows = _rows("""SELECT customers, report_date FROM reports WHERE report_type='end_of_shift'
                    AND time_slot=:s AND customers IS NOT NULL AND archived_at IS NULL""", s=time_slot)
    vals = [r["customers"] for r in rows
            if r["report_date"] and datetime.strptime(r["report_date"], "%Y-%m-%d").strftime("%A") == weekday]
    return (sum(vals) / len(vals), len(vals)) if vals else (None, 0)


# plans
def save_plans(rows, plan_date, created_by, action="plan_published"):
    with engine().begin() as c:
        c.execute(sa.text("DELETE FROM plans WHERE plan_date=:d"), {"d": plan_date})
        for r in rows:
            c.execute(sa.text("""INSERT INTO plans(created_at, plan_date, time_slot, customers, cashiers, baristas,
                                 predicted_level, expected_wait, ai_insight, created_by, ai_cashiers, ai_baristas)
                                 VALUES(:t, :d, :s, :cu, :ca, :b, :l, :w, :i, :by, :aic, :aib)"""),
                      {"t": now(), "d": plan_date, "s": r["slot"], "cu": int(r["customers"]),
                       "ca": int(r["cashiers"]), "b": int(r["baristas"]), "l": r["level"],
                       "w": float(r["wait"]), "i": r.get("insight", ""), "by": created_by,
                       "aic": int(r.get("ai_cashiers", r["cashiers"])), "aib": int(r.get("ai_baristas", r["baristas"]))})
    changed = sum(1 for r in rows if (r.get("ai_cashiers", r["cashiers"]), r.get("ai_baristas", r["baristas"]))
                  != (r["cashiers"], r["baristas"]))
    log(created_by, action,
        f"{plan_date} ({len(rows)} hour(s)" + (f", {changed} changed by the manager)" if changed else ")"))


def delete_plans(plan_date, by):
    n = _exec("DELETE FROM plans WHERE plan_date=:d", d=str(plan_date))
    log(by, "plan_deleted", f"{plan_date} ({n} hour(s))")
    return n


def get_plans(plan_date):
    return _rows("SELECT * FROM plans WHERE plan_date=:d ORDER BY time_slot", d=str(plan_date))


# response times
def record_timing(kind, seconds):
    try:
        _exec("INSERT INTO timings(at, kind, seconds) VALUES(:a, :k, :s)", a=now(), k=kind, s=float(seconds))
    except Exception:
        pass


def timing_stats():
    return _rows("""SELECT kind, COUNT(*) AS n, AVG(seconds) AS avg_s, MIN(seconds) AS min_s, MAX(seconds) AS max_s
                    FROM timings GROUP BY kind""")


# backup
def export_zip(by=None):
    """All data as CSV files in one ZIP. Password hashes and session tokens are never exported."""
    buf = io.BytesIO()
    tables = {
        "users.csv": pd.DataFrame(list_users()),
        "reports.csv": pd.DataFrame(_rows("SELECT * FROM reports ORDER BY id")),
        "plans.csv": pd.DataFrame(_rows("SELECT * FROM plans ORDER BY id")),
        "settings.csv": pd.DataFrame(_rows("SELECT * FROM settings")),
        "activity_log.csv": pd.DataFrame(get_audit(100000)),
        "response_times.csv": pd.DataFrame(_rows("SELECT at, kind, seconds FROM timings ORDER BY id")),
    }
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for name, df in tables.items():
            z.writestr(name, df.to_csv(index=False))
    log(by, "data_exported", "full backup ZIP")
    return buf.getvalue()


def counts():
    out = {}
    for t in ("users", "reports", "plans", "audit"):
        r = _one(f"SELECT COUNT(*) AS n FROM {t}")
        out[t] = r["n"] if r else 0
    return out
