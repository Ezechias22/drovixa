# Windows upgrade notes — Phase 12

Phase 12 is an additive source overlay with no database migration. Preserve:

- `.env`
- `mobile/.env`
- `mobile/google-services.json`
- Neon, Render, Mux, Firebase, EAS, and signing credentials

After extracting the ZIP over `C:\Users\touss\DrovixaProject`, run `npm install`,
rebuild the local services, then execute `scripts\verify-phase12.ps1`.

Do not use `docker compose down -v`. The database migration head must remain
`20260825_0012`.
