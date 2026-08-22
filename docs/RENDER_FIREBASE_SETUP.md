# Render + Firebase setup

Render hosts Drovixa. Firebase Cloud Messaging delivers native push
notifications. Mux remains the video provider.

## 1. Create the Firebase Android app

1. Open Firebase Console and create or select the Drovixa project.
2. Add an Android app with package name `com.drovixa.app`.
3. Download `google-services.json` and place it at
   `drovixa/mobile/google-services.json`.
4. In Firebase **Project settings > Service accounts**, generate a new private
   key. Keep the downloaded JSON outside the repository.
5. Enable the Cloud Messaging API when Firebase asks for it.

Create the server-safe base64 value in PowerShell:

```powershell
$ServiceAccountFile = "$env:USERPROFILE\Downloads\drovixa-firebase-admin.json"
$FirebaseB64 = [Convert]::ToBase64String(
    [IO.File]::ReadAllBytes($ServiceAccountFile)
)
$FirebaseB64 | Set-Clipboard
```

Put the project ID and the copied base64 string in the root `.env`:

```dotenv
PUSH_PROVIDER=firebase
FIREBASE_PROJECT_ID=your-firebase-project-id
FIREBASE_SERVICE_ACCOUNT_JSON_B64=the-complete-base64-value
FIREBASE_DRY_RUN=false
PUSH_BATCH_SIZE=500
```

Never put the Admin service-account value in `mobile/.env`.

## 2. Test Firebase locally

```powershell
$DockerExe = "C:\Program Files\Docker\Docker\resources\bin\docker.exe"
Set-Location "C:\Users\touss\DrovixaProject\drovixa"

& $DockerExe compose up --build -d --wait --force-recreate backend worker scheduler admin web
.\scripts\verify-phase9.ps1
```

## 3. Create an Android development build

Remote notifications are unavailable in Expo Go on current Android Expo SDKs.
Use EAS:

```powershell
Set-Location "C:\Users\touss\DrovixaProject\drovixa"
npm install
npx eas-cli login
npx eas-cli build:configure

npx eas-cli build --platform android --profile development
```

Before the remote build, add `mobile/google-services.json` as an EAS **file**
environment variable named `GOOGLE_SERVICES_FILE` for the `development` and
`production` environments. Use the Expo dashboard's Environment Variables page;
the file variable is exposed to the build as a temporary path. Then run
`npx eas-cli credentials --platform android` and upload the separate Firebase
Admin service-account JSON under **FCM V1 service account key**. Install the
resulting build on a physical phone, sign in, accept notification permission,
and verify the device appears under `GET /api/v1/push-tokens`.

## 4. Prepare the Git repository for Render

Render Blueprints read `render.yaml` from the Git repository root. Push the
complete `drovixa` folder to a private GitHub or GitLab repository. Never commit:

- `.env` or `mobile/.env`
- `google-services.json`
- Firebase Admin service-account JSON
- Mux credentials or signing keys

## 5. Create the Render Blueprint

In Render, choose **New > Blueprint**, connect the repository, and select the
root `render.yaml`. The Blueprint creates:

- `drovixa-api`
- `drovixa-web`
- `drovixa-admin`
- `drovixa-worker` with Celery Beat
- `drovixa-postgres`
- `drovixa-redis` Render Key Value

Fill every prompted `sync: false` value. Important values:

| Variable | Value |
| --- | --- |
| `BACKEND_CORS_ORIGINS` | JSON list containing the final Web and Admin HTTPS origins |
| `FIRST_SUPERUSER_EMAIL` | Drovixa owner email |
| `FIRST_SUPERUSER_PASSWORD` | Unique password with at least 12 characters |
| `MUX_*` | Existing Mux credentials from the current `.env` |
| `MUX_UPLOAD_CORS_ORIGIN` | Final Admin or upload UI HTTPS origin, never `*` |
| `FIREBASE_PROJECT_ID` | Firebase project ID |
| `FIREBASE_SERVICE_ACCOUNT_JSON_B64` | Complete base64 service-account JSON |

Enter the same Firebase values for both the API and worker when Render prompts.
The API runs migrations before each deploy and bootstraps the super administrator
only after the first successful deploy.

The Blueprint uses paid `starter` services because Render does not offer a free
background worker and free instances are not appropriate for a production
streaming service. Review the current Render estimate before approving creation.

## 6. Point the clients to Render

After Render assigns the final URLs, update the mobile build environment:

```dotenv
EXPO_PUBLIC_API_URL=https://YOUR-DROVIXA-API.onrender.com/api/v1
EXPO_PUBLIC_APP_ENV=production
EXPO_PUBLIC_RELEASE=drovixa-mobile@0.9.0
EXPO_PUBLIC_PUSH_ENABLED=true
```

If the actual Web/Admin hostnames differ from the values entered during Blueprint
creation, update `BACKEND_CORS_ORIGINS` on the API and redeploy it.

## 7. Production checks

```powershell
Invoke-RestMethod "https://YOUR-DROVIXA-API.onrender.com/api/v1/health/ready" |
    ConvertTo-Json -Depth 5

Start-Process "https://YOUR-DROVIXA-WEB.onrender.com"
Start-Process "https://YOUR-DROVIXA-ADMIN.onrender.com/login"
```

Then create a test campaign in Admin with both `in_app` and `push`, send it to a
small test audience, and inspect its delivery summary before sending to everyone.
