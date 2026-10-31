"""
ui.py - BrewStaffAI look and feel: colors, page header, cards, badges.
Green = Okay, amber = Congested, red = Overloaded on every page.
"""
import base64
import html
import os
from functools import lru_cache

import streamlit as st

ASSETS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")

BG, CARD, BORDER, TEXT, MUTED = "#0E1311", "#161E1A", "#26332C", "#EEF1EC", "#A3AEA6"
GREEN, LIME, AMBER, RED, BLUE = "#2E7D4F", "#A6CE39", "#F0A73A", "#E5534B", "#58A6FF"
CASHIER_COLOR, BARISTA_COLOR = AMBER, GREEN
LEVEL_COLOR = {"Okay": "#3FB950", "Congested": AMBER, "Overloaded": RED}
LEVEL_ICON = {"Okay": "✅", "Congested": "⚠️", "Overloaded": "⛔"}
LEVEL_TEXT = {"Okay": "Short waits (7 min or less)", "Congested": "Long waits (7–15 min)",
              "Overloaded": "Very long waits (over 15 min)"}
SENT_ICON = {"Positive": "🙂", "Neutral": "😐", "Negative": "🙁"}
CAT_ICON = {"Staffing/Workload": "👥", "Equipment": "🛠️", "Customer Concern": "🗣️",
            "Inventory/Supplies": "📦", "Process": "🔄", "Other": "📝"}

esc = html.escape


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
.bs-title {{ font-size:2.0rem; font-weight:800; margin:0; line-height:1.2; }}
.bs-sub {{ color:var(--muted); margin:4px 0 18px 0; font-size:0.98rem; }}
.bs-card {{ background:var(--card); border:1px solid var(--border); border-radius:16px; padding:18px 20px;
  height:100%; }}
.bs-card h4 {{ margin:0 0 6px 0; font-size:1.0rem; color:var(--muted); font-weight:600; }}
.bs-kpi {{ font-size:2.0rem; font-weight:800; line-height:1.1; }}
.bs-kpi-sub {{ color:var(--muted); font-size:0.85rem; }}
.bs-badge {{ display:inline-block; padding:4px 12px; border-radius:999px; font-weight:700; font-size:0.9rem; }}
.bs-chip {{ display:inline-block; padding:3px 10px; border-radius:999px; font-size:0.82rem; margin:2px 4px 2px 0;
  background:rgba(255,255,255,.07); border:1px solid var(--border); }}
.bs-new {{ background:{LIME}; color:#10200F; font-weight:800; border:none; }}
.bs-ai {{ border:1.5px solid {LIME}55; background:linear-gradient(135deg, rgba(166,206,57,.10), rgba(46,125,79,.10));
  border-radius:18px; padding:18px 22px; margin:8px 0 6px 0; }}
.bs-ai-top {{ display:flex; justify-content:space-between; align-items:center; gap:10px; margin-bottom:8px;
  flex-wrap:wrap; }}
.bs-ai-tag {{ background:{LIME}; color:#10200F; font-weight:800; font-size:0.75rem; padding:3px 9px; border-radius:6px; }}
.bs-ai-src {{ color:var(--muted); font-size:0.8rem; }}
.bs-ai-head {{ font-size:1.25rem; font-weight:750; margin:4px 0 10px 0; }}
.bs-point {{ display:flex; gap:10px; align-items:flex-start; margin:7px 0; }}
.bs-point .n {{ min-width:26px; height:26px; border-radius:50%; background:{GREEN}; color:white; font-weight:700;
  display:flex; align-items:center; justify-content:center; font-size:0.8rem; }}
.bs-crew {{ display:flex; gap:6px; align-items:center; flex-wrap:wrap; margin:4px 0; }}
.bs-dot {{ width:20px; height:20px; border-radius:50%; display:inline-block; }}
.bs-step {{ display:flex; align-items:center; gap:10px; color:var(--muted); font-size:0.9rem; flex-wrap:wrap; margin:0 0 14px 0; }}
.bs-step b {{ color:{TEXT}; }}
.bs-step .dot {{ width:24px; height:24px; border-radius:50%; background:{GREEN}; color:#fff; display:inline-flex;
  align-items:center; justify-content:center; font-size:.78rem; font-weight:700; }}
.bs-slot {{ border-left:6px solid; border-radius:12px; padding:10px 14px; margin:6px 0; background:var(--card); }}
.bs-reply {{ border-left:4px solid {LIME}; background:rgba(166,206,57,.08); border-radius:8px; padding:8px 12px;
  margin-top:8px; }}
section[data-testid="stSidebar"] {{ border-right:1px solid var(--border); }}
div[data-testid="stForm"] {{ border-radius:16px; }}
.st-key-refresh_btn {{ display:flex; justify-content:flex-end; }}
@media (max-width: 640px) {{
  .bs-title {{ font-size:1.6rem; }}
  .block-container {{ padding:3.6rem 1rem 2rem 1rem; }}
  .st-key-refresh_btn {{ justify-content:flex-start; }}
}}
</style>""", unsafe_allow_html=True)


def page_header(title, purpose):
    left, right = st.columns([5, 1], vertical_alignment="center", gap="small")
    left.markdown(f"<div class='bs-title'>{esc(title)}</div>", unsafe_allow_html=True)
    if right.button("Refresh", icon=":material/refresh:", key="refresh_btn", width="content",
                    help="Load the latest data"):
        st.rerun()
    st.markdown(f"<div class='bs-sub'>{purpose}</div>", unsafe_allow_html=True)


def steps(items):
    html_ = "".join(f"<span class='dot'>{i}</span><b>{t}</b>{'<span>→</span>' if i < len(items) else ''}"
                    for i, t in enumerate(items, 1))
    st.markdown(f"<div class='bs-step'>{html_}</div>", unsafe_allow_html=True)


def badge(level, size="0.9rem"):
    c = LEVEL_COLOR.get(level, MUTED)
    return (f"<span class='bs-badge' style='background:{c}22;color:{c};border:1px solid {c};font-size:{size}'>"
            f"{LEVEL_ICON.get(level, '')} {esc(str(level))}</span>")


def chip(text, cls=""):
    return f"<span class='bs-chip {cls}'>{esc(str(text))}</span>"


def kpi(label, value, sub="", color=TEXT):
    st.markdown(f"<div class='bs-card'><h4>{label}</h4><div class='bs-kpi' style='color:{color}'>{value}</div>"
                f"<div class='bs-kpi-sub'>{sub}</div></div>", unsafe_allow_html=True)


def crew_text(cashiers, baristas):
    return f"{cashiers} cashier{'s' * (cashiers != 1)} · {baristas} barista{'s' * (baristas != 1)}"


def people(cashiers, baristas):
    """Crew as colored dots: amber = cashier, green = barista (same colors as the charts)."""
    dots = (f"<span class='bs-dot' style='background:{CASHIER_COLOR}'></span>" * cashiers +
            "<span style='width:10px'></span>" +
            f"<span class='bs-dot' style='background:{BARISTA_COLOR}'></span>" * baristas)
    return f"<div class='bs-crew'>{dots}</div><div class='bs-kpi-sub'>{crew_text(cashiers, baristas)}</div>"


def ai_card(title, provider, headline=None, points=None, extra_html=""):
    """Standard look for every AI result. Text from the AI is escaped before display."""
    src = f"Generated by {provider}" if provider else "Basic summary (AI is unavailable right now)"
    pts = "".join(f"<div class='bs-point'><div class='n'>{i}</div><div>{esc(str(p))}</div></div>"
                  for i, p in enumerate(points or [], 1))
    head = f"<div class='bs-ai-head'>{esc(str(headline))}</div>" if headline else ""
    st.markdown(f"<div class='bs-ai'><div class='bs-ai-top'><div><span class='bs-ai-tag'>AI</span> "
                f"<b>{title}</b></div><div class='bs-ai-src'>{src}</div></div>{head}{pts}{extra_html}</div>",
                unsafe_allow_html=True)


def password_feedback(password, email=""):
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
    st.caption("Color = how busy the AI expects the hour to be · number = expected wait in minutes")
    st.markdown(" ".join(f"{badge(l)} <span style='color:{MUTED};font-size:.85rem;margin-right:14px'>"
                         f"{LEVEL_TEXT[l]}</span>" for l in LEVEL_COLOR), unsafe_allow_html=True)


def plain_chart(fig, key=None):
    st.plotly_chart(fig, width="stretch", config={"displayModeBar": False}, key=key)
