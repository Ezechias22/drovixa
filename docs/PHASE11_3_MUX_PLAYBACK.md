# Drovixa Phase 11.3 — Mux playback hotfix

This hotfix fixes the web player that opened but stayed at `0:00` with a blank
video surface.

## What changed

- The web Content Security Policy now permits Mux playback across `*.mux.com`
  instead of only `stream.mux.com`.
- Mux Data endpoints under `*.litix.io` are permitted.
- The HLS player retries one network failure and one recoverable media failure.
- Fatal HLS failures now show a safe, actionable error instead of a silent
  blank player.
- A retry button requests a fresh signed playback URL without exposing it.

No database migration or environment-secret change is included.

## Deploy

After applying the overlay, commit and push the two web files. Render should
automatically deploy `drovixa-web-free`. The API, admin, database, Redis, Mux,
and Firebase secrets do not need to be changed for this CSP fix.

Once Render reports Live, open the watch page in a private window or force a
hard refresh. If the player displays `Mux rejected the secure playback link`,
the remaining issue is a mismatch between `MUX_SIGNING_KEY_ID` and
`MUX_SIGNING_PRIVATE_KEY_B64` on the API service. A generic CDN error instead
points to network/CSP filtering.
