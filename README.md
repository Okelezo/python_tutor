# Python Project Tutor

An interactive tutor to help you master Python from basics to advanced topics.

## Features
- CLI tutor (fast practice loop)
- Web tutor (UI)
- Auto-graded coding exercises (unit-test style)
- Multi-user accounts (register/login/logout)
- Progress tracking per user (SQLite)
- AI help (hint/explain/review) using BYOK (bring your own OpenAI key)

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

Create a local `.env` (optional) by copying `.env.example` to `.env`.
The `.env` file is ignored by git.

## Run (CLI)

```bash
pytutor track list
pytutor track start fundamentals
```

## Run (Web)

```bash
pytutor-web
```

Then open: http://127.0.0.1:8010

## Accounts

When running the web app you must:
- Register at `/auth/register`
- Login at `/auth/login`

## AI (Safest mode: BYOK only)

This project is configured to be safe for public deployment:
- The server **does not use** a shared OpenAI key.
- Each user pastes their **own** OpenAI key into the exercise page.
- The key is stored only in that user's browser (localStorage).

## Deploy to Railway (shareable)

Recommended for multi-user usage:

1. Deploy from GitHub.
2. Set the service root directory to:

   `python-project-tutor`

3. Add a persistent volume and mount it at `/data`.
4. Set Railway Variables:

   - `PYTUTOR_COOKIE_SECURE=1`
   - `PYTUTOR_DB_PATH=/data/pytutor.db`

Optional extra protection (in addition to accounts):

   - `PYTUTOR_BASIC_AUTH_USER=...`
   - `PYTUTOR_BASIC_AUTH_PASS=...`

Notes:
- Railway provides `PORT` automatically; the app will bind to `0.0.0.0` and that port.
- Without a mounted volume + `PYTUTOR_DB_PATH`, the SQLite DB may reset on redeploy.
