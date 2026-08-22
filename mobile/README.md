# Drovixa mobile — Phase 9

This Expo Router application contains the API-driven Home, Discover, vertical
Shorts, My List, Profile, Search, Notifications, auth and content-detail
experiences. Playback requests a short-lived signed Mux HLS grant before mounting
`expo-video`, supports fullscreen/Picture-in-Picture, and syncs authenticated
watch progress using backend policy.

Copy `mobile/.env.example` to `mobile/.env`, replace the sample IP with your
computer's current LAN IPv4 address, and run `npm run mobile` from the repository
root. The phone and computer must be on the same network. Never put Mux credentials
in this file; they belong only in the root backend `.env`.

Production builds use `eas.json`, remote app-version management, automatic build
number increments, an app-version runtime policy, native splash assets, and
optional Sentry reporting. Store submission still requires the owner's Expo,
Apple, and Google accounts and an explicit release decision.

Phase 9 registers the Android native FCM token after authentication, removes the
device token during sign-out, shows foreground notifications, and routes safe
notification actions into the app. Put `google-services.json` in `mobile/` only
for local EAS/native builds and set `GOOGLE_SERVICES_FILE=./google-services.json`.
Do not commit it. Remote push requires an EAS development or production build;
it is intentionally skipped in Expo Go.
