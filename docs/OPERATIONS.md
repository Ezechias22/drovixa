# Drovixa operations runbook

## Daily signals

- `/api/v1/health/live` confirms the process is alive.
- `/api/v1/health/ready` confirms PostgreSQL and Redis dependencies.
- `/api/v1/metrics` is private and requires `METRICS_TOKEN` when enabled.
- Sentry receives sanitized backend, Web, Admin, and mobile exceptions when DSNs
  are configured.

Alert on readiness failures, sustained 5xx responses, high p95 latency, payment or
Mux webhook failures, Celery queue growth, database saturation, backup failure,
and expiring domains/certificates. Do not expose the metrics endpoint through the
public reverse proxy.

## Deployment

Release immutable image tags, back up the database, deploy through the protected
GitHub `production` environment, wait for health checks, then run smoke tests.
Do not mutate an existing tag. Roll back by redeploying the last known-good image
tag; schema rollback is a separate reviewed operation.

## Capacity

Start with two API workers and two Celery workers, then tune from measured CPU,
memory, connection pool, queue, and latency data. Run `ops/load/k6-smoke.js` in a
staging environment before major releases, never against production without an
approved test window.
