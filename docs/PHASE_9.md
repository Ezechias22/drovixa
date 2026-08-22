# Phase 9 — Firebase notifications and Render deployment

Phase 9 turns the existing in-app notification system into a native push
delivery pipeline and makes the monorepo deployable as one Render Blueprint.
Mux remains the only active video provider.

## Delivered

- Firebase Admin SDK integration behind a provider-neutral push contract.
- Authenticated native FCM token registration, listing, rotation, and
  deactivation without returning raw tokens to clients.
- Per-device and per-campaign delivery records with failure codes and timestamps.
- Batched Firebase multicast delivery capped at 500 tokens per request.
- Automatic invalid-token deactivation and retry-safe campaign state handling.
- Immediate and scheduled campaign delivery through Celery.
- In-app notifications remain functional if Firebase is disabled.
- Admin provider status, campaign composer, live campaign state, and delivery
  summary API.
- Expo Android permission/channel setup, foreground handling, safe deep links,
  registration after login, and deactivation during logout.
- Render Blueprint for API, public Web, Admin, worker/beat, PostgreSQL, and
  persistent Key Value.
- Render-compatible PostgreSQL URL normalization and one-time super-admin
  bootstrap.

## New API routes

- `GET /api/v1/push/config`
- `POST /api/v1/push-tokens`
- `GET /api/v1/push-tokens`
- `DELETE /api/v1/push-tokens/current`
- `DELETE /api/v1/push-tokens/{push_token_id}`
- `GET /api/v1/admin/notifications/provider-status`
- `GET /api/v1/admin/notification-campaigns/{campaign_id}/deliveries`

## Data migration

Alembic revision `20260823_0010` adds `push_tokens` and
`notification_deliveries`. Raw FCM tokens are required for provider delivery but
are never returned by API responses or written to logs. A SHA-256 fingerprint is
used for uniqueness and public responses expose only a short suffix.

## Security boundaries

- `FIREBASE_SERVICE_ACCOUNT_JSON_B64` belongs only in backend/worker secrets.
- `google-services.json` belongs only in the native build environment and is
  excluded from Git.
- The mobile app receives no Firebase Admin private key.
- Campaign management continues to require `notifications.manage`.
- Notification action URLs are accepted by the mobile client only when they
  match Drovixa internal routes.
- Production configuration rejects malformed Firebase base64 JSON or a project
  ID that does not match the service account.

## Validation

Run:

```powershell
Set-Location C:\Users\touss\DrovixaProject\drovixa
.\scripts\verify-phase9.ps1
```

Remote push must be tested on a physical Android device using an EAS development
or production build. Expo Go is suitable for general UI/API testing but not for
Phase 9 remote push delivery.

## Roadmap after Phase 9

The planned complete product has 12 phases. Three remain:

1. Phase 10: profiles, Kids mode, ratings, secure downloads, casting, and final
   playback/device experience.
2. Phase 11: ads, daily rewards, referrals, social login, Watch Party, and growth
   automation.
3. Phase 12: full QA/security/performance pass, production monitoring and
   backups, signed EAS builds, store assets/legal pages, and Play Store/App Store
   submission readiness.

Store review and account verification are external approvals and cannot be
guaranteed by application code.
