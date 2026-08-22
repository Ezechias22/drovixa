# Drovixa security operations

## Secrets

Keep `.env`, EAS secrets, Mux credentials, signing keys, payment keys, database
URLs, and Sentry auth tokens outside Git. Use a production secret manager, grant
least privilege, separate staging from production, and rotate exposed values.
JWT and refresh secrets must be independent and at least 32 random characters.

## Network and data

Only HTTPS ports 80/443 are public in the production Compose topology. API,
Admin, Web, workers, PostgreSQL, and Redis stay private. Use TLS for managed
PostgreSQL and Redis, encrypt backups at rest in the storage provider, restrict
admin access, and retain audit logs according to policy.

## Release response

Run dependency/secret scans on every change, review Sentry alerts without sending
PII, test account/session revocation, and rehearse rollback. For a suspected
incident: freeze deployment, preserve logs, revoke affected keys/sessions, assess
scope, restore service, notify required parties, and document corrective actions.

The Phase 8 audit is clean at high/critical severity for Web and Admin. Expo 57's
Metro build-tool dependency tree still reports upstream high-severity
`image-size` denial-of-service advisories. They are not part of the deployed Web
or Admin servers, and forcing npm's proposed downgrade would break the Expo SDK
compatibility contract. Keep mobile builds on trusted assets, track Expo's patched
release, and block any critical mobile advisory in CI.
