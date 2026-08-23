# Windows upgrade — Phase 11

This ZIP is a safe overlay for a working Phase 10 repository. It contains no
`.env`, `mobile/.env`, `google-services.json`, Neon password, Render Key Value
URL, Firebase service account, or Mux secret.

## Install

1. Start Docker Desktop and wait until the Linux engine is ready.
2. Put `drovixa-phase11-growth.zip` in Downloads.
3. Run the PowerShell block supplied with the ZIP handoff from a normal terminal.
4. Never add `-v` to `docker compose down`.

The block backs up PostgreSQL, preserves protected files, extracts the overlay,
runs `npm install`, validates all clients, rebuilds the stack, verifies migration
`20260825_0012`, commits, and pushes to `main` for Render auto-deployment.

## Render

No new paid Render service is required. API, Web, and Admin reuse the current
free deployment; Neon stores the new tables and Render Key Value continues to
serve caching/rate limiting. Worker/scheduler behavior remains compatible with
the Phase 9.1 free-mode configuration.

After auto-deploy, verify:

- `https://drovixa-api-free.onrender.com/api/v1/health/ready`
- `https://drovixa-web-free.onrender.com/rewards`
- `https://drovixa-admin-free.onrender.com/growth`

## Android

Phase 11's growth and Watch Party UI is JavaScript-only relative to the Phase 10
native build. An EAS Update may be used when runtime `0.11.0` already exists;
otherwise make a fresh preview APK:

```powershell
Set-Location C:\Users\touss\DrovixaProject\drovixa\mobile
npx eas-cli@latest build --platform android --profile preview
```

## First test

1. Sign in and open Profile → Rewards & referrals.
2. Claim the daily reward twice; only one ledger reward must appear.
3. Share your referral code and apply it from a second account.
4. Start a published title and tap Watch Party.
5. Join from another account, exchange chat messages, and verify only the host
   can change play/pause state.
6. Open Admin → Growth & Watch Party and inspect live totals/automations.

Keep the timestamped pre-Phase-11 dump until Render and Neon validation is done.
