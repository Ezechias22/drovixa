# Drovixa Phase 12 — Production launch readiness

Phase 12 closes the planned implementation roadmap. It does not invent another
feature module or change user data. It turns the Phase 11 application into a
controlled release candidate with repeatable launch, monitoring, backup,
rollback, legal, and store-submission gates.

## Delivered

- Version `0.12.0` across API, Mobile, Web, Admin, and the workspace lockfile.
- Android preview APK and production AAB separation in EAS.
- Production mobile configuration rejects HTTP and local API URLs.
- Explicit Expo Updates project URL and production update channel.
- A local Windows release verifier for Compose, clients, secret exclusions,
  public endpoints, and release-version consistency.
- A production smoke test with retries for Render cold starts, API readiness,
  Web/Admin availability, security headers, and deployed version.
- A guarded Neon/PostgreSQL backup command that creates and validates a custom
  dump plus SHA-256 checksum without printing the database URL.
- GitHub release-gate, production-smoke, and confirmed mobile-submission gates.
- Incident, rollback, backup/restore, legal, privacy, community, account
  deletion, and store-listing templates.

## Data safety

There is no Phase 12 Alembic migration. The expected database head remains
`20260825_0012`. Phase 12 never runs `docker compose down -v`, never replaces a
local `.env`, and never commits Firebase, Neon, Mux, JWT, or store credentials.

## What still depends on external approval

Implementation can finish locally, but the following cannot be approved by
source code:

- Google Play and Apple App Store developer-account verification.
- Final legal review and publication of the Privacy Policy and Terms URLs.
- OAuth consent-screen verification for Google/Apple sign-in.
- Payment/IAP merchant approval and product creation.
- Store review and production rollout approval.

Until those approvals exist, use the EAS `preview` profile for installable APK
testing and keep real payment/IAP switches disabled.

## Release order

1. Back up Neon and validate the dump.
2. Run `scripts/verify-phase12.ps1` locally.
3. Commit and push the Phase 12 overlay.
4. Wait for API, Web, and Admin to report Live on Render.
5. Run the production smoke test against the public URLs.
6. Build an EAS preview APK and complete device acceptance tests.
7. Publish reviewed legal URLs and finish store console configuration.
8. Run the guarded GitHub Mobile Release workflow only after approval.
