# Drovixa Phase 8 — Production readiness and release engineering

Phase 8 turns the complete product baseline into an operational release system.
It does not claim that production is already deployed or that store review has
already happened; those actions require the owner's domains, cloud accounts,
signing credentials, legal documents, and explicit release approval.

## Delivered

- API version `0.8.0`, release/build metadata, hardened proxy handling, request
  size limit, authenticated Prometheus-format metrics, Sentry integration, and
  database/Redis timeouts and pool controls.
- Performance indexes in Alembic revision `20260822_0009`.
- Fixed, idempotent super-admin bootstrap that can safely reset the configured
  account without async relationship lazy loading.
- Installable Web PWA with offline fallback and a cache policy that excludes API,
  Mux playback, HLS manifests, and video segments.
- Sentry hooks for Web, Admin, Expo mobile, and FastAPI.
- Expo runtime/version policy, EAS production profiles, native splash configuration,
  and mobile release workflow.
- Production Docker topology with automatic TLS, private application services,
  non-root/read-only containers, managed PostgreSQL/Redis expectation, backups,
  restore guardrails, smoke tests, and a k6 load-test baseline.
- Dependency, vulnerability, secret, client, backend, container-release, and
  manually approved deployment workflows.

## Required before a real public launch

Configure domains and DNS, managed databases, Sentry, Mux production webhooks,
payment/IAP production credentials, email delivery, privacy/terms URLs, Apple and
Google developer accounts, Expo project ownership, store screenshots/metadata,
support contacts, monitoring alerts, and a tested restore drill. Complete
`docs/RELEASE_CHECKLIST.md` before promoting a release.
