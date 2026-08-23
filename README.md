# Drovixa

Drovixa is a production-oriented monorepo for a cinematic short-drama, series,
shorts, and movie streaming platform. This delivery contains the completed
**Phase 1 foundation**, **Phase 2 content/catalog**, **Phase 3 secure
streaming**, **Phase 4 user experience**, **Phase 5 monetization**, and
**Phase 6 community and moderation**, **Phase 7 administration**, **Phase 8
production readiness and release engineering**, **Phase 9 Firebase push
notifications and Render deployment**, **Phase 10 profiles, Kids mode, ratings,
secure downloads, casting, and device playback**, and **Phase 11 server-issued
ads, daily coin streaks, referral rewards, verified Google/Apple identity
exchange, Watch Party rooms, and growth automations**.

## Repository map

```text
drovixa/
├── mobile/       # Expo Router app with the native secure-HLS player foundation
├── web/          # Next.js app with the browser secure-HLS player foundation
├── admin/        # Independent Next.js administration dashboard
├── backend/      # FastAPI API, worker, migrations, and tests
├── docker-compose.yml
├── .env.example
└── Makefile
```

The foundation provides asynchronous FastAPI + SQLAlchemy 2, PostgreSQL migrations,
Redis-backed rate limiting/cache primitives, Celery wiring, email/password auth,
short-lived JWT access tokens, opaque rotating refresh tokens, session/device
revocation, granular RBAC, public feature flags/remote config, protected admin
configuration APIs, structured errors, request IDs, security headers, health
checks, Docker, CI, and automated tests.

Phase 2 adds countries, languages, genres, tags, actors, crew, shared content,
series, seasons, episodes, movies, video-asset metadata, subtitle tracks,
rights windows, public catalog APIs, granular admin CRUD/publishing, pagination,
soft deletion, and audit records for every administrative mutation.

Phase 3 adds the provider-neutral `VideoProvider` contract. The Drovixa
installation uses Mux Video as its active provider. It includes direct resumable upload
sessions, URL ingest,
signature-verified idempotent webhooks, signed HLS/DASH authorization,
content-rights/geo/access/device checks, playback sessions, progress, valid-view
counting, continue watching, history, and native/browser player foundations.

Phase 4 adds API-driven Home, Discover, Search, suggestions, trending searches,
vertical Shorts, series/movie details, favorites/My List, notifications and
preferences. The Next.js public experience is responsive and PWA-ready. The
Expo Router app includes the exact five-tab mobile navigation, SecureStore auth,
guest gates, premium cinematic screens, and secure Mux playback handoff. UI
content comes from the shared FastAPI API.

Phase 5 adds server-authoritative wallets, an immutable-style coin ledger,
audited admin adjustments, coin packages, transactional episode unlocks,
permanent entitlements, subscription plans and memberships, payment records,
idempotent signed webhooks, a provider-neutral `PaymentProvider`, Stripe-ready
web checkout, and server-only Apple/Google receipt-verification boundaries. The
responsive Web/PWA and Expo clients include real API-driven wallet and Premium
screens. No frontend event, fake balance, or unverified receipt can grant value.

Phase 6 adds generic likes for content, episodes, and Shorts; paginated comments
and one-level replies; spoiler controls; comment likes; user reports with
database-configurable reasons; moderator hide/delete/restore/spam/pin actions;
temporary user mutes and bans; notifications; granular RBAC; and audit logging.
Comments disappear from both clients and close at the API when
`comments_enabled` is disabled. Mobile and web expose the same community API.

Phase 7 finalizes the independent administration product: secure HttpOnly-cookie
sessions, a responsive cinematic control center, dashboard metrics, user and
role management, content operations, dynamic homepage construction, notification
campaigns with scheduled delivery, analytics, payment/subscription/coin views,
moderation queues, settings, feature flags, and paginated audit logs. Public Home
sections now come from the database and can be reordered or targeted without an
application release.

Phase 8 adds operational hardening: build/release metadata, authenticated metrics,
Sentry integration, proxy and payload protections, performance indexes, an
installable offline-aware PWA, Expo/EAS production configuration, production
containers with automatic TLS, backup/restore guardrails, smoke/load tests,
security scans, immutable image releases, and an approval-gated deployment path.

Phase 9 adds native Firebase Cloud Messaging token registration, token rotation
and deactivation, segmented in-app plus push campaigns, scheduled Celery delivery,
per-device delivery records, failure handling, and an audited provider-status
dashboard. Android builds use the native FCM token from `expo-notifications`;
Firebase Admin credentials remain server-only. A root `render.yaml` provisions
the API, Web, Admin, worker, PostgreSQL, and persistent Key Value services.

Phase 10 adds up to five viewer profiles per account, PIN-protected and
age-filtered Kids profiles, profile-aware discovery/playback, five-star ratings,
Premium application-private offline downloads with expiring server licenses,
Chromecast and AirPlay controls, playback speed, device/session management, and
an Admin experience dashboard. Mobile downloads use Mux signed static
renditions; provider credentials never enter the client.

Phase 11 adds frequency-capped house/partner ads with signed delivery sessions,
idempotent rewarded-ad coins, a seven-day daily reward calendar, two-sided
referral rewards backed by the wallet ledger, verified Google and Apple token
exchange, synchronized Watch Party state and chat, and event-driven growth
notifications. The Admin dashboard exposes acquisition and engagement signals.

The registration route enforces `registration_enabled` on the server. Later
modules must use the same dependency pattern so disabling a module removes its
client UI and also closes its API entrypoints.

## Quick start with Docker

```bash
cp .env.example .env
# Replace JWT_SECRET, REFRESH_SECRET and FIRST_SUPERUSER_PASSWORD.
docker compose up --build -d --wait
docker compose exec backend python -m app.scripts.bootstrap_superuser
curl http://localhost:8000/api/v1/health/ready
```

Open the independent Admin Dashboard at `http://localhost:3001` and sign in with
the super-administrator account stored in `.env`.

Install and verify the Phase 11 clients:

```bash
npm install
npm run typecheck:clients
npm run build --workspace @drovixa/web
npm run build --workspace @drovixa/admin
```

API documentation is available at `http://localhost:8000/docs` outside the
production environment.

## Local backend development

Python 3.12+ is required.

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r backend/requirements-dev.txt
cp .env.example .env
cd backend
alembic upgrade head
uvicorn app.main:app --reload
```

Run quality checks:

```bash
make test
make lint
make typecheck
```

## Implemented API surface

- `GET /api/v1/health/live`, `GET /api/v1/health/ready`
- `POST /api/v1/auth/register`, `/login`, `/refresh`, `/logout`, `/logout-all`
- `GET /api/v1/users/me`, `PATCH /api/v1/users/me`
- `GET /api/v1/users/me/devices`, `DELETE /api/v1/users/me/devices/{id}`
- `GET /api/v1/feature-flags`, `GET /api/v1/remote-config`
- `GET /api/v1/countries`, `/languages`, `/genres`, `/tags`
- `GET /api/v1/content/{slug}`, `/series`, `/series/{slug}`,
  `/series/{id}/episodes`, `/movies`, `/movies/{slug}`, `/actors/{slug}`
- Protected, paginated catalog/content CRUD and publish endpoints under
  `/api/v1/admin`
- `POST /api/v1/admin/video-assets/upload-sessions`, `/video-assets/ingest`
- `POST /api/v1/webhooks/videos/mux` (active default)
- `POST /api/v1/playback/episodes/{id}/authorize`,
  `/playback/movies/{id}/authorize`, `/progress`
- `GET /api/v1/continue-watching`, `/history` plus remove/restart/clear routes
- `GET /api/v1/home`, `/discover`, `/shorts`, `/search`,
  `/search/suggestions`, `/search/trending`
- Authenticated `/favorites`, `/search/history`, `/notifications`, and
  `/notification-preferences`
- Native `/push/config` and authenticated `/push-tokens` registration and
  deactivation routes
- `GET /api/v1/wallet`, `/wallet/transactions`, `/coins/packages`
- `POST /api/v1/coins/purchase`, `/episodes/{id}/unlock`, `/iap/verify`
- `GET /api/v1/subscriptions/plans`, `/subscriptions/current`
- `POST /api/v1/subscriptions/checkout`, `/subscriptions/cancel`
- Signed, idempotent `POST /api/v1/webhooks/payments/{provider}`
- Audited package, plan, wallet, payment and subscription administration under
  `/api/v1/admin`
- Generic `/api/v1/likes`, `/comments`, `/comments/{id}/replies`, comment likes,
  `/report-reasons`, and `/reports`
- Moderation queues and actions under `/api/v1/admin/comments`,
  `/api/v1/admin/reports`, and `/api/v1/admin/users/{id}/mute|ban|restore`
- `GET /api/v1/admin/dashboard`, `/analytics/overview`, `/analytics/content`
- Paginated user/role administration under `/api/v1/admin/users` and `/roles`
- Dynamic `/api/v1/admin/homepage/sections` ordering and manual content assignment
- Draft, scheduled, queued, partially delivered, sent and cancelled
  `/api/v1/admin/notification-campaigns`, including provider status and delivery summaries
- Filterable, paginated `GET /api/v1/admin/audit-logs`
- Authenticated `/api/v1/profiles`, `/ratings/{content_id}`, `/downloads`, and
  `/cast-sessions`, plus `/api/v1/admin/experience/summary`
- `/api/v1/ads`, `/rewards/daily`, `/referrals`, `/auth/social`,
  `/watch-parties`, and `/api/v1/admin/growth`

Authentication responses return an access token and a refresh token. Clients
must store the mobile refresh token in SecureStore; the web BFF should put it in
a Secure, HttpOnly, SameSite cookie. The API never stores the raw refresh token.

## Security and operations notes

- Run migrations as a release step before scaling API replicas.
- Never use the example secrets or database password in staging/production.
- Put the API behind TLS and a trusted reverse proxy/load balancer.
- `/health/live` is process liveness; `/health/ready` verifies PostgreSQL and,
  when configured, Redis.
- `/api/v1/metrics` uses Prometheus text format, is token-protected in production, and
  is blocked from the public production reverse proxy.
- Every upload created by the Mux adapter uses a `signed` playback policy. The API
  returns only short-lived signed manifests after server-side authorization;
  clients never receive the provider API token or signing key.
- Mux credentials are optional for catalog/auth development, but real
  upload and playback routes return a structured configuration error until the
  provider and signing variables are present.
- `PAYMENT_PROVIDER=disabled` is the safe local default. Coin ledger and unlock
  flows work without a payment provider; real web purchases require Stripe
  server credentials and a signed webhook. Mobile purchases remain closed until
  Apple/Google server verification is provisioned.
- Google/Apple auth activates only when matching OAuth client IDs are configured;
  server-side identity-token validation remains mandatory.
- Remote push notifications require an EAS development/production build on
  Android; current Expo Go clients cannot exercise native remote push delivery.

See `docs/PHASE_11.md`, `docs/RENDER_FIREBASE_SETUP.md`, `docs/OPERATIONS.md`, and
`docs/RELEASE_CHECKLIST.md` for production responsibilities and release gates.
Mux provisioning and webhook details remain in `docs/PHASE_3_1_MUX.md`.
