# Windows upgrade — Phase 10

This package is a safe overlay for the existing Phase 9.1 repository. It does
not contain `.env`, `mobile/.env`, `google-services.json`, Neon credentials,
Firebase credentials, Mux credentials, or Render Key Value credentials.

## Before installing

- Let any EAS build already running finish. That APK is still a Phase 9 build.
- Start Docker Desktop and wait until the engine is ready.
- Confirm the ZIP is named `drovixa-phase10-complete.zip` in Downloads.
- Do not use `docker compose down -v`.

## Install, validate, and deploy

Run the complete PowerShell block supplied with the ZIP handoff. It creates a
local PostgreSQL backup, extracts the overlay, installs the two new native
packages, rebuilds Docker, verifies migration `20260824_0011`, checks that no
secret is tracked, and pushes to `main`.

Render auto-deploys API, Web, and Admin from GitHub. The API start command from
Phase 9.1 applies the new Alembic migration to Neon before Uvicorn starts.

## Build the installable Android app

After Render is live and the verification commands pass:

```powershell
Set-Location C:\Users\touss\DrovixaProject\drovixa\mobile
npx eas-cli@latest build --platform android --profile preview
```

Open the EAS build link, download the APK on the Android phone, permit installs
from that browser when Android asks, and install it. This Phase 10 APK no longer
depends on scanning an Expo Go QR code.

## First device test

1. Sign in with the super-admin account.
2. Open Profile, then Profiles, and create a normal and a Kids profile.
3. Select the Kids profile and confirm mature titles disappear.
4. Rate a title from its detail page.
5. Start a ready Mux title and test speed plus Chromecast/AirPlay when available.
6. Tap Download. A first attempt can report that Mux is preparing the rendition;
   wait and retry.
7. Open Downloads, disconnect Wi-Fi, and play the downloaded title.
8. Open Devices and revoke an old session.
9. Sign in to the Admin dashboard and open Experience.

## Rollback boundary

Keep the timestamped local dump created before installation. The Phase 10
migration is additive, but do not manually downgrade Neon while a Phase 10
service is running. If deployment fails, stop the Render auto-deploy and inspect
its first exception before restoring any database.
