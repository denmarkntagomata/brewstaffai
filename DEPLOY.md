# Put BrewStaffAI Online (free) — Step by Step

When you're done, BrewStaffAI has **one link** that the manager, staff, and groupmates open on any phone or laptop. Everyone shares **one database**: the same accounts, reports, and plans.

```
 Phone / laptop  ──►  Streamlit Community Cloud (the app, free)  ──►  Neon (the database, free)
                           code comes from GitHub                     accounts · reports · plans · log
```

**Cost: ₱0.** No credit card needed for either service.

---

## Part A: Create the free database (Neon) — 10 minutes

1. Go to **https://neon.com** and click **Sign up**. Choose **Continue with GitHub** (easiest) or Google.
2. Create a project:
   - **Project name:** `brewstaffai`
   - **Postgres version:** keep the default
   - **Region:** choose **AWS US East (N. Virginia)**. Streamlit Cloud runs in the US, so this is the fastest choice.
   - Click **Create project**.
3. On the project dashboard, click **Connect** (top right).
4. Copy the **connection string**. It looks like:
   ```
   postgresql://neondb_owner:AbC123xyz@ep-cool-name-123456.us-east-1.aws.neon.tech/neondb?sslmode=require
   ```
   ⚠️ **This string contains the database password. Treat it like an API key**: never post it in the group chat or put it on GitHub.

That's all. BrewStaffAI creates its own tables the first time it connects.

## Part B: Test the cloud database on your laptop — 5 minutes

1. Open `.streamlit/secrets.toml` and add these lines at the top. Paste your Neon string between the quotes, and make up your own setup code (only you should know it):
   ```toml
   DATABASE_URL = "postgresql://neondb_owner:...neon.tech/neondb?sslmode=require"
   SETUP_CODE = "make-up-a-long-code-only-you-know"
   ```
   ⚠️ When you copy the string from Neon, click **Show password** first. A copied `****` password causes "wrong password".
2. Save, then restart the app:
   ```
   python -m pip install -r requirements.txt
   python -m streamlit run app.py
   ```
3. You'll see **First-time setup** again. That's correct: the cloud database starts empty. Type your **setup code**, then create the real manager account.
4. Go to **Settings → Data & backup**. It should say **Cloud** and **Online**.

## Part C: Put the app online (Streamlit Community Cloud) — 10 minutes

1. Make sure your latest code is on GitHub (Source Control → Commit → Sync). `secrets.toml` is never uploaded.
2. Go to **https://share.streamlit.io** and click **Continue with GitHub**.
3. Click **Create app** → **Deploy a public app from GitHub**:
   - **Repository:** `denmarkntagomata/brewstaffai`
   - **Branch:** `main`
   - **Main file path:** `app.py`
   - **App URL:** choose a name, e.g. `brewstaffai-junglebrew`
4. Click **Advanced settings**:
   - **Python version:** 3.12
   - **Secrets:** open your local `.streamlit/secrets.toml`, copy **everything** (DATABASE_URL, SETUP_CODE, Gemini, Groq lines), and paste it here.
5. Click **Deploy**. The first start takes 2–5 minutes while it installs the libraries.
6. Open your link, e.g. `https://brewstaffai-junglebrew.streamlit.app`, and log in with the manager account from Part B. It's the same database, so the account already exists.

## Part D: Add the team

1. Log in as the manager → **Settings → Team accounts → Add a team member**.
2. Give each person their **temporary password privately**. They choose their own password at first login.
3. Send everyone the link. On phones, they can tap **Share → Add to Home Screen** so it opens like an app.

---

## Good to know

| Situation | What happens | What to do |
|---|---|---|
| Nobody used the app for a while | Streamlit Cloud puts it to sleep | Open the link, click **"Yes, get this app back up!"**, and wait about 30 seconds |
| First request after 5 idle minutes | Neon wakes the database | About a 1-second delay, automatic |
| You refresh the browser page | You stay logged in (a login cookie), unless you were idle for 30 minutes | Nothing. On a shared café device, always press **Log out** |
| Someone opens the link before the manager exists | They see "Setup is locked" or need the setup code | Only the person with `SETUP_CODE` can create the first manager |
| Archived reports | Deleted automatically 30 days after archiving | Download a backup first if you need them for the paper |
| You push new code to GitHub | Streamlit Cloud updates the app automatically | Data stays safe in Neon |
| Pilot week | Data is saved in Neon, not on the app server | Download **Settings → Data & backup → Full backup** daily anyway |
| Groupmates testing on their laptops | Without `DATABASE_URL`, they use their own local database | Fine for QA; the real data is only in the online app |

**Free limits (more than enough for a café pilot):**
- Neon free: 1 GB storage (BrewStaffAI uses well under 10 MB for a month of reports).
- Streamlit Community Cloud: unlimited public apps that sleep when unused.

## If something goes wrong

| Error | Fix |
|---|---|
| "Can't connect to the database: wrong password" | Copy the connection string from Neon again (click **Show password** first). You can reset the password in Neon → Roles. |
| "the address in DATABASE_URL is wrong" | The host part was cut off. Copy the whole string again. |
| "Can't reach the database right now" | Check the internet. Neon may be waking up: wait a few seconds and press **Try again**. |
| "Setup is locked" | Add `SETUP_CODE = "..."` to Secrets, then reload the app. |
| App shows "Error installing requirements" | Make sure `requirements.txt` is on GitHub, then click **Reboot app** in Streamlit Cloud |
| AI says offline only online | You forgot to paste the Gemini/Groq lines in the Streamlit Cloud **Secrets** |
| Need to start over with an empty database | Neon → your project → **Branches** → reset, or create a new project and update DATABASE_URL |
