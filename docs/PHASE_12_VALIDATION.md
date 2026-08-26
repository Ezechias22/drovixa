# Phase 12 validation contract

A release candidate is acceptable only when all applicable gates pass:

- Backend Ruff, mypy, pytest, Alembic upgrade, and Alembic check.
- Mobile, Web, and Admin TypeScript checks.
- Optimized Web and Admin builds.
- Expo public configuration generation with an HTTPS production API URL.
- Docker builds for Backend, Web, and Admin.
- Secret scan with no tracked `.env`, Firebase service account, signing key, or
  store credential.
- API `/health/live` and `/health/ready` return HTTP 200.
- The API reports version `0.12.0` after production deployment.
- Web and Admin return HTTP 200 and expected browser security headers.
- A recent PostgreSQL custom dump passes checksum and `pg_restore --list`.
- Login, registration, catalog, signed playback, Mux upload, push notification,
  profile, reward, referral, and Watch Party acceptance tests pass on devices.
- The installable Android preview APK passes cold start, background/resume,
  offline, notification, and upgrade tests on at least two Android versions.

Passing automation is necessary but not sufficient for store publication.
Legal text, screenshots, age rating, data-safety declarations, support contact,
account deletion, and third-party console approvals must also be reviewed.
