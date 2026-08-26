# Drovixa production and store release checklist

## Engineering

- [ ] Phase 12 verifier, CI, security scan, and container builds pass.
- [ ] Neon backup is recent, checksummed, and restore-tested on a disposable DB.
- [ ] Render API, Web, Admin, Redis, Neon, Mux, and Firebase are healthy.
- [ ] Signed playback, upload webhooks, notifications, auth, and deletion work.
- [ ] Preview APK passes upgrade, offline, background, and low-network tests.
- [ ] Sentry releases and alert recipients are configured without secrets in Git.

## Product and content

- [ ] Only licensed content is published; posters, subtitles, and ratings match.
- [ ] Guest/free/premium/coin rules match the UI and server entitlements.
- [ ] Support, moderation, copyright, refund, and incident contacts are staffed.

## Legal and stores

- [ ] Legal entity and policies are reviewed and published on HTTPS URLs.
- [ ] Account deletion works in app and through the public request path.
- [ ] Google/Apple data, ads, UGC, age-rating, and purchase declarations match
      the running build.
- [ ] OAuth, push, IAP/payment, signing, and store-console accounts are approved.
- [ ] Reviewer notes and a non-owner test account are ready.

## Release

- [ ] Create immutable tag `v0.12.0` only after all required gates pass.
- [ ] Roll out to internal testers, then a small production percentage.
- [ ] Monitor errors, latency, playback failures, signups, payments, and support.
- [ ] Keep the previous known-good release and rollback steps available.
