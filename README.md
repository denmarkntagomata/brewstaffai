# BrewStaffAI — Version 4.2.1

AI-Based Staffing Recommendation System for Jungle Brew Café, Parañaque City.
Internal system: **Manager and Staff only.**

## What's new in v4.2.1

| Area | What changed |
|---|---|
| Built-in User Guide (manager) | **How the AI Works** now has two tabs: **How the AI works** (the same accuracy and charts for the panel) and **User guide**. The guide is visual: pick a topic (Daily routine, Staffing Planner, Staff Reports, Pilot Results, Settings, Colors & AI, Troubleshooting, Glossary & help) and see numbered step cards, color legends, and tap-to-open FAQs. |
| Built-in User Guide (staff) | **Settings** now has three tabs: **My account**, **User guide** (staff tasks only: get started, send a report, report an incident, My Reports, troubleshooting, glossary), and **How the AI works** (a simple 4-step explanation with the color legend, no charts). |
| Help contact | The Glossary & help section shows: *Need help? Contact the BrewStaffAI team leader, Denmark Nercua Tagomata, at denmarkntagomata.pup@gmail.com.* |
| No logic changes | The AI model, recommendations, database, and all v4.2 features are unchanged. The guide lives in its own file, `guide.py`. |

**Upgrading from v4.2:** replace the files and push. No database or Secrets changes are needed.

## What was new in v4.2

| Area | What changed |
|---|---|
| 12-hour time (both sides) | All times now show the Philippine way with AM/PM, e.g., **1:00 PM – 2:00 PM** and **Oct 31, 2026 · 11:27 PM**. The AI explanations are also asked to use AM/PM. Times are still saved in 24-hour form in the database, so nothing changes in the data or the AI logic. |
| Edit or delete today's plan (manager) | The Dashboard now has **Edit plan** and **Delete plan** under today's staffing plan. Edit lets you change customers, cashiers, or baristas per hour; changed hours are re-checked by the AI before saving. Delete asks for confirmation first. Both are recorded in the activity log. |
| Archive is easy to find (manager) | An **Archive (n)** button now sits right under **Refresh** on Staff Reports. Each report card has its own **Archive** button (no more hidden dropdown); a small pop-up asks for the reason. Inside the archive you can **Restore** or **Delete now** (with a confirmation pop-up). |
| Activity log tab (manager) | The activity log table moved to its own **Settings → Activity log** tab, right after Data & backup. The "Activity log · n events" card stays on Data & backup. |
| Friendlier Pilot Results (manager) | New **How to use this page** guide (open by default until there is pilot data), numbered tabs, and short "how to read this chart" notes under each result. |
| Delete confirmation (staff) | Pressing **Delete report** now opens a pop-up: *"Are you sure…? Once deleted, it cannot be recovered. If you change your mind, you will need to send a new report."* |
| Cleaner code | Simpler section comments and a small `timefmt.py` helper for all time labels. No changes to the AI model, recommendation logic, or database data. |

**Upgrading from v4.1:** just replace the files (keep your `.streamlit/secrets.toml`). No database changes are needed.

## What was new in v4.1

| Area | What changed |
|---|---|
| Manager decides | In **Plan the day**, the manager can change the cashiers/baristas for any hour before publishing. The AI re-checks those hours and shows the new expected wait. The AI's original crew is saved next to the final crew, and the activity log records how many hours were changed. |
| Privacy notice | Every user reads and accepts a one-time privacy notice (Data Privacy Act of 2012, RA 10173) before using the system. Users can read it again in **Settings → My account**. Accepting or declining is logged. |
| Accuracy per level | **How the AI Works** now shows precision, recall, and F1-score for Okay, Congested, and Overloaded, plus a short explanation of where the AI makes mistakes. |
| Response time | **How the AI Works** shows how fast one AI prediction is, and the average time for planning a day, testing an hour, and AI tagging (measured automatically while the app is used). Included in the backup ZIP as `response_times.csv`. |
| Small fixes | Chart labels no longer overlap; single-topic charts no longer show one very thick bar. |

## What was new in v4

| Area | What changed |
|---|---|
| Stay logged in | Refreshing the page no longer logs you out. A secure cookie keeps you in for up to 30 minutes of no activity. Logging out ends it right away. |
| Refresh button | Top right of every page: loads the latest data without logging out. |
| Staff: edit or delete | Staff can fix or delete their own report within 24 hours, while it is open and before the manager replies. Every change is in the activity log. |
| Manager reply | The manager can reply to any report. The staff member sees it in **My Reports**. |
| Archive | The manager archives a report with a reason (logged). Archived reports are hidden from charts, can be restored, and are **deleted automatically 30 days after archiving**. |
| Notification badges | Sidebar shows **Staff Reports (2)** for new reports and **My Reports (1)** for new replies. |
| Weekly summary as CSV | The AI weekly summary can be downloaded as a CSV file (no PDF). |
| Pilot Results page | Day-by-day agreement between the AI prediction and what staff felt, with charts and CSV downloads. |
| Tagging accuracy check | The team hand-labels reports without seeing the AI tags. The app computes the match rate against the 80% target (goal: 50 reports). |
| Clear errors | Database problems show plain messages, for example "Can't connect to the database: wrong password". |
| Setup code | On the online app, the first manager account can only be created with the `SETUP_CODE` from Secrets. |
| Simpler screens | Planner uses the café defaults from Settings (no sliders). "Test a specific hour" shows the gauge and options chart; the rest is under **Details for the panel**. Plain words, cleaner icons. |

**Upgrading from v3:** copy your `.streamlit/secrets.toml` into this folder and add a `SETUP_CODE` line (see `.streamlit/secrets.toml.example`). The database updates itself on first start; existing accounts and reports are kept.

## First run

```
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

1. With no accounts yet, the first screen is **First-time setup**. Create the manager account with a `@junglebrewpq.com` email and a strong password. (Online, you also need the `SETUP_CODE`.)
2. Log in as **Manager**.
3. **Settings → Team accounts → Add a team member** creates staff accounts. Copy the one-time temporary password and give it to the person privately.
4. The staff member logs in as **Staff** and must choose their own password right away.

## Pages

**Manager**
- **Dashboard:** today's plan (with **Edit plan** / **Delete plan**), open issues, latest reports
- **Staffing Planner**
  - *Plan the day:* the AI plans every hour; publish it to staff
  - *Test a specific hour:* try one hour (promo, someone absent)
- **Staff Reports:** AI-tagged reports, charts, weekly summary (CSV), resolve, reply, archive (Archive button under Refresh)
- **Pilot Results:** AI vs. staff agreement by day, and the tagging accuracy check
- **How the AI Works:** visual explanation for the panel, plus the **User guide** tab
- **Settings:** account, team, café defaults, AI services, data & backup, activity log

**Staff**
- **My Shift Today:** the published crew plan and quick buttons
- **End-of-Shift Report** and **Report an Incident**
- **My Reports:** tags, manager replies, edit or delete within 24 hours
- **Settings:** change password, **User guide**, and a simple **How the AI works**

## Security

| Protection | How it works |
|---|---|
| Company emails only | Only **@junglebrewpq.com** addresses; personal emails are refused |
| Strong passwords | 12+ characters with uppercase, lowercase, number, symbol; common words blocked |
| Encrypted storage | Passwords saved as salted PBKDF2-SHA256 hashes (200,000 rounds), never as plain text |
| Lockout | 5 wrong tries lock the account for 5 minutes |
| Auto logout | After 30 minutes of no activity |
| Login cookie | Holds a random token only; the database stores just its SHA-256 hash. Ends on logout, password reset, or deactivation |
| Role check | Staff cannot open manager pages; the login also checks the chosen role |
| No default passwords | First manager is created with the setup code; staff get one-time temporary passwords |
| Safe display | Text typed by users or returned by the AI is escaped before it is shown |
| AI privacy | Staff names removed before text goes to Gemini/Groq; keys kept out of the code |
| Shared cloud database | Neon PostgreSQL over SSL; the connection string is kept in Secrets |
| Activity log | Logins, account changes, report edits, replies, archives, deletes, and exports are recorded |

## AI keys

Check them with `python test_keys.py` or in **Settings → AI services → Test AI connection**.
Without keys, AI boxes say "Basic summary (AI is unavailable right now)" and the app still works.

## Files

| File | Purpose |
|---|---|
| `app.py` | Start here: login check, sidebar menu, badges, auto logout, error screen |
| `login_page.py` | Login screen and first-time setup |
| `session_cookie.py` | Stay logged in after a page refresh |
| `privacy.py` | One-time privacy notice and consent |
| `timefmt.py` | 12-hour (AM/PM) time labels |
| `guide.py` | Built-in User Guide (manager and staff) and the simple "How the AI works" for staff |
| `auth.py` | Email, password, lockout, and timeout rules |
| `db.py` | Database (Neon PostgreSQL online, SQLite locally) |
| `pages_manager.py` / `pages_pilot.py` / `pages_staff.py` / `settings_page.py` | The pages |
| `ui.py` / `charts.py` | Styling and charts |
| `ai_helper.py` | Gemini (main) / Groq (backup) / offline fallback |
| `recommender.py` | Decision Tree prediction, recommendation, simulation double-check |
| `sim_engine.py`, `generate_dataset.py`, `train_model.py`, `labels.py` | Simulator, dataset, and model training |

## Notes and assumptions

- Hourly customer numbers in **Settings → Café defaults** are placeholders from the COMP 014 observation (about 24 customers/hour at the noon peak). Update them after the re-observation.
- Pilot Results defaults to the pilot week (Nov 21–28, 2026) once it starts; before that it shows the last 7 days. You can pick any dates.
- The tagging check only uses reports that have text. Editing a report clears its check label, because the AI re-tags it.
- Archived reports disappear from the staff member's **My Reports** too.
- If a browser blocks cookies, the app still works; a refresh just asks for the password again.
