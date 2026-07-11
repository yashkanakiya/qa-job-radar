# QA Job Radar - Hosted Scanner

Runs on GitHub's servers on a schedule and emails you when it finds new
remote QA/manual-tester roles, even if your laptop is off. Covers
RemoteOK, Remotive, and Arbeitnow. Indeed and LinkedIn can't be included -
both block automated access for every tool, no exceptions.

## Setup (about 10 minutes, one time)

### 1. Create the repo
- Go to github.com → **New repository** → name it something like `qa-job-radar` → **Private** is fine → Create.
- Upload these three items, keeping the folder structure:
  - `job_scanner.py`
  - `.github/workflows/scan.yml`
  - `README.md` (optional, just for your reference)

  Easiest way: on the new repo page, click **"uploading an existing file"**, drag in `job_scanner.py`, then separately create the path `.github/workflows/scan.yml` (GitHub lets you type a path with slashes when adding a new file, which auto-creates the folders).

### 2. Create a Gmail App Password (so the bot can send email)
- You need 2-Step Verification turned on for your Gmail account first: myaccount.google.com/security
- Then go to myaccount.google.com/apppasswords
- Create a new app password (name it "QA Job Radar"), copy the 16-character code it gives you. This is NOT your normal Gmail password - keep it private.

### 3. Add secrets to the repo
In your repo: **Settings → Secrets and variables → Actions → New repository secret**. Add three:

| Name | Value |
|---|---|
| `EMAIL_ADDRESS` | The Gmail address that will send the digest (can be your own) |
| `EMAIL_APP_PASSWORD` | The 16-character app password from step 2 |
| `EMAIL_TO` | Where you want digests delivered — e.g. `yashkanakiya281297@gmail.com` |

### 4. Turn it on
- Go to the **Actions** tab of your repo → you'll see "QA Job Radar Scan" → click **Enable workflow** if prompted.
- Click **Run workflow** once manually to test it. Check your inbox in a minute or two.
- After that, it runs automatically every 30 minutes, forever, for free — no need to open anything.

## Notes
- GitHub's schedule can lag a few minutes during peak load — that's normal, not a bug.
- It only emails you when it finds a NEW job it hasn't seen before (tracked in `seen_jobs.json`, which the workflow updates itself each run).
- Free GitHub accounts get unlimited Actions minutes on public repos, and 2,000 free minutes/month on private repos — this job takes under a minute per run, so you're well within the free tier either way.
- To adjust frequency, edit the `cron` line in `.github/workflows/scan.yml` (e.g. `*/15 * * * *` for every 15 minutes).
- To change keywords or add resume skills, edit the `RESUME_SKILLS` / `ROLE_KEYWORDS` lists near the top of `job_scanner.py`.
