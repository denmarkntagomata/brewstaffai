"""
db.py — SQLite database for BrewStaffAI v2 (Manager and Staff only)
Tables:
  users     company-email accounts, hashed passwords, lockout counters
  reports   staff end-of-shift and incident reports + AI tags
  plans     staffing plans saved by the manager
  settings  café defaults (hourly customer profile, service times)
Passwords are stored as salted PBKDF2-SHA256 hashes (200,000 rounds), never as plain text.
"""
import hashlib
import json
import os
import secrets
import shutil
import sqlite3
from datetime import datetime, timedelta

import auth

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "brewstaff.db")

DEFAULT_SETTINGS = {
    # Placeholder until the re-observation (based on ~24 customers/hour at the observed noon peak)
    "hourly_profile": {"8": 15, "9": 15, "10": 12, "11": 12, "12": 24, "13": 24, "14": 14, "15": 14,
                       "16": 20, "17": 20, "18": 22, "19": 22, "20": 12, "21": 12},
    "service_times": {"cashier": 1.0, "simple": 2.0, "complex": 4.5, "p_simple": 0.40},
    "max_counter_staff": 4,
}


def conn():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    c = sqlite3.connect(DB_PATH, check_same_thread=False)
    c.row_factory = sqlite3.Row
    return c


def now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


# ------------------------------------------------------------------ passwords
def hash_pw(password, salt=None):
    salt = salt or secrets.token_hex(16)
    h = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 200_000).hex()
    return f"{salt}${h}"


def check_pw(password, stored):
    salt, _ = stored.split("$", 1)
    return secrets.compare_digest(hash_pw(password, salt), stored)


# ------------------------------------------------------------------ setup
def init_db():
    # v1 used usernames (staff1, manager). Keep a backup and start fresh for v2.
    if os.path.exists(DB_PATH):
        with conn() as c:
            cols = [r[1] for r in c.execute("PRAGMA table_info(users)")]
        if cols and "email" not in cols:
            shutil.move(DB_PATH, DB_PATH.replace(".db", "_v1_backup.db"))
    with conn() as c:
        c.executescript("""
        CREATE TABLE IF NOT EXISTS users(
            email TEXT PRIMARY KEY, full_name TEXT NOT NULL,
            role TEXT NOT NULL CHECK(role IN ('manager','staff')),
            pw_hash TEXT NOT NULL, active INTEGER DEFAULT 1, must_change INTEGER DEFAULT 0,
            failed INTEGER DEFAULT 0, locked_until TEXT, created_at TEXT, last_login TEXT);
        CREATE TABLE IF NOT EXISTS reports(
            id INTEGER PRIMARY KEY AUTOINCREMENT, user_email TEXT NOT NULL, created_at TEXT NOT NULL,
            report_type TEXT NOT NULL, report_date TEXT, time_slot TEXT, customers INTEGER,
            cashiers INTEGER, baristas INTEGER, reported_level TEXT, predicted_level TEXT,
            text TEXT, sentiment TEXT, category TEXT, ai_summary TEXT, ai_provider TEXT,
            status TEXT DEFAULT 'Open');
        CREATE TABLE IF NOT EXISTS plans(
            id INTEGER PRIMARY KEY AUTOINCREMENT, created_at TEXT, plan_date TEXT, time_slot TEXT,
            customers INTEGER, cashiers INTEGER, baristas INTEGER, predicted_level TEXT,
            expected_wait REAL, ai_insight TEXT, created_by TEXT);
        CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY, value TEXT);
        """)


def has_manager():
    with conn() as c:
        return c.execute("SELECT COUNT(*) FROM users WHERE role='manager' AND active=1").fetchone()[0] > 0


# ------------------------------------------------------------------ accounts
def create_user(email, full_name, role, password, must_change=False):
    email = auth.normalize_email(email)
    if auth.email_problem(email):
        raise ValueError(auth.email_problem(email))
    if not auth.password_ok(password, email):
        raise ValueError("Password is not strong enough.")
    with conn() as c:
        if c.execute("SELECT 1 FROM users WHERE email=?", (email,)).fetchone():
            raise ValueError("An account with this email already exists.")
        c.execute("INSERT INTO users(email, full_name, role, pw_hash, must_change, created_at) VALUES(?,?,?,?,?,?)",
                  (email, full_name.strip(), role, hash_pw(password), int(must_change), now()))


def login(email, password, role):
    """Returns (user_dict, None) on success or (None, error_message)."""
    email = auth.normalize_email(email)
    generic = "Incorrect email, password, or role."
    with conn() as c:
        u = c.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
        if not u:
            return None, generic
        if u["locked_until"] and datetime.strptime(u["locked_until"], "%Y-%m-%d %H:%M:%S") > datetime.now():
            left = datetime.strptime(u["locked_until"], "%Y-%m-%d %H:%M:%S") - datetime.now()
            return None, f"Too many wrong attempts. Try again in {int(left.total_seconds() // 60) + 1} minute(s)."
        if not u["active"]:
            return None, "This account is deactivated. Please contact the manager."
        if not check_pw(password, u["pw_hash"]) or u["role"] != role:
            failed = u["failed"] + 1
            lock = (datetime.now() + timedelta(minutes=auth.LOCK_MINUTES)).strftime("%Y-%m-%d %H:%M:%S") \
                if failed >= auth.MAX_FAILED else None
            c.execute("UPDATE users SET failed=?, locked_until=? WHERE email=?",
                      (0 if lock else failed, lock, email))
            if lock:
                return None, f"Too many wrong attempts. This account is locked for {auth.LOCK_MINUTES} minutes."
            return None, f"{generic} ({auth.MAX_FAILED - failed} attempt(s) left)"
        c.execute("UPDATE users SET failed=0, locked_until=NULL, last_login=? WHERE email=?", (now(), email))
    d = dict(u)
    d.pop("pw_hash", None)
    return d, None


def change_password(email, new_password, must_change=False):
    with conn() as c:
        c.execute("UPDATE users SET pw_hash=?, must_change=?, failed=0, locked_until=NULL WHERE email=?",
                  (hash_pw(new_password), int(must_change), email))


def set_active(email, active):
    with conn() as c:
        c.execute("UPDATE users SET active=? WHERE email=?", (int(active), email))


def list_users():
    with conn() as c:
        return [dict(r) for r in c.execute(
            "SELECT email, full_name, role, active, must_change, last_login, created_at FROM users ORDER BY role, full_name")]


def staff_names():
    return [u["full_name"] for u in list_users()]


def get_user(email):
    with conn() as c:
        r = c.execute("SELECT email, full_name, role, active, must_change FROM users WHERE email=?", (email,)).fetchone()
    return dict(r) if r else None


# ------------------------------------------------------------------ settings
def get_setting(key):
    with conn() as c:
        r = c.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
    return json.loads(r["value"]) if r else DEFAULT_SETTINGS[key]


def set_setting(key, value):
    with conn() as c:
        c.execute("INSERT INTO settings(key, value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                  (key, json.dumps(value)))


# ------------------------------------------------------------------ reports
def add_report(**f):
    f.setdefault("created_at", now())
    with conn() as c:
        c.execute(f"INSERT INTO reports({','.join(f)}) VALUES({','.join('?' * len(f))})", list(f.values()))


def get_reports(email=None, days=None):
    q, args = "SELECT * FROM reports WHERE 1=1", []
    if email:
        q += " AND user_email=?"; args.append(email)
    if days:
        q += " AND created_at >= ?"; args.append((datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S"))
    with conn() as c:
        return [dict(r) for r in c.execute(q + " ORDER BY id DESC", args)]


def set_status(report_id, status):
    with conn() as c:
        c.execute("UPDATE reports SET status=? WHERE id=?", (status, report_id))


def avg_reported_customers(weekday, time_slot):
    """Average customers staff reported for this weekday and time slot (the feedback loop)."""
    with conn() as c:
        rows = c.execute("""SELECT customers, report_date FROM reports WHERE report_type='end_of_shift'
                            AND time_slot=? AND customers IS NOT NULL""", (time_slot,)).fetchall()
    vals = [r["customers"] for r in rows
            if r["report_date"] and datetime.strptime(r["report_date"], "%Y-%m-%d").strftime("%A") == weekday]
    return (sum(vals) / len(vals), len(vals)) if vals else (None, 0)


# ------------------------------------------------------------------ plans
def save_plans(rows, plan_date, created_by):
    with conn() as c:
        c.execute("DELETE FROM plans WHERE plan_date=?", (plan_date,))
        for r in rows:
            c.execute("""INSERT INTO plans(created_at, plan_date, time_slot, customers, cashiers, baristas,
                         predicted_level, expected_wait, ai_insight, created_by) VALUES(?,?,?,?,?,?,?,?,?,?)""",
                      (now(), plan_date, r["slot"], r["customers"], r["cashiers"], r["baristas"],
                       r["level"], r["wait"], r.get("insight", ""), created_by))


def get_plans(plan_date):
    with conn() as c:
        return [dict(r) for r in c.execute("SELECT * FROM plans WHERE plan_date=? ORDER BY time_slot", (plan_date,))]
