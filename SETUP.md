# Setup Guide — Daily Wisdom Faith

One-time setup, ~30 minutes. After this you never touch any of it again — you
just drop files into Drive each day.

> ## Are API keys in GitHub safe?
>
> **Yes, when you use GitHub Secrets** (which is what we do). Secrets are
> encrypted at rest by GitHub, never appear in your code or commits,
> auto-redact from workflow logs, and can be rotated any time. Your code only
> references them by name (`${{ secrets.OLLAMA_API_KEY }}`), never a literal
> value.
>
> What's *unsafe* is hardcoding keys directly in source files, committing
> `.env` files, or making the repo public with secrets exposed. Our
> `.gitignore` blocks the dangerous patterns.
>
> Three things you should still do:
> 1. Keep the GitHub repo **private**.
> 2. Turn on **2FA** for your GitHub account.
> 3. Never paste secrets into chat tools, screenshots, or emails.
>
> If a key ever leaks: rotate it in the provider's dashboard, update the
> GitHub Secret, you're safe in under a minute.

## Pre-flight checklist

- [ ] You have access to the Google account that owns
      [@DailyWisdomFaith](https://www.youtube.com/@DailyWisdomFaith)
- [ ] A laptop/desktop with Python 3.11+ and FFmpeg installed
      (Mac: `brew install python ffmpeg`)
- [ ] A free GitHub account
- [ ] An Ollama Cloud account with API key

---

## Step 1 — Create a Google Cloud project (10 min)

The system uploads to YouTube and reads from Drive using one set of OAuth
credentials. You need a free Google Cloud project to issue them.

1. Go to <https://console.cloud.google.com/projectcreate>
2. Project name: `daily-wisdom-faith`. Click **Create**.
3. Wait for the project to be created, then make sure it's selected in the
   top dropdown.
4. **Enable the APIs we need.** For each link below, click and then click
   **Enable**:
   - <https://console.cloud.google.com/apis/library/youtube.googleapis.com>
   - <https://console.cloud.google.com/apis/library/drive.googleapis.com>
5. **Configure the OAuth consent screen** —
   <https://console.cloud.google.com/apis/credentials/consent>
   - User type: **External** → Create
   - App name: `Daily Wisdom Faith`
   - User support email: your email
   - Developer contact: your email
   - Save and Continue through the rest (no scopes needed here, we request them
     at runtime)
   - On **Test users**: add the Google account that owns
     `@DailyWisdomFaith`. **This is critical** — without it the consent flow
     will fail.
   - Save.
6. **Create OAuth credentials** —
   <https://console.cloud.google.com/apis/credentials>
   - Click **+ Create Credentials** → **OAuth client ID**
   - Application type: **Desktop app**
   - Name: `daily-wisdom-bootstrap`
   - Click **Create**
   - A dialog will show a Client ID and Client Secret. **Click "Download
     JSON"** and save the file as `client_secret.json` in the repo root.

---

## Step 2 — Run the bootstrap (5 min)

The bootstrap does OAuth, creates Drive folders, and prints the values you'll
paste into GitHub Secrets in the next step.

```bash
cd "/path/to/PRAYER CHANNEL"
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python scripts/bootstrap.py
```

A browser window will open. Sign in with the
**@DailyWisdomFaith Google account** and click **Allow** for both YouTube and
Drive. (You may see a "Google hasn't verified this app" warning — click
**Advanced → Go to Daily Wisdom Faith (unsafe)**. This is normal for personal
OAuth apps; the app is yours.)

When it finishes, the script will print a block like:

```
GOOGLE_CLIENT_ID         = 1234...apps.googleusercontent.com
GOOGLE_CLIENT_SECRET     = GOCSPX-...
GOOGLE_REFRESH_TOKEN     = 1//04...
DRIVE_QUEUE_FOLDER_ID    = 1A2B3C...
```

**Copy those four values somewhere safe.** You'll paste them into GitHub in
Step 5.

Open Drive — you should now see a `prayer-channel-queue/` folder with 30
date-named subfolders, plus `default/` and `published/`.

---

## Step 3 — Get an Ollama Cloud API key (2 min)

1. Sign in at <https://ollama.com/cloud>
2. Go to your **API Keys** page and create a new key
3. Save the key
4. Note the exact model name available to you. The repo defaults to
   `deepseek-v4-flash` — if your account has a different DeepSeek variant
   (V3, V3.1, etc.), note that name; you'll set it as `OLLAMA_MODEL` in
   Step 5.

> **If `deepseek-v4-flash` doesn't exist on your account**, try the model name
> shown in your Ollama Cloud console. Any reasonably capable text model works
> — the prompt is robust. If quality is poor you can swap models without
> redeploying anything.

---

## Step 4 — Create the GitHub repo and add secrets (5 min)

1. Create a new private GitHub repo (any name, e.g. `daily-wisdom-pipeline`)
2. Push the contents of this folder to it:
   ```bash
   git init
   git add .
   git commit -m "Initial commit"
   git branch -M main
   git remote add origin https://github.com/<your-username>/<repo-name>.git
   git push -u origin main
   ```
   *Make sure `client_secret.json` and `.env` are NOT pushed — `.gitignore`
   already excludes them, but double-check with `git status` before commit.*

3. In the GitHub web UI, go to **Settings → Secrets and variables → Actions →
   New repository secret** and add each of these:

   | Secret name              | Value                                          |
   | ------------------------ | ---------------------------------------------- |
   | `GOOGLE_CLIENT_ID`       | from Step 2 bootstrap output                   |
   | `GOOGLE_CLIENT_SECRET`   | from Step 2 bootstrap output                   |
   | `GOOGLE_REFRESH_TOKEN`   | from Step 2 bootstrap output                   |
   | `DRIVE_QUEUE_FOLDER_ID`  | from Step 2 bootstrap output                   |
   | `OLLAMA_API_KEY`         | from Step 3                                    |
   | `SMTP_APP_PASSWORD`      | *(optional)* from Step 5 below                 |

4. *(Optional but recommended)* In the same UI, switch to the **Variables** tab
   and override defaults if you want a different model:
   - `OLLAMA_MODEL` — e.g. `deepseek-v3.1` if you don't have v4-flash
   - `OLLAMA_API_BASE` — only if Ollama Cloud changes their endpoint

---

## Step 5 — (Optional) Gmail App Password for richer emails

**You can skip this entirely.** Without it, the system runs fine — GitHub
Actions still emails you whenever a workflow fails (using your GitHub account
email), and you can check the YouTube channel directly to confirm uploads.

If you want extra confirmation emails *and* failure logs sent to your inbox:

1. Turn on 2-Step Verification at <https://myaccount.google.com/security>
2. Create an App Password at <https://myaccount.google.com/apppasswords>
3. Paste the 16-character code as a GitHub secret named `SMTP_APP_PASSWORD`

---

## Step 6 — Verify with a manual run (3 min)

In your GitHub repo:

1. Go to **Actions** tab
2. Click **Daily Upload — 9 AM IST** in the left sidebar
3. Click **Run workflow** → **Run workflow**
4. Wait ~3 minutes
5. Either:
   - Today's Drive folder has audio+video → it will publish a real scheduled
     video to YouTube (private, scheduled to go public at 9 AM IST tomorrow if
     today's slot has passed)
   - Today's folder is empty AND no `default/` content → the run fails with a
     clear error and emails you. Drop a fallback audio+video into the
     `default/` Drive folder once and you'll never see this error again.

You should also get a confirmation email at `naveends798@gmail.com`.

---

## Step 7 — Optional: local smoke test of the AI metadata + thumbnail crop

To verify your Ollama key and try the thumbnail processor without touching
Drive or YouTube:

```bash
cp .env.example .env
# fill in OLLAMA_API_KEY
python scripts/test_pipeline.py "trust-in-the-lord-psalm-23" /path/to/your-thumbnail.jpg
open out/thumbnail.jpg
```

You'll see the AI-generated title/description and the resized thumbnail.
If the title quality looks off, try a different `OLLAMA_MODEL`.

---

## Daily routine after setup

1. **Generate a song on Suno** — pick a topic from `topics.txt` or your own.
2. **Save the .mp3** with the kebab-case topic name, e.g.
   `trust-in-the-lord-psalm-23.mp3`.
3. **Pick a video clip** — any short atmospheric loop (.mp4). One file, you
   can reuse it across many days. 10–60 seconds is fine; the system loops it.
4. **Make a thumbnail** — any .jpg or .png. The system resizes/crops it to
   YouTube's 1280×720 spec automatically (16:9 center-crop).
5. **Open Drive** → `prayer-channel-queue/` → click into a future date folder
   → upload all three files.
6. Done. On that date at 9 AM IST, it auto-posts.

You can prep a week or a month of content in one sitting.

---

## Troubleshooting

- **"Empty response from Ollama"** — your Ollama Cloud key is invalid or the
  model name doesn't exist on your account. Update `OLLAMA_API_KEY` or
  `OLLAMA_MODEL` (variable, not secret).
- **"Google did not return a refresh token"** — re-run the bootstrap after
  revoking prior consent at
  <https://myaccount.google.com/permissions>.
- **YouTube upload returns 403 quotaExceeded** — by default YouTube Data API
  allows 10,000 units/day; one upload uses ~1,600 so the daily 9 AM run is
  fine. If you trigger many manual runs, wait until midnight Pacific.
- **Channel goes silent** — check the latest workflow run in GitHub Actions
  for errors. The failure email should also include the log tail.
- **Want to skip a day** — leave the folder empty and remove the `default/`
  fallback; the run will fail loudly. Or just don't worry about it; missing one
  day is fine.
