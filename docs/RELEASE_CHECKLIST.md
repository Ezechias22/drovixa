# Drovixa release checklist

## Engineering

- [ ] Backend lint, strict typecheck, tests, coverage, and Alembic checks pass.
- [ ] Mobile/Web/Admin typechecks and production Web/Admin builds pass.
- [ ] Dependency, secret, and container scans have no unaccepted high/critical issue.
- [ ] Staging smoke and k6 thresholds pass using the candidate image tag.
- [ ] Database backup and isolated restore drill are current.
- [ ] Rollback image tag and owner are recorded.

## Platform

- [ ] Production DNS, HTTPS, CORS, trusted hosts, proxy trust, Sentry, alerts, and backups are verified.
- [ ] Mux signing keys/webhooks and playback on representative devices are verified.
- [ ] Stripe and/or Apple/Google receipt verification is enabled only with real server-side credentials.
- [ ] Super-admin password is stored in a password manager and old sessions are revoked.

## Store and policy

- [ ] Privacy policy, terms, content policy, account deletion, support contact, and age rating are approved.
- [ ] Apple/Google identifiers, signing, screenshots, descriptions, review notes, and test accounts are ready.
- [ ] Analytics consent/data declarations match actual SDK and server behavior.
- [ ] Release approval is recorded before production deployment or store submission.
