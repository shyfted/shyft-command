# Shyft Command

Operational command interface for display content and device control at `cms.shyfted.com.au`.

## Configuration

Copy `.env.example` to `.env` in the deployment environment and set real values. Required production settings:

- `APP_URL=https://cms.shyfted.com.au`
- `DATABASE_URL=sqlite:///data/cms.db`
- `AUTH_SESSION_SECRET` set to a long random value
- `CMS_ADMIN_EMAIL` and `CMS_ADMIN_PASSWORD` for first-admin bootstrap
- SMTP settings for password reset email delivery
- Hanshow IntegrationProxy settings and `SHYFT_ESL_TARGETS` for ESL delivery

Do not commit `.env`, the SQLite database, uploaded media, or generated runtime state.

## ESL updates

The **ESL Updates** page is available from the hamburger menu. An authenticated
user chooses existing content, previews the target-sized E-Ink render, selects a
showroom display, and submits the update through the existing delivery adapter.
Version 1 exposes at most two `1600x1200` targets. `SHYFT_ESL_UI_TARGET_IDS` can
explicitly allow-list them when additional targets exist in `SHYFT_ESL_TARGETS`.

Command retains its internal `queued`, `rendered`, `submitting`, `accepted`, and
`failed` states while presenting Preparing, Sending, Update sent, and Failed to
customers. Update sent does not claim that the physical display refreshed.
Credentials, access tokens, bound SKUs, provider references, and image payloads
are not exposed in the UI or persisted in push history.

### ESL render profiles

Targets default to `monochrome_eink`. Compatible 13.3-inch Luminas may opt in
with `"render_profile":"lumina_six_colour"`. That profile proportionally fits
the source onto a white 1600 x 1200 canvas, then deterministically maps every
pixel to black, white, red, yellow, blue, or green using Pillow's nearest-colour
palette quantizer with dithering disabled. Preview and submission both use this
same renderer. The Hanshow material supplied with this project does not specify
the required PNG colour mode for `rsrvBlob`, so colour transport remains subject
to a separately approved physical test.

## Local Setup

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
export AUTH_SESSION_SECRET="$(python3 -c 'import secrets; print(secrets.token_urlsafe(48))')"
export SESSION_COOKIE_SECURE=false
export CMS_ADMIN_EMAIL=admin@example.com
export CMS_ADMIN_PASSWORD='replace-with-a-long-temporary-password'
flask --app app run --host 0.0.0.0 --port 5050
```

The app creates database tables automatically on startup. If no Shyft Command users exist yet and `CMS_ADMIN_EMAIL` and `CMS_ADMIN_PASSWORD` are set, the app creates the first admin account from those environment variables. After the first successful admin login, remove `CMS_ADMIN_EMAIL` and `CMS_ADMIN_PASSWORD` from the deployment environment. If users already exist, those variables are ignored. There is no public registration; after bootstrap, admins can create staff or admin users from `/users`.

## Production Run

Install dependencies in a virtual environment, provide environment variables through the host/process manager, and run:

```bash
gunicorn --bind 127.0.0.1:5050 app:app
```

Place a reverse proxy in front of Gunicorn for `https://cms.shyfted.com.au`, terminate TLS there, and forward requests to `127.0.0.1:5050`. Keep `SESSION_COOKIE_SECURE=true` in production.

## Auth Foundation

- Email/password login with secure password hashing.
- Logout clears the server-side session cookie data.
- Dashboard routes require an active authenticated user.
- Admin-only `/users` page can view, create, enable, disable, and delete users.
- Roles are `admin` and `staff`.
- Forgot/reset password uses random reset tokens; only token hashes are stored.
- Login and reset requests are rate limited per session/IP window for MVP pilot use.
- Sessions expire according to `SESSION_LIFETIME_HOURS`.
- The auth model is centralized around user/session helpers so 2FA can be added later without public registration.
