# Phase 11 overlay manifest

The Phase 11 ZIP is an additive overlay for a verified Phase 10 repository. It
contains the following 40 files beneath the top-level `drovixa/` directory.

## Root and release metadata

- `.env.example`
- `README.md`
- `package.json`
- `package-lock.json`

## Backend and database

- `backend/.env.example`
- `backend/app/api/router.py`
- `backend/app/core/version.py`
- `backend/app/models/__init__.py`
- `backend/app/models/growth.py`
- `backend/app/routes/admin_growth.py`
- `backend/app/routes/growth.py`
- `backend/app/schemas/growth.py`
- `backend/app/services/growth.py`
- `backend/migrations/versions/20260825_0012_phase11_growth.py`
- `backend/tests/test_growth.py`
- `backend/tests/test_health_and_config.py`

## Mobile

- `mobile/.env.example`
- `mobile/app.json`
- `mobile/package.json`
- `mobile/app/_layout.tsx`
- `mobile/app/(tabs)/index.tsx`
- `mobile/app/(tabs)/profile.tsx`
- `mobile/app/growth.tsx`
- `mobile/app/watch-party/[code].tsx`
- `mobile/app/watch/[id].tsx`
- `mobile/src/features/auth/api.ts`
- `mobile/src/features/growth/AdCard.tsx`
- `mobile/src/features/growth/api.ts`

## Web and Admin

- `web/package.json`
- `web/app/rewards/page.tsx`
- `web/app/watch-party/[code]/page.tsx`
- `web/features/profile/ProfileExperience.tsx`
- `admin/package.json`
- `admin/app/(panel)/growth/page.tsx`
- `admin/components/admin-shell.tsx`

## Documentation and verification

- `docs/PHASE_11.md`
- `docs/PHASE_11_FILE_MANIFEST.md`
- `docs/PHASE_11_VALIDATION.md`
- `docs/WINDOWS_PHASE_11_UPGRADE.md`
- `scripts/verify-phase11.ps1`

The overlay excludes runtime secrets, `.env`, `mobile/.env`, Firebase credential
files, dependency directories, caches, local builds, database dumps, and Git
metadata.
