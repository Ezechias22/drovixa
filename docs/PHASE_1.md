# Drovixa Phase 1 — Foundation

## Scope delivered

Phase 1 establishes the production boundary; it does not fake content,
streaming, wallets, subscriptions, or frontend screens.

```text
Clients (mobile / web / admin)
             |
             v
       FastAPI /api/v1
        |           |
        v           v
   PostgreSQL     Redis
        |
        v
  Celery worker entrypoint
```

The backend is split into API dependencies, core infrastructure, models,
schemas, repositories, services, routes, workers, operational scripts,
migrations, and tests. Business transactions live in services; routes do not
write authentication state directly.

## Authentication design

- Passwords are hashed with Argon2 through `pwdlib`.
- Access tokens are JWTs with `sub`, `sid`, `jti`, `typ`, `iat`, `nbf`, `exp`,
  issuer, and audience validation. Default lifetime: 20 minutes.
- Refresh tokens are 64-byte opaque random secrets. Only an HMAC-SHA256 hash is
  stored in PostgreSQL. Default lifetime: 60 days.
- Every refresh rotates the token. Reusing an already rotated token revokes the
  complete token family and device session.
- Access checks load the active server-side session, user status, roles, and
  permissions, so a ban or session revoke applies immediately.
- Devices and sessions are separate records. Users can revoke one device or all
  sessions.

For Expo, store tokens in SecureStore. For the public web application, use a
same-origin Next.js BFF to store the refresh token in a Secure, HttpOnly,
SameSite cookie; never expose it to browser JavaScript.

## RBAC and runtime controls

The migration seeds all specified roles: `guest`, `user`, `premium_user`,
`moderator`, `content_manager`, `support_agent`, `finance_admin`, `admin`, and
`super_admin`. Administrative capabilities are permission codes such as
`content.publish`, `wallet.adjust`, and `settings.manage`; there is no
`is_admin` shortcut.

The migration also seeds the specified feature flags and public remote config.
Admin changes require permission and generate an audit record containing the
actor, old/new values, request IP, and user agent. Cache is invalidated after a
committed change. Registration is enforced server-side by
`registration_enabled`; future modules should reuse the same dependency.

## First run

```bash
cp .env.example .env
openssl rand -hex 32  # use for JWT_SECRET
openssl rand -hex 32  # use a different value for REFRESH_SECRET
docker compose up --build -d
docker compose exec backend python -m app.scripts.bootstrap_superuser
```

Do not run bootstrap automatically during API startup. Keeping it explicit
prevents multiple replicas from racing to create or mutate the owner account.

## Verification

```bash
curl http://localhost:8000/api/v1/health/live
curl http://localhost:8000/api/v1/health/ready
curl http://localhost:8000/api/v1/remote-config
curl http://localhost:8000/api/v1/feature-flags
```

Local quality gates:

```bash
make lint
make typecheck
make test
cd backend
alembic check
```

Expected automated suite: 22 tests, at least 80% branch-aware application
coverage, clean Ruff lint, clean strict mypy, and no Alembic model drift.

## Environment separation

Create distinct databases, Redis instances, secrets, and provider credentials
for development, staging, and production. Startup validation rejects weak or
shared signing secrets in staging/production and rejects debug mode there.

## Deferred by design

- Google and Apple auth require provider credentials and client bundle IDs.
- Email verification and password reset require a selected transactional email
  provider.
- Phase 2 adds content schemas/admin CRUD. Phase 3 adds the video-provider
  abstraction and signed playback. Monetization tables begin in Phase 5.
- Mobile, web, and admin source applications are initialized in their client
  phases; their repository boundaries are reserved now to avoid mixing them.

These items are documented rather than represented by mock production APIs.

