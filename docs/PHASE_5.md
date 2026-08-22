# Drovixa Phase 5 — Monetization

Phase 5 adds production-oriented financial foundations without trusting the
frontend. Mux remains the active video provider; Phase 5 does not require any
Cloudflare configuration.

## Delivered modules

- Wallets with purchased and bonus balances
- Append-only business ledger records for every balance change
- Audited, idempotent admin adjustments
- Web/iOS/Android coin packages
- Transactional episode unlock and permanent entitlement creation
- Subscription plans with remotely configurable benefits
- Active/cancel-at-period-end subscription state
- Provider-neutral payment contract and Stripe web-checkout adapter
- Signature-verified, idempotent payment webhooks
- Payment, payment-event and refund records
- Apple/Google receipt-verifier boundary that grants nothing until a real
  server verifier is configured
- Responsive Coins and Premium screens for Web/PWA, Android, iOS and tablets
- Drovixa logo variants for PWA, browser icon, iOS, Android adaptive icon and
  Expo splash

## Database migration

The Phase 5 migration is:

```text
20260816_0006 (head)
```

It creates `wallets`, `wallet_ledger`, `coin_packages`, `episode_unlocks`,
`subscription_plans`, `subscriptions`, `payments`, `payment_events`, and
`refunds`. Existing users receive a zero-balance wallet during migration.

## Safe Windows upgrade

Run this from PowerShell. Keep the existing `.env`; do not copy `.env.example`
over it because it contains placeholders only.

```powershell
$ProjectRoot = "C:\Users\touss\DrovixaProject"
$ProjectDir = Join-Path $ProjectRoot "drovixa"
$DockerBin = "C:\Program Files\Docker\Docker\resources\bin"
$DockerExe = Join-Path $DockerBin "docker.exe"
$ZipFile = "$env:USERPROFILE\Downloads\drovixa-phase5-monetization.zip"

$MachinePath = [Environment]::GetEnvironmentVariable("Path", "Machine")
$UserPath = [Environment]::GetEnvironmentVariable("Path", "User")
$env:Path = "$DockerBin;$MachinePath;$UserPath"

if (-not (Test-Path $ZipFile)) { throw "ZIP Phase 5 la pa jwenn nan Downloads." }

Set-Location $ProjectDir
& $DockerExe compose exec -T postgres `
  pg_dump -U drovixa -d drovixa `
  --format=custom `
  --file=/tmp/drovixa-before-phase5.dump
if ($LASTEXITCODE -ne 0) { throw "Backup PostgreSQL la echwe." }

& $DockerExe compose cp `
  "postgres:/tmp/drovixa-before-phase5.dump" `
  "..\drovixa-before-phase5.dump"
if (-not (Test-Path "..\drovixa-before-phase5.dump")) {
  throw "Fichye backup la pa jwenn."
}

& $DockerExe compose down
Set-Location $ProjectRoot
Expand-Archive $ZipFile -DestinationPath . -Force
Set-Location $ProjectDir

& $DockerExe compose up --build -d --wait
if ($LASTEXITCODE -ne 0) {
  & $DockerExe compose logs backend --tail 200
  throw "Phase 5 pa rive demare."
}

& $DockerExe compose ps
& $DockerExe compose exec backend alembic current
Invoke-RestMethod "http://localhost:8000/api/v1/health/ready" |
  ConvertTo-Json -Depth 5
```

Expected Alembic output: `20260816_0006 (head)`.

## Payment environment variables

The existing project starts safely without new payment variables because the
backend defaults to `PAYMENT_PROVIDER=disabled`. Add these only when activating
real Stripe checkout:

```dotenv
PAYMENT_PROVIDER=stripe
PAYMENT_SUCCESS_URL=http://localhost:3000/payment/success
PAYMENT_CANCEL_URL=http://localhost:3000/payment/cancelled
STRIPE_SECRET_KEY=
STRIPE_WEBHOOK_SECRET=
STRIPE_API_BASE_URL=https://api.stripe.com/v1
```

Configure the Stripe webhook endpoint as:

```text
POST https://api.your-domain.com/api/v1/webhooks/payments/stripe
```

At minimum subscribe to checkout completion/failure, invoices and subscription
updates. Never expose either Stripe secret in Web or Expo environment files.

Mobile receipt variables stay disabled until the real App Store and Play Store
applications and server credentials exist:

```dotenv
IAP_VERIFICATION_ENABLED=false
APPLE_IAP_SHARED_SECRET=
GOOGLE_PLAY_PACKAGE_NAME=
GOOGLE_PLAY_SERVICE_ACCOUNT_JSON_B64=
```

## Enable modules and create products

Use Swagger at `http://localhost:8000/docs`, authenticate as a super admin, and:

1. Set `coins_enabled` and/or `subscriptions_enabled` to `true` with
   `PATCH /api/v1/admin/feature-flags/{key}`.
2. Create coin packages with `POST /api/v1/admin/coin-packages`.
3. Create Premium plans with `POST /api/v1/admin/subscription-plans`.
4. Create separate package records for `web`, `android`, and `ios`. Native
   packages must contain the exact store product ID.

When a feature flag is off, the clients remove its navigation entry and the API
rejects module operations.

## Run the clients

```powershell
Set-Location C:\Users\touss\DrovixaProject\drovixa
npm install

# Web/PWA
npm run dev --workspace @drovixa/web
```

For a physical phone, set `mobile/.env` to the computer's LAN address:

```dotenv
EXPO_PUBLIC_API_URL=http://YOUR-PC-IP:8000/api/v1
```

Then:

```powershell
npm run start --workspace @drovixa/mobile
```

The phone and PC must be on the same network and Windows Firewall must allow the
backend and Expo development ports.

## Verification

```powershell
Set-Location C:\Users\touss\DrovixaProject\drovixa
py -3.12 -m venv .venv
& .\.venv\Scripts\python.exe -m pip install -r backend\requirements-dev.txt

Set-Location .\backend
& ..\.venv\Scripts\python.exe -m pytest -q
& ..\.venv\Scripts\ruff.exe check app tests migrations
& ..\.venv\Scripts\mypy.exe app

Set-Location ..
npm run typecheck:clients
npm run build --workspace @drovixa/web
```

Acceptance checks:

- No financial POST works without authentication and an idempotency key.
- Insufficient coins create no ledger entry, unlock, or entitlement.
- Repeating an unlock idempotency key does not debit twice.
- Repeating a payment webhook does not grant coins twice.
- Bonus coins are consumed before purchased coins.
- Active subscriptions authorize Premium playback.
- Mobile receipts cannot grant value while server verification is unconfigured.
- Every admin wallet adjustment creates both a ledger record and an audit log.
- Web and Expo type checks pass, and the responsive logo assets render.
