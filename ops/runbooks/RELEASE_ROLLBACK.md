# Release and rollback runbook

Before release, record the current Render deploy IDs, image/source commit,
database head, configuration changes, backup path, and responsible operator.

Release Web/Admin/API first, run public smoke tests, then distribute the mobile
preview. For store release, use staged rollout and monitor crash-free sessions,
API errors, latency, playback authorization/CDN failures, sign-in, purchases,
push delivery, and support volume.

Rollback application services to the previous known-good commit or immutable
image when the release is incompatible. Prefer forward database fixes because
Phase migrations are additive; never downgrade a production database without a
reviewed, tested recovery procedure. After rollback, run readiness and critical
journey tests and document the decision.
