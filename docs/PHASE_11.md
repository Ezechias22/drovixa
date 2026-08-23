# Phase 11 — Growth, rewards, social identity, and Watch Party

Phase 11 adds Drovixa's first controlled growth system without weakening the
server-authoritative wallet, authentication, or playback boundaries built in
earlier phases.

## Delivered

- Frequency-capped ad placements selected and issued by the API.
- Expiring, unguessable ad-delivery sessions and idempotent event tracking.
- Rewarded-ad coins written once through the existing immutable-style wallet
  ledger; a repeated completion event cannot mint coins twice.
- A seven-day daily streak with server dates, idempotent claims, and coin values
  of 5, 5, 10, 10, 15, 20, and 50.
- One referral code per account, one referral per invitee, self-invite blocking,
  and two-sided ledger rewards (50 inviter / 25 invitee coins).
- Verified Google and Apple identity-token exchange. Provider configuration is
  fail-closed and no OAuth secret is shipped to a client.
- Watch Party creation, invite codes, membership, host-only playback state,
  polling synchronization, sharing, and party chat.
- Event-driven growth notifications with configurable cooldowns.
- Responsive mobile Rewards/Referral and Watch Party screens, a home ad card,
  matching Web routes, and an Admin Growth dashboard.

## New API surface

- `GET /api/v1/growth/config`
- `GET /api/v1/ads/next`, `POST /api/v1/ads/events`
- `GET /api/v1/rewards/daily`, `POST /api/v1/rewards/daily/claim`
- `GET /api/v1/referrals/me`, `POST /api/v1/referrals/apply`
- `POST /api/v1/auth/social`
- `POST /api/v1/watch-parties`
- `POST /api/v1/watch-parties/{code}/join`
- `GET /api/v1/watch-parties/{code}`
- `PATCH /api/v1/watch-parties/{code}/state`
- `POST /api/v1/watch-parties/{code}/messages`
- `GET /api/v1/admin/growth/summary`
- `GET|POST /api/v1/admin/growth/ads`
- `GET /api/v1/admin/growth/automations`
- `PATCH /api/v1/admin/growth/automations/{id}`

## Migration

Alembic revision `20260825_0012` creates the Phase 11 growth tables, a Drovixa
Premium house ad, two safe notification automations, and activates the existing
Phase 11 feature flags. It is additive and preserves all Phase 10 data.

## OAuth activation

Social identity exchange remains hidden and fail-closed until Render contains
the matching public client IDs:

```text
GOOGLE_OAUTH_CLIENT_IDS=<comma-separated IDs or JSON array>
APPLE_OAUTH_CLIENT_IDS=<comma-separated IDs or JSON array>
```

Google tokens are checked with Google's token-info service and audience; Apple
tokens are verified against Apple's signed JWKS, issuer, and audience. Do not
put Google client secrets or Apple private keys in the mobile application.

## Watch Party scope

Phase 11 synchronizes state through authenticated HTTPS polling every three
seconds. It is intentionally compatible with the current free Render plan and
does not require an additional always-on websocket service. Phase 12 may replace
polling with real-time transport after load measurements justify it.

## Remaining roadmap

One planned implementation phase remains:

1. Phase 12: final QA, security/performance hardening, production monitoring and
   backup drills, signed store builds, legal/store assets, and submission gates.

Store review, OAuth-provider verification, and external account approval remain
third-party processes.
