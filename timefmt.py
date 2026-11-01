"""
timefmt.py - shows times the way people read them in the Philippines (12-hour clock with AM/PM).
Times are still saved in 24-hour form in the database; only the display changes.
"""
from datetime import datetime


def hour_label(hour, minutes=True):
    h = int(hour) % 24
    suffix = "AM" if h < 12 else "PM"
    return f"{h % 12 or 12}:00 {suffix}" if minutes else f"{h % 12 or 12} {suffix}"


def slot_label(slot):
    """'13:00-14:00' -> '1:00 PM – 2:00 PM'"""
    if not slot or len(slot) < 5:
        return slot or ""
    start = int(slot[:2])
    return f"{hour_label(start)} – {hour_label(start + 1)}"


def slot_short(slot):
    """'13:00-14:00' -> '1 PM'"""
    return hour_label(int(slot[:2]), minutes=False) if slot else ""


def dt_label(value):
    """'2026-10-31 23:27:05' -> 'Oct 31, 2026 · 11:27 PM'"""
    if not value:
        return ""
    try:
        d = datetime.strptime(str(value)[:19], "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return str(value)
    return f"{d:%b} {d.day}, {d.year} · {d.hour % 12 or 12}:{d:%M} {'AM' if d.hour < 12 else 'PM'}"
