"""
test_keys.py — checks your Gemini and Groq API keys
=====================================================
Run in the VS Code terminal (inside the brewstaffai folder):
    python test_keys.py

It reads .streamlit/secrets.toml, tells you if each key works, lists the model
names your account can use, and tests the model names you typed.
"""
import os
import re
import sys

import requests

PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".streamlit", "secrets.toml")


def load_secrets():
    if not os.path.exists(PATH):
        print("X  File not found: .streamlit/secrets.toml")
        print("   Create it inside the .streamlit folder (see the guide) and run this again.")
        sys.exit(1)
    vals = {}
    with open(PATH, encoding="utf-8-sig") as f:
        for line in f:
            m = re.match(r'\s*([A-Z_]+)\s*=\s*["\'](.*)["\']', line)
            if m:
                vals[m.group(1)] = m.group(2).strip()
    return vals


def missing(v):
    return not v or "paste" in v.lower()


s = load_secrets()
print("=" * 60)
print("GEMINI (main)")
print("=" * 60)
gkey, gmodel = s.get("GEMINI_API_KEY", ""), s.get("GEMINI_MODEL", "")
if missing(gkey):
    print("!  No Gemini key yet. Paste it in secrets.toml as GEMINI_API_KEY = \"...\"")
else:
    try:
        r = requests.get("https://generativelanguage.googleapis.com/v1beta/models",
                         params={"key": gkey, "pageSize": 200}, timeout=20)
        if r.status_code != 200:
            print(f"X  Gemini rejected the key (error {r.status_code}). Copy the key again from AI Studio.")
            print("  ", r.text[:200])
        else:
            names = [m["name"].replace("models/", "") for m in r.json().get("models", [])
                     if "generateContent" in m.get("supportedGenerationMethods", [])]
            flash = [n for n in names if "flash" in n]
            print("OK Your Gemini key works.")
            print("   'Flash' models your account can use (fast and free-tier friendly):")
            for n in flash[:15]:
                print("     -", n)
            if gmodel:
                t = requests.post(f"https://generativelanguage.googleapis.com/v1beta/models/{gmodel}:generateContent",
                                  params={"key": gkey}, timeout=30,
                                  json={"contents": [{"parts": [{"text": "Reply with exactly: BrewStaffAI ready"}]}]})
                if t.status_code == 200:
                    reply = t.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
                    print(f"OK Test with GEMINI_MODEL = \"{gmodel}\" worked. Gemini replied: {reply}")
                elif t.status_code == 429:
                    print(f"!  \"{gmodel}\" hit the free-tier limit (error 429). Wait a minute, or try a")
                    print("   'flash-lite' model from the list above.")
                else:
                    print(f"X  GEMINI_MODEL = \"{gmodel}\" did not work (error {t.status_code}).")
                    if flash:
                        print(f"   Try changing it to: GEMINI_MODEL = \"{flash[0]}\"")
    except requests.RequestException as e:
        print("X  Could not reach Google. Check your internet connection.", e)

print()
print("=" * 60)
print("GROQ (backup)")
print("=" * 60)
qkey, qmodel = s.get("GROQ_API_KEY", ""), s.get("GROQ_MODEL", "")
if missing(qkey):
    print("!  No Groq key yet. Paste it in secrets.toml as GROQ_API_KEY = \"...\"")
else:
    try:
        h = {"Authorization": f"Bearer {qkey}"}
        r = requests.get("https://api.groq.com/openai/v1/models", headers=h, timeout=20)
        if r.status_code != 200:
            print(f"X  Groq rejected the key (error {r.status_code}). Copy the key again from console.groq.com.")
        else:
            ids = sorted(m["id"] for m in r.json().get("data", []))
            chat = [i for i in ids if not any(x in i for x in ("whisper", "guard", "tts", "orpheus"))]
            print("OK Your Groq key works.")
            print("   Chat models your account can use:")
            for i in chat[:15]:
                print("     -", i)
            if qmodel:
                t = requests.post("https://api.groq.com/openai/v1/chat/completions", headers=h, timeout=30,
                                  json={"model": qmodel, "messages": [
                                      {"role": "user", "content": "Reply with exactly: BrewStaffAI ready"}]})
                if t.status_code == 200:
                    print(f"OK Test with GROQ_MODEL = \"{qmodel}\" worked. Groq replied: "
                          f"{t.json()['choices'][0]['message']['content'].strip()}")
                else:
                    print(f"X  GROQ_MODEL = \"{qmodel}\" did not work (error {t.status_code}).")
                    if chat:
                        pick = next((i for i in chat if "llama" in i and "70b" in i), chat[0])
                        print(f"   Try changing it to: GROQ_MODEL = \"{pick}\"")
    except requests.RequestException as e:
        print("X  Could not reach Groq. Check your internet connection.", e)

print()
print("Done. If both say OK, restart the app:  python -m streamlit run app.py")
