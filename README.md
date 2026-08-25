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
The workspace supports the proven `1600x1200` 13.3-inch Lumina profile and the
`672x960` 9.7-inch Nebular Pro profile. `SHYFT_ESL_UI_TARGET_IDS` can explicitly
allow-list the displays exposed from `SHYFT_ESL_TARGETS`.

Command retains its internal `queued`, `rendered`, `submitting`, `accepted`, and
`failed` states while presenting Preparing, Sending, Update sent, and Failed to
customers. Update sent does not claim that the physical display refreshed.
Credentials, access tokens, bound SKUs, provider references, and image payloads
are not exposed in the UI or persisted in push history.

### ESL render profiles

Targets default to `monochrome_eink`. The 13.3-inch Lumina and 9.7-inch Nebular
Pro use `"render_profile":"six_colour_eink"`. That profile proportionally fits
the source onto the target's white canvas, then deterministically maps every
pixel to black, white, green, red, yellow, or blue using Pillow's nearest-colour
palette quantizer with dithering disabled. Preview and submission both use this
same renderer. The legacy `lumina_six_colour` profile name remains supported.
The Hanshow material supplied with this project does not specify
the required PNG colour mode for `rsrvBlob`, so colour transport remains subject
to a separately approved physical test.

Before staging, Command checks that media is readable, uses an approved source
type, is compatible with the selected display family, and has an aspect ratio
that can be fitted safely. Differing source resolutions remain supported when
the approved renderer can adapt them. Immediately before submission, Command
also verifies that the result is a valid PNG at the target's exact dimensions.

Every configured ESL target must have a unique device ID and a unique Hanshow
article SKU. Command rejects the entire ESL target configuration when a SKU is
shared, preventing a single individual-display push from fanning out to more
than one physical ESL.

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
