"""
auth.py - BrewStaffAI account security rules
  * Only company emails ending in @junglebrewpq.com are allowed.
  * Passwords must be strong (12+ characters, upper, lower, number, symbol).
  * 5 wrong passwords lock the account for 5 minutes.
  * Sessions end after 30 minutes of no activity.
"""
import re
import secrets
import string

COMPANY_DOMAIN = "junglebrewpq.com"
EMAIL_RE = re.compile(r"^[a-z0-9](?:[a-z0-9._-]{0,62}[a-z0-9])?@" + re.escape(COMPANY_DOMAIN) + r"$")
PERSONAL_DOMAINS = ("gmail.", "yahoo.", "outlook.", "hotmail.", "live.", "icloud.", "proton", "aol.", "ymail.")

MIN_LENGTH = 12
MAX_FAILED = 5
LOCK_MINUTES = 5
IDLE_MINUTES = 30

# A few of the most leaked passwords; any password containing these is refused.
COMMON = ["password", "123456", "qwerty", "letmein", "welcome", "admin", "iloveyou", "abc123",
          "staff", "manager", "junglebrew", "brewstaff", "coffee", "111111", "000000"]


def normalize_email(email):
    return (email or "").strip().lower()


def email_problem(email):
    """Returns None if the email is allowed, otherwise a friendly reason."""
    e = normalize_email(email)
    if not e:
        return "Please enter your work email."
    if "@" not in e:
        return f"Use your work email, for example juan.delacruz@{COMPANY_DOMAIN}."
    domain = e.split("@", 1)[1]
    if any(domain.startswith(p) for p in PERSONAL_DOMAINS):
        return f"Personal emails (Gmail, Outlook, Yahoo, etc.) are not allowed. Use your @{COMPANY_DOMAIN} email."
    if domain != COMPANY_DOMAIN:
        return f"Only @{COMPANY_DOMAIN} emails can be used in BrewStaffAI."
    if not EMAIL_RE.match(e):
        return "That email format is not valid. Use letters, numbers, dots, dashes, or underscores before the @."
    return None


def password_checks(password, email=""):
    """List of (rule, passed) used for the live checklist."""
    p = password or ""
    local = normalize_email(email).split("@")[0]
    return [
        (f"At least {MIN_LENGTH} characters", len(p) >= MIN_LENGTH),
        ("An uppercase letter (A–Z)", any(c.isupper() for c in p)),
        ("A lowercase letter (a–z)", any(c.islower() for c in p)),
        ("A number (0–9)", any(c.isdigit() for c in p)),
        ("A symbol (! @ # $ % & * ? etc.)", any(c in string.punctuation for c in p)),
        ("No common words or your email name", not any(w in p.lower() for w in COMMON)
         and not (len(local) >= 3 and local in p.lower())),
    ]


def password_ok(password, email=""):
    return all(ok for _, ok in password_checks(password, email))


def strength(password, email=""):
    """(score 0-100, label) for the strength bar."""
    passed = sum(ok for _, ok in password_checks(password, email))
    bonus = min(20, max(0, len(password or "") - MIN_LENGTH) * 4)
    score = min(100, int(passed / 6 * 80) + bonus)
    label = "Strong" if score >= 85 else "Fair" if score >= 55 else "Weak"
    return score, label


def generate_password(length=14):
    """Strong random temporary password (used when the manager creates a staff account)."""
    alphabet = string.ascii_letters + string.digits + "!@#$%&*?"
    while True:
        pw = "".join(secrets.choice(alphabet) for _ in range(length))
        if password_ok(pw):
            return pw
