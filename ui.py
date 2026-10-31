"""
ui.py — BrewStaffAI look and feel (Jungle Brew brand) + reusable visual components.
HCI principles used:
  * Consistency: every page starts with the same header (title + one line "what this page is for").
  * Recognition over recall: icons + labels in the menu, colors always mean the same thing
    (green = Okay, amber = Congested, red = Overloaded).
  * Visibility of AI: every AI result sits in a card with the same "AI" badge and says which model made it.
  * Minimalism: advanced options are folded away; results are shown as visuals first, text second.
"""
import base64
import os
from functools import lru_cache

import streamlit as st

ASSETS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")

BG, CARD, BORDER, TEXT, MUTED = "#0E1311", "#161E1A", "#26332C", "#EEF1EC", "#A3AEA6"
GREEN, LIME, AMBER, RED, BLUE = "#2E7D4F", "#A6CE39", "#F0A73A", "#E5534B", "#58A6FF"
LEVEL_COLOR = {"Okay": "#3FB950", "Congested": AMBER, "Overloaded": RED}
LEVEL_ICON = {"Okay": "✅", "Congested": "⚠️", "Overloaded": "⛔"}
LEVEL_TEXT = {"Okay": "Short waits (7 min or less)", "Congested": "Long waits (7–15 min)",
              "Overloaded": "Very long waits (over 15 min)"}
SENT_ICON = {"Positive": "🙂", "Neutral": "😐", "Negative": "🙁"}
CAT_ICON = {"Staffing/Workload": "👥", "Equipment": "🛠️", "Customer Concern": "🗣️",
            "Inventory/Supplies": "📦", "Process": "🔄", "Other": "📝"}


@lru_cache(maxsize=8)
def asset_b64(name):
    with open(os.path.join(ASSETS, name), "rb") as f:
        return base64.b64encode(f.read()).decode()


def inject_css():
    st.markdown(f"""
<style>
:root {{ --card:{CARD}; --border:{BORDER}; --muted:{MUTED}; }}
.block-container {{ padding-top: 2.2rem; max-width: 1200px; }}
h1, h2, h3 {{ letter-spacing: -0.01em; }}
.bs-header {{ display:flex; align-items:center; gap:14px; margin-bottom:4px; }}
.bs-header .ico {{ font-size:2.1rem; width:58px; height:58px; display:flex; align-items:center;
  justify-content:center; border-radius:16px; background:rgba(46,125,79,.22); }}
.bs-header h1 {{ font-size:2.0rem; margin:0; padding:0; }}
.bs-sub {{ color:var(--muted); margin:2px 0 18px 72px; font-size:0.98rem; }}
.bs-card {{ background:var(--card); border:1px solid var(--border); border-radius:16px; padding:18px 20px;
  height:100%; }}
.bs-card h4 {{ margin:0 0 6px 0; font-size:1.0rem; color:var(--muted); font-weight:600; }}
.bs-kpi {{ font-size:2.0rem; font-weight:800; line-height:1.1; }}
.bs-kpi-sub {{ color:var(--muted); font-size:0.85rem; }}
.bs-badge {{ display:inline-block; padding:4px 12px; border-radius:999px; font-weight:700; font-size:0.9rem; }}
.bs-chip {{ display:inline-block; padding:3px 10px; border-radius:999px; font-size:0.82rem; margin:2px 4px 2px 0;
  background:rgba(255,255,255,.07); border:1px solid var(--border); }}
.bs-ai {{ border:1.5px solid {LIME}55; background:linear-gradient(135deg, rgba(166,206,57,.10), rgba(46,125,79,.10));
  border-radius:18px; padding:18px 22px; margin:8px 0 6px 0; }}
.bs-ai-top {{ display:flex; justify-content:space-between; align-items:center; gap:10px; margin-bottom:8px; }}
.bs-ai-tag {{ background:{LIME}; color:#10200F; font-weight:800; font-size:0.75rem; padding:3px 9px; border-radius:6px; }}
.bs-ai-src {{ color:var(--muted); font-size:0.8rem; }}
.bs-ai-head {{ font-size:1.25rem; font-weight:750; margin:4px 0 10px 0; }}
.bs-point {{ display:flex; gap:10px; align-items:flex-start; margin:7px 0; }}
.bs-point .n {{ min-width:26px; height:26px; border-radius:50%; background:{GREEN}; color:white; font-weight:700;
  display:flex; align-items:center; justify-content:center; font-size:0.8rem; }}
.bs-people {{ font-size:1.9rem; letter-spacing:4px; line-height:1.3; }}
.bs-step {{ display:flex; align-items:center; gap:10px; color:var(--muted); font-size:0.9rem; flex-wrap:wrap; margin:0 0 14px 0; }}
.bs-step b {{ color:{TEXT}; }}
.bs-step .dot {{ width:24px; height:24px; border-radius:50%; background:{GREEN}; color:#fff; display:inline-flex;
  align-items:center; justify-content:center; font-size:.78rem; font-weight:700; }}
.bs-slot {{ border-left:6px solid; border-radius:12px; padding:10px 14px; margin:6px 0; background:var(--card); }}
section[data-testid="stSidebar"] {{ border-right:1px solid var(--border); }}
div[data-testid="stForm"] {{ border-radius:16px; }}
</style>""", unsafe_allow_html=True)


def page_header(icon, title, purpose):
    st.markdown(f"<div class='bs-header'><div class='ico'>{icon}</div><h1>{title}</h1></div>"
                f"<div class='bs-sub'>{purpose}</div>", unsafe_allow_html=True)


def steps(items):
    html = "".join(f"<span class='dot'>{i}</span><b>{t}</b>{'<span>→</span>' if i < len(items) else ''}"
                   for i, t in enumerate(items, 1))
    st.markdown(f"<div class='bs-step'>{html}</div>", unsafe_allow_html=True)


def badge(level, size="0.9rem"):
    c = LEVEL_COLOR.get(level, MUTED)
    return (f"<span class='bs-badge' style='background:{c}22;color:{c};border:1px solid {c};font-size:{size}'>"
            f"{LEVEL_ICON.get(level, '')} {level}</span>")


def chip(text):
    return f"<span class='bs-chip'>{text}</span>"


def kpi(label, value, sub="", color=TEXT):
    st.markdown(f"<div class='bs-card'><h4>{label}</h4><div class='bs-kpi' style='color:{color}'>{value}</div>"
                f"<div class='bs-kpi-sub'>{sub}</div></div>", unsafe_allow_html=True)


def people(cashiers, baristas):
    return ("<div class='bs-people'>" + "🧾" * cashiers + "<span style='opacity:.35'> | </span>" + "☕" * baristas +
            f"</div><div class='bs-kpi-sub'>🧾 {cashiers} cashier(s) · ☕ {baristas} barista(s)</div>")


def ai_card(title, provider, headline=None, points=None, extra_html=""):
    """The one standard look for every AI result."""
    src = f"Generated by {provider}" if provider else "AI service offline · showing a template answer"
    pts = "".join(f"<div class='bs-point'><div class='n'>{i}</div><div>{p}</div></div>"
                  for i, p in enumerate(points or [], 1))
    head = f"<div class='bs-ai-head'>{headline}</div>" if headline else ""
    st.markdown(f"<div class='bs-ai'><div class='bs-ai-top'><div><span class='bs-ai-tag'>AI</span> "
                f"<b>{title}</b></div><div class='bs-ai-src'>{src}</div></div>{head}{pts}{extra_html}</div>",
                unsafe_allow_html=True)


def password_feedback(password, email=""):
    """Live strength bar + checklist so users can SEE what makes a password strong."""
    import auth
    if not password:
        st.caption(f"Password rules: {auth.MIN_LENGTH}+ characters with uppercase, lowercase, number, and symbol.")
        return
    score, label = auth.strength(password, email)
    color = {"Strong": LEVEL_COLOR["Okay"], "Fair": AMBER, "Weak": RED}[label]
    st.markdown(f"<div style='display:flex;align-items:center;gap:10px;margin:2px 0 6px'>"
                f"<div style='flex:1;height:8px;border-radius:6px;background:{BORDER}'>"
                f"<div style='width:{score}%;height:8px;border-radius:6px;background:{color}'></div></div>"
                f"<b style='color:{color}'>{label}</b></div>", unsafe_allow_html=True)
    st.markdown("".join(f"<div style='font-size:.86rem;color:{LEVEL_COLOR['Okay'] if ok else MUTED}'>"
                        f"{'✔' if ok else '○'} {rule}</div>" for rule, ok in auth.password_checks(password, email)),
                unsafe_allow_html=True)


def legend():
    st.caption("Color = AI prediction for that hour · number = average wait from the simulation check")
    st.markdown(" ".join(f"{badge(l)} <span style='color:{MUTED};font-size:.85rem;margin-right:14px'>"
                         f"{LEVEL_TEXT[l]}</span>" for l in LEVEL_COLOR), unsafe_allow_html=True)
