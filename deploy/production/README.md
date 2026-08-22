# Drovixa production deployment

This deployment publishes only Caddy on ports 80/443. The API, Admin, Web,
worker, and scheduler remain on the private Docker network. PostgreSQL and Redis
must be managed services with TLS, automated provider snapshots, and restricted
network access.

1. Copy `.env.production.example` to `.env.production` on the server.
2. Replace every placeholder and pin immutable image tags.
3. Point the three DNS names to the server.
4. Validate: `docker compose --env-file .env.production config --quiet`.
5. Pull and start: `docker compose --env-file .env.production pull` followed by
   `docker compose --env-file .env.production up -d --wait`.
6. Run `ops/smoke/smoke-test.sh https://api.example.com https://app.example.com https://admin.example.com`.

Never put the production environment file in Git. Rotate credentials immediately
if a secret is exposed. See `docs/OPERATIONS.md` and `docs/DISASTER_RECOVERY.md`.

For Render, use the root `render.yaml` Blueprint instead of this self-managed
Compose stack. Complete every `sync: false` value before the first deploy so the
one-time super-administrator bootstrap hook can run. See
`docs/RENDER_FIREBASE_SETUP.md`.
