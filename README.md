# BrewStaffAI — Version 2

AI-Based Staffing Recommendation System for Jungle Brew Café, Parañaque City.
Internal system: **Manager and Staff only.**

## What's new in v2

| Area | What changed |
|---|---|
| 🔐 Login | Split screen with the Jungle Brew storefront photo and round logo. Choose **Staff** or **Manager**, then log in with your work email. |
| 🛡️ Security | Only `@junglebrewpq.com` emails · strong passwords (12+ characters, upper, lower, number, symbol) with a live checklist · 5 wrong tries = 5-minute lock · auto logout after 30 minutes · no default passwords · new staff must set their own password on first login |
| 🧭 Easier to use | Grouped sidebar menu with icons · every page says what it's for · numbered steps · large buttons |
| 📊 Visual AI results | Hour-by-hour color strip, crew vs. customers chart, wait-time gauges, confidence bar, chart of every staffing option, sentiment donut, topic chart, accuracy gauge, confusion matrix |
| ⚙️ Settings | One page with tabs: My account · Team accounts · Café defaults · AI services · Security |

## First run (important)

```
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

1. Because there are no default passwords, the first screen is **First-time setup**. Create the manager account with a `@junglebrewpq.com` email and a strong password.
2. Log in as **Manager**.
3. Go to **Settings → Team accounts → Add a team member** to create staff accounts. The app shows a **one-time temporary password**: copy it and give it to the staff member privately.
4. The staff member logs in as **Staff** and must choose their own password right away.

Your v1 database (with `staff1`, `manager`) is automatically backed up as `data/brewstaff_v1_backup.db` and not used anymore.

## AI keys

Keep your existing `.streamlit/secrets.toml` from v1 (copy it into this folder's `.streamlit` folder). Check the keys with:
```
python test_keys.py
```
You can also check them in **Settings → AI services → Test AI connection**.

## Pages

**Manager**
- 🏠 **Dashboard:** today at a glance (plan, open issues, reports, AI accuracy vs. real shifts)
- 📅 **Staffing Planner**
  - *Plan the whole day:* the AI plans every hour, then you publish to staff
  - *Check one hour in detail:* prediction, recommendation, simulation check, and AI Insight
- 🗂️ **Staff Reports:** AI-tagged reports, charts, AI weekly summary, resolve issues, CSV download
- 🧠 **How the AI Works:** a visual explanation for the panel (pipeline, accuracy, what the AI looks at, real-world check)
- ⚙️ **Settings**

**Staff**
- 🏠 **My Shift Today:** the published crew plan and quick buttons
- 📝 **End-of-Shift Report:** the AI tags it and compares "you felt" vs. "AI predicted"
- ⚠️ **Report an Incident**
- 📄 **My Reports**
- ⚙️ **Settings:** change password

## Files

| File | Purpose |
|---|---|
| `app.py` | Start here: login check, sidebar menu, auto logout |
| `login_page.py` | Split-screen login and first-time setup |
| `auth.py` | Security rules (email domain, password strength, lockout, timeout) |
| `db.py` | SQLite database (users, reports, plans, settings) |
| `pages_manager.py` / `pages_staff.py` / `settings_page.py` | The pages |
| `ui.py` / `charts.py` | Styling and infographic charts |
| `ai_helper.py` | Gemini (main) / Groq (backup) / offline fallback |
| `recommender.py` | Decision Tree prediction + staffing recommendation + simulation check |
| `sim_engine.py`, `generate_dataset.py`, `train_model.py`, `labels.py` | Simulator, dataset, and model training (unchanged from v1) |
| `assets/` | Jungle Brew logo and storefront photo |

## Notes and assumptions

- The hourly customer numbers in **Settings → Café defaults** are placeholders based on the COMP 014 observation (~24 customers/hour at the noon peak). Update them after the re-observation.
- Every wait-time number uses the same 10 simulation runs, so the gauge, charts, and AI text always agree.
- Without API keys, AI boxes show "AI service offline · showing a template answer". The app still works.
