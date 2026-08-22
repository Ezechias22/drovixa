# Drovixa disaster recovery

Target an initial RPO of six hours and RTO of four hours, then tighten those
targets after measuring the real restore process. Use managed PostgreSQL point-in-
time recovery in addition to the provided logical backup job. Store copies in a
separate account/region with retention and object-lock controls where available.

Every quarter, restore the latest backup into an isolated database, verify its
SHA-256 checksum, apply migrations, and test health, admin login, catalog, Mux
playback authorization, entitlements, comments, and audit logs. Never test a
destructive restore against production. Record elapsed time and any gaps.

The restore script requires `CONFIRM_RESTORE=DROVIXA`, a deliberate target URL,
and an explicit backup path. After a recovery, rotate credentials if compromise
was possible and reconcile webhooks/payments received during the outage.
