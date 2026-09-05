# Drovixa Phase 9.1 — Render gratis san Blueprint

Dokiman sa a mete Drovixa sou entènèt pou premye tès ak premye itilizatè yo san
Blueprint peye. Li pa ranplase `render.yaml`; fichye sa a rete konfigirasyon
production pou lè pwojè a pare pou plan peye.

## Sa vèsyon gratis la genyen

- yon Web Service gratis pou API FastAPI a;
- yon Web Service gratis pou sit piblik Next.js la;
- yon Web Service gratis pou Admin Dashboard la;
- yon PostgreSQL gratis;
- yon Key Value gratis;
- Firebase push imedya an mòd `inline`, san Celery worker;
- yon scheduler limyè anndan API a pou kanpay pwograme yo.

Pa kreye `Background Worker`, `Cron Job`, oswa Blueprint pou vèsyon sa a.
Kanpay pwograme yo ka anreta lè Render mete API gratis la dòmi. Yo trete lè API
a reveye ankò. PostgreSQL gratis la ekspire apre 30 jou epi li pa gen backup;
planifye yon export oswa yon upgrade anvan dat ekspirasyon an.

## 1. Pouse hotfix la sou GitHub

Nan PowerShell, apre ou fin ekstrè ZIP Phase 9.1 la sou pwojè a:

```powershell
Set-Location "C:\Users\touss\DrovixaProject\drovixa"

git status --short
git add .
git commit -m "Drovixa Phase 9.1: Render free staging mode"
git push origin main
```

Pa ajoute `.env`, `mobile/.env`, `google-services.json`, oswa Firebase Admin JSON
nan Git.

## 2. Kreye PostgreSQL gratis la

Nan Render Dashboard:

1. `New` > `Postgres`.
2. Name: `drovixa-postgres-free`.
3. Region: chwazi menm region pou tout sèvis yo.
4. Database: `drovixa`.
5. User: `drovixa`.
6. Instance Type/Plan: `Free`.
7. Kreye database la epi konsève **Internal Database URL** la pou API a.

## 3. Kreye Key Value gratis la

1. `New` > `Key Value`.
2. Name: `drovixa-redis-free`.
3. Menm region ak PostgreSQL la.
4. Plan: `Free`.
5. Maxmemory policy: `noeviction` si opsyon an disponib.
6. Kreye li epi konsève **Internal URL** la.

## 4. Kreye API gratis la

Chwazi `New` > `Web Service`, konekte repo
`https://github.com/Ezechias22/drovixa`, epi itilize:

| Chan Render | Valè |
| --- | --- |
| Name | `drovixa-api-free` |
| Branch | `main` |
| Language/Runtime | `Docker` |
| Root Directory | kite vid |
| Dockerfile Path | `./backend/Dockerfile` |
| Docker Build Context | `.` |
| Instance Type | `Free` |
| Health Check Path | `/api/v1/health/ready` |

Docker Command:

```sh
python -m app.scripts.start_api
```

Kòmand sa a pa bezwen okenn guillemets oswa `sh -c`. Li aplike migrasyon yo,
verifye premye kont administratè a, senkronize katalòg demo a dapre
`DEMO_CATALOG_ENABLED`, epi li demare Uvicorn sou pò Render bay la.

Ajoute environment variables sa yo. Pran valè sekrè yo nan `.env` lokal la;
pa poste yo sou GitHub.

```dotenv
APP_ENV=staging
SERVICE_ROLE=api
DEBUG=false
RELEASE=drovixa@0.9.1-free
TRUST_PROXY_HEADERS=true
FORCE_HTTPS=true
TRUSTED_HOSTS=["*.onrender.com","localhost"]
BACKEND_CORS_ORIGINS=["https://TEMP-WEB.onrender.com","https://TEMP-ADMIN.onrender.com"]

DATABASE_URL=INTERNAL_DATABASE_URL_POSTGRES_LA
REDIS_URL=INTERNAL_KEY_VALUE_URL_LA
CELERY_BROKER_URL=INTERNAL_KEY_VALUE_URL_LA
CELERY_RESULT_BACKEND=INTERNAL_KEY_VALUE_URL_LA
DATABASE_POOL_SIZE=5
DATABASE_MAX_OVERFLOW=5
HEALTHCHECK_REDIS_REQUIRED=false
RATE_LIMIT_ENABLED=true

JWT_SECRET=SEKRE_FO_AK_OMWEN_32_KARAKTE
REFRESH_SECRET=YON_LOT_SEKRE_FO_AK_OMWEN_32_KARAKTE
METRICS_ENABLED=false

FIRST_SUPERUSER_EMAIL=EMAIL_ADMIN_OU
FIRST_SUPERUSER_PASSWORD=MODPAS_ADMIN_OU_AK_OMWEN_12_KARAKTE
FIRST_SUPERUSER_NAME=Drovixa Owner

VIDEO_PROVIDER=mux
MUX_TOKEN_ID=VALE_OU
MUX_TOKEN_SECRET=VALE_OU
MUX_SIGNING_KEY_ID=VALE_OU
MUX_SIGNING_PRIVATE_KEY_B64=VALE_OU
MUX_WEBHOOK_SECRET=SEKRE_TANPORE_POU_PREMYE_DEPLOY_LA
MUX_UPLOAD_CORS_ORIGIN=https://TEMP-ADMIN.onrender.com
VIDEO_ALLOWED_ORIGINS=["https://TEMP-WEB.onrender.com","https://TEMP-ADMIN.onrender.com"]

PUSH_PROVIDER=firebase
FIREBASE_PROJECT_ID=VALE_OU
FIREBASE_SERVICE_ACCOUNT_JSON_B64=VALE_OU
FIREBASE_DRY_RUN=false
PUSH_BATCH_SIZE=100
NOTIFICATION_DELIVERY_MODE=inline
SCHEDULED_NOTIFICATION_POLLING_ENABLED=true
SCHEDULED_NOTIFICATION_POLL_INTERVAL_SECONDS=60

PAYMENT_PROVIDER=disabled
```

`JWT_SECRET` ak `REFRESH_SECRET` dwe diferan. Pou premye deploy la, ou ka itilize
yon valè o aza kòm `MUX_WEBHOOK_SECRET`; apre API URL la egziste, ranplase li ak
vrè signing secret endpoint Mux la.

## 5. Kreye sit Web gratis la

Kreye yon lòt `Web Service` sou menm repo a:

| Chan Render | Valè |
| --- | --- |
| Name | `drovixa-web-free` |
| Branch | `main` |
| Runtime | `Docker` |
| Root Directory | kite vid |
| Dockerfile Path | `./web/Dockerfile` |
| Docker Build Context | `.` |
| Instance Type | `Free` |
| Health Check Path | `/` |

Environment variables:

```dotenv
INTERNAL_API_URL=https://URL-API-OU.onrender.com/api/v1
NEXT_PUBLIC_API_URL=/api/drovixa
NEXT_PUBLIC_APP_ENV=staging
RELEASE=drovixa-web@0.9.1-free
```

Malgre non `INTERNAL_API_URL` la, sèvi ak URL **piblik HTTPS** API a sou plan
gratis la.

## 6. Kreye Admin Dashboard gratis la

Kreye yon twazyèm `Web Service`:

| Chan Render | Valè |
| --- | --- |
| Name | `drovixa-admin-free` |
| Branch | `main` |
| Runtime | `Docker` |
| Root Directory | kite vid |
| Dockerfile Path | `./admin/Dockerfile` |
| Docker Build Context | `.` |
| Instance Type | `Free` |
| Health Check Path | `/login` |

Environment variables:

```dotenv
INTERNAL_API_URL=https://URL-API-OU.onrender.com/api/v1
ADMIN_COOKIE_SECURE=true
NEXT_PUBLIC_APP_ENV=staging
RELEASE=drovixa-admin@0.9.1-free
```

## 7. Mete vrè URL yo nan API a

Lè Web ak Admin fin resevwa URL pa yo, tounen nan Environment API a epi
ranplase valè tanporè yo:

```dotenv
BACKEND_CORS_ORIGINS=["https://VRÈ-WEB-OU.onrender.com","https://VRÈ-ADMIN-OU.onrender.com"]
VIDEO_ALLOWED_ORIGINS=["https://VRÈ-WEB-OU.onrender.com","https://VRÈ-ADMIN-OU.onrender.com"]
MUX_UPLOAD_CORS_ORIGIN=https://VRÈ-ADMIN-OU.onrender.com
```

Sove chanjman yo epi kite API a redeploy.

## 8. Konekte Mux webhook la

Nan Mux Dashboard, kreye endpoint sa a:

```text
https://URL-API-OU.onrender.com/api/v1/webhooks/videos/mux
```

Kopye signing secret Mux bay pou endpoint sa a, mete li kòm
`MUX_WEBHOOK_SECRET` nan API Render la, epi redeploy API a.

## 9. Konekte aplikasyon mobil lan

Nan `mobile/.env` lokal la:

```dotenv
EXPO_PUBLIC_API_URL=https://URL-API-OU.onrender.com/api/v1
EXPO_PUBLIC_APP_ENV=staging
EXPO_PUBLIC_RELEASE=drovixa-mobile@0.9.1-free
EXPO_PUBLIC_PUSH_ENABLED=true
```

Pou Firebase push reyèl, itilize yon EAS development oswa production build;
Expo Go pa sifi pou remote notification sou Android aktyèl la.

## 10. Verifikasyon

```powershell
Set-Location "C:\Users\touss\DrovixaProject\drovixa"

.\scripts\verify-render-free.ps1 `
    -ApiUrl "https://URL-API-OU.onrender.com" `
    -WebUrl "https://URL-WEB-OU.onrender.com" `
    -AdminUrl "https://URL-ADMIN-OU.onrender.com"
```

Premye demann lan ka pran plis tan si sèvis gratis la te dòmi. Apre tès la,
antre nan Admin, kreye yon kanpay pou yon ti odyans, epi teste `in_app + push`
anvan ou voye bay tout itilizatè yo.

Dokiman ofisyèl:

- Render Free: https://render.com/docs/free
- Render Docker: https://render.com/docs/docker
- Mux webhooks: https://www.mux.com/docs/core/listen-for-webhooks
