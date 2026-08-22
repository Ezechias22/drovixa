# Phase 10 overlay manifest

This overlay contains only Phase 10 source changes. It is designed to be
expanded over the GitHub-synced Phase 9.1 repository without replacing local or
hosted secrets.

## Included areas

- Backend profile, Kids, rating, download-license, cast-session, playback, and
  experience code.
- Alembic revision `20260824_0011` and automated tests.
- Mobile native casting/file-system dependencies, profile/download/device and
  offline-player screens, and production API EAS configuration.
- Web profile selection and Admin experience monitoring.
- Package lock, version metadata, validation script, and Phase 10 guides.

## Explicitly excluded

- `.env` and `mobile/.env`
- `google-services.json` and `GoogleService-Info.plist`
- Firebase service-account JSON
- Neon, Redis, Mux, JWT, admin-password, or Render credentials
- `.git`, `node_modules`, `.next`, `.expo`, caches, and build output
- Phase 9.1 files unrelated to Phase 10

The installation command must run `npm install` after extraction and create a
new EAS preview build because Google Cast is a native dependency.
