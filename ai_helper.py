"""
ai_helper.py - generative AI features (Gemini main, Groq backup, offline fallback)
  explain_hour()    short insight for one hour (headline, reasons, risk, tip)
  explain_day()     summary of a whole-day staffing plan
  tag_feedback()    sentiment + topic + one-line summary for each staff report
  weekly_summary()  weekly digest (top issues, what went well, actions)

Keys come from Streamlit secrets or environment variables. Staff names are removed before text is sent.
"""
import json
import os
import re
from collections import Counter

import requests

CATEGORIES = ["Staffing/Workload", "Equipment", "Customer Concern", "Inventory/Supplies", "Process", "Other"]
SENTIMENTS = ["Positive", "Neutral", "Negative"]
_COMMON = {"staff", "manager", "jungle", "brew", "demo", "one", "two", "three", "cafe", "café"}


def _secret(name, default=None):
    try:
        import streamlit as st
        if name in st.secrets:
            return st.secrets[name]
    except Exception:
        pass
    return os.environ.get(name, default)


def ai_status():
    return {"Gemini": bool(_secret("GEMINI_API_KEY")), "Gemini model": _secret("GEMINI_MODEL", "gemini-3.5-flash"),
            "Groq": bool(_secret("GROQ_API_KEY")), "Groq model": _secret("GROQ_MODEL", "openai/gpt-oss-120b")}


def scrub(text, names=()):
    """Replace staff names with [staff] before text is sent to an AI service."""
    for n in names:
        for part in [n] + n.split():
            if len(part) > 2 and part.lower() not in _COMMON:
                text = re.sub(rf"\b{re.escape(part)}\b", "[staff]", text, flags=re.I)
    return text


def _gemini(prompt):
    key = _secret("GEMINI_API_KEY")
    if not key:
        raise RuntimeError("no Gemini key")
    model = _secret("GEMINI_MODEL", "gemini-3.5-flash")
    r = requests.post(f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
                      params={"key": key}, timeout=30,
                      json={"contents": [{"parts": [{"text": prompt}]}],
                            "generationConfig": {"temperature": 0.2}})
    r.raise_for_status()
    return r.json()["candidates"][0]["content"]["parts"][0]["text"]


def _groq(prompt):
    key = _secret("GROQ_API_KEY")
    if not key:
        raise RuntimeError("no Groq key")
    model = _secret("GROQ_MODEL", "openai/gpt-oss-120b")
    r = requests.post("https://api.groq.com/openai/v1/chat/completions", timeout=30,
                      headers={"Authorization": f"Bearer {key}"},
                      json={"model": model, "temperature": 0.2,
                            "messages": [{"role": "user", "content": prompt}]})
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"]


def ask_llm(prompt):
    """Returns (text, provider). provider is 'Gemini', 'Groq', or None if both failed."""
    for name, fn in (("Gemini", _gemini), ("Groq", _groq)):
        try:
            return fn(prompt).strip(), name
        except Exception:
            continue
    return None, None


def ask_json(prompt, required):
    """Ask for JSON and check the required keys. Returns (dict or None, provider)."""
    text, provider = ask_llm(prompt + "\n\nReturn ONLY valid JSON. No markdown, no extra text.")
    if text:
        try:
            data = json.loads(re.search(r"\{.*\}", text, re.S).group(0))
            if all(k in data for k in required):
                return data, provider
        except Exception:
            pass
    return None, None


RULES = """Rules: use ONLY the numbers given, never invent numbers, plain simple English for café staff,
each bullet max 18 words, no names. Thresholds: Okay <= 7 min wait, Congested 7-15 min, Overloaded > 15 min."""


# ---------------------------------------------------------------- one hour
def explain_hour(ctx):
    prompt = f"""You are BrewStaffAI, the staffing assistant of Jungle Brew Café, Parañaque City.
Explain this staffing recommendation to the store manager.
{RULES}
JSON keys: "headline" (one sentence, max 14 words), "why" (list of 3 short reasons),
"risk" (one sentence: what happens if the current plan is kept), "tip" (one practical tip).

Time slot: {ctx['slot']} ({ctx['day']}) · expected customers: {ctx['customers']} · simple drinks: {ctx['p_simple']:.0%}
Current plan: {ctx['cur_c']} cashier(s) + {ctx['cur_b']} barista(s) -> AI predicts {ctx['cur_level']}, \
simulated wait {ctx['cur_wait']:.1f} min, {ctx['cur_walkout']:.0%} walk out
Recommended: {ctx['rec_c']} cashier(s) + {ctx['rec_b']} barista(s) -> AI predicts {ctx['rec_level']} \
(confidence {ctx['rec_conf']:.0%}), simulated wait {ctx['rec_wait']:.1f} min, {ctx['rec_walkout']:.0%} walk out, \
barista busy {ctx['rec_util']:.0%}
Target reached: {ctx['reached']}"""
    data, provider = ask_json(prompt, ["headline", "why", "risk", "tip"])
    if data:
        return data, provider
    same = (ctx["cur_c"], ctx["cur_b"]) == (ctx["rec_c"], ctx["rec_b"])
    return {
        "headline": "Keep the current crew." if same else
        f"Use {ctx['rec_c']} cashier(s) and {ctx['rec_b']} barista(s) for this hour.",
        "why": [f"About {ctx['customers']} customers are expected in this hour.",
                f"The AI predicts {ctx['rec_level']} with the recommended crew ({ctx['rec_conf']:.0%} confidence).",
                (f"Simulated average wait stays at about {ctx['rec_wait']:.1f} minutes." if same else
                 f"Simulated average wait drops to about {ctx['rec_wait']:.1f} minutes.")],
        "risk": f"With the current plan the AI predicts {ctx['cur_level']} "
                f"(about {ctx['cur_wait']:.1f} min wait, {ctx['cur_walkout']:.0%} walk out).",
        "tip": "Prepare cups and syrups before the hour starts to speed up drink making.",
    }, None


# ---------------------------------------------------------------- whole day
def explain_day(day, rows):
    lines = "\n".join(f"{r['slot']}: {r['customers']} customers -> {r['cashiers']}C+{r['baristas']}B, "
                      f"{r['level']}, wait {r['wait']} min" for r in rows)
    prompt = f"""You are BrewStaffAI for Jungle Brew Café. Summarize this AI staffing plan for {day} for the manager.
{RULES}
JSON keys: "headline" (one sentence, max 14 words), "peak" (one sentence naming the busiest hours),
"actions" (list of 3 short practical actions for the day).

Plan per hour (C = cashier, B = barista):
{lines}"""
    data, provider = ask_json(prompt, ["headline", "peak", "actions"])
    if data:
        return data, provider
    peak = max(rows, key=lambda r: r["customers"])
    most = max(r["cashiers"] + r["baristas"] for r in rows)
    return {"headline": f"Plan for {day}: up to {most} counter staff at the busiest hour.",
            "peak": f"Busiest hour: {peak['slot']} with about {peak['customers']} customers.",
            "actions": ["Schedule your strongest barista during the peak hours.",
                        "Use slow hours for cleaning and restocking.",
                        "Check staff reports tonight to improve tomorrow's plan."]}, None


# ---------------------------------------------------------------- feedback tagging
_KEYWORDS = {
    "Staffing/Workload": ["staff", "short", "alone", "rush", "busy", "tired", "overtime", "kulang", "pagod", "barista"],
    "Equipment": ["machine", "grinder", "espresso", "broken", "sira", "pos", "printer", "blender", "aircon"],
    "Customer Concern": ["customer", "complain", "angry", "wait", "line", "queue", "reklamo"],
    "Inventory/Supplies": ["out of", "milk", "cups", "beans", "stock", "supply", "ubos", "syrup", "ran out"],
    "Process": ["process", "order", "layout", "system", "procedure", "flow", "counter"],
}
_POS = ["smooth", "good", "great", "helped", "thank", "fine", "maayos", "ayos", "improved", "fast"]
_NEG = ["broken", "late", "short", "angry", "complain", "problem", "ubos", "sira", "slow", "rush", "issue",
        "ran out", "stopped", "long"]


def _fallback_tag(text):
    t = text.lower()
    scores = {c: sum(k in t for k in kws) for c, kws in _KEYWORDS.items()}
    cat = max(scores, key=scores.get) if max(scores.values()) > 0 else "Other"
    pos, neg = sum(k in t for k in _POS), sum(k in t for k in _NEG)
    sent = "Positive" if pos > neg else "Negative" if neg > pos else "Neutral"
    return {"sentiment": sent, "category": cat, "summary": text[:100]}


def tag_feedback(text, names=()):
    clean = scrub(text, names)
    prompt = f"""Classify this staff shift report from a café. It is about shift conditions only.
JSON keys: "sentiment" (one of {SENTIMENTS}), "category" (one of {CATEGORIES}),
"summary" (one short sentence, max 15 words, for the manager, no names).

Report: \"\"\"{clean}\"\"\""""
    data, provider = ask_json(prompt, ["sentiment", "category", "summary"])
    if data and data["sentiment"] in SENTIMENTS and data["category"] in CATEGORIES:
        return {**data, "provider": provider}
    return {**_fallback_tag(clean), "provider": None}


# ---------------------------------------------------------------- weekly summary
def weekly_summary(reports, names=()):
    if not reports:
        return None, None
    lines = "\n".join(f"- [{r['sentiment']}/{r['category']}] {scrub(r['text'] or r['ai_summary'] or '', names)}"
                      for r in reports[:60])
    prompt = f"""You are BrewStaffAI. Summarize this week's staff shift reports for the café manager.
{RULES}
JSON keys: "headline" (one sentence, max 14 words), "top_issues" (list of up to 3 objects with keys
"issue" and "count"), "went_well" (list of up to 2 short points), "actions" (list of 2 short suggested actions).

Reports:
{lines}"""
    data, provider = ask_json(prompt, ["headline", "top_issues", "went_well", "actions"])
    if data:
        return data, provider
    cats = Counter(r["category"] for r in reports if r["sentiment"] != "Positive").most_common(3)
    good = [r["ai_summary"] for r in reports if r["sentiment"] == "Positive"][:2]
    return {"headline": f"{len(reports)} report(s) this period.",
            "top_issues": [{"issue": c, "count": n} for c, n in cats],
            "went_well": good or ["No positive reports yet."],
            "actions": ["Review open issues with the team.", "Follow up on equipment and supply problems first."]}, None
