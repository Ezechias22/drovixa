# Phase 10 — Profiles, offline playback, and casting

Phase 10 completes Drovixa's multi-viewer and device playback experience while
keeping Mux as the only video provider and the Render/Neon/Firebase staging
deployment introduced in Phase 9.1.

## Delivered

- Up to five viewer profiles per account with a persistent active profile.
- Optional four-to-six digit profile PINs and profile-specific autoplay and
  language preferences.
- Kids profiles with an age limit and server-side filtering on Home, Discover,
  Search, suggestions, Shorts, playback, and downloads.
- One five-star rating per viewer profile and title, with server-authoritative
  aggregate score and count.
- Premium offline movie and episode downloads stored only in the app-private
  mobile directory.
- Expiring, device-bound download licenses whose raw token is stored in native
  SecureStore and never persisted by the API.
- Signed Mux static MP4 rendition authorization. If Mux is still preparing a
  static rendition, the API returns `DOWNLOAD_PREPARING`; retry later.
- Chromecast support through Google Cast, AirPlay routing on iOS, playback
  speed controls, and audited cast-session telemetry.
- Mobile profile, download, offline player, and device-management screens.
- Public Web profile selection and a new Admin experience dashboard.

## New API surface

- `GET|POST /api/v1/profiles`
- `PATCH|DELETE /api/v1/profiles/{profile_id}`
- `POST /api/v1/profiles/{profile_id}/verify-pin`
- `GET|PUT|DELETE /api/v1/ratings/{content_id}`
- `POST /api/v1/downloads/episodes/{episode_id}/authorize`
- `POST /api/v1/downloads/movies/{movie_id}/authorize`
- `GET /api/v1/downloads`
- `PATCH /api/v1/downloads/{license_id}`
- `POST /api/v1/downloads/{license_id}/verify`
- `POST /api/v1/cast-sessions`
- `PATCH /api/v1/cast-sessions/{cast_id}`
- `GET /api/v1/admin/experience/summary`

Authenticated clients send the selected profile in
`X-Drovixa-Profile-ID`. The server still verifies profile ownership and Kids
rules; the header is not trusted as authorization by itself.

## Data migration

Alembic revision `20260824_0011` creates `viewer_profiles`,
`content_ratings`, `download_licenses`, and `cast_sessions`, adds
`content.rating_count`, and activates the existing Phase 10 feature flags.

The migration is additive and preserves all Phase 9 data. Never run
`docker compose down -v` during the upgrade.

## Native build requirement

Google Cast and the private file-system download implementation include native
modules. Expo Go cannot validate the complete Phase 10 experience. After the
overlay is installed and pushed, create a new EAS preview APK:

```powershell
Set-Location C:\Users\touss\DrovixaProject\drovixa\mobile
npx eas-cli@latest build --platform android --profile preview
```

The preview profile already points to
`https://drovixa-api-free.onrender.com/api/v1`. Firebase's Android service file
must remain configured in EAS exactly as it was for Phase 9.

## Operational notes

- The `super_admin` role may test Premium downloads in staging. Ordinary users
  still need an active Premium subscription.
- Mux static renditions may add storage/encoding usage to the Mux account.
- An offline license lasts 48 hours by default. Expired files remain unreadable
  until the user reconnects and downloads a newly authorized copy.
- Chromecast uses the default media receiver unless
  `GOOGLE_CAST_RECEIVER_APP_ID` is supplied at native build time.
- The Admin `/experience` page reports aggregate counts; it never exposes PINs,
  license tokens, or signed download URLs.

## Validation

For the local Docker stack:

```powershell
Set-Location C:\Users\touss\DrovixaProject\drovixa
.\scripts\verify-phase10.ps1
```

For Render, verify these URLs after the GitHub deployment finishes:

- `https://drovixa-api-free.onrender.com/api/v1/health/ready`
- `https://drovixa-web-free.onrender.com/profiles`
- `https://drovixa-admin-free.onrender.com/experience`

## Remaining roadmap

Two planned phases remain after Phase 10:

1. Phase 11: ads, daily rewards, referrals, social login, Watch Party, and
   growth automation.
2. Phase 12: final QA/security/performance, production monitoring and backups,
   signed store builds, legal/store assets, and submission readiness.

Store approval and third-party account verification remain external processes.
