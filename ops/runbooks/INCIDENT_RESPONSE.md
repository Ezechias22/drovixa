# Incident response runbook

1. Declare severity, incident owner, UTC start time, affected surfaces, and a
   private communication channel.
2. Preserve logs and audit evidence. Never paste tokens, user data, or private
   playback URLs into public tickets.
3. Contain: disable affected feature flags, revoke sessions/credentials,
   restrict endpoints, pause publishing/payments, or roll back as appropriate.
4. Diagnose with Render, Neon, Redis, Mux, Firebase, Sentry, and application
   request IDs. Distinguish provider outage from code/config regression.
5. Recover using the last known-good immutable release; run readiness, smoke,
   login, catalog, playback, and notification checks.
6. Notify users/regulators/providers when required. Record decisions and times.
7. Complete a blameless post-incident review with root cause, impact, detection,
   corrective actions, owners, and deadlines.
