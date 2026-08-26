# Neon backup and restore drill

Run `ops/backup/neon-backup.ps1` with the direct Neon connection URL supplied
through `DATABASE_BACKUP_URL`. Store the dump and checksum in an encrypted,
access-controlled location separate from the primary database.

At least monthly:

1. Create a disposable Neon branch or separate non-production database.
2. Verify the dump checksum and list it with `pg_restore --list`.
3. Restore with `--no-owner --no-privileges` to the disposable target.
4. Confirm Alembic head `20260825_0012`, user/catalog counts, login, signed
   playback authorization, wallet ledger consistency, and notification data.
5. Record backup time, restore time, operator, result, RPO/RTO, and cleanup.
6. Delete the disposable target only after evidence is recorded.

Never test a destructive restore against production.
