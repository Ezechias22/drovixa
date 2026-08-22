# Drovixa Mobile 0.5.1 hotfix

This hotfix fixes the React Native `Text strings must be rendered within a
<Text> component` runtime error on Discover and introduces the branded Drovixa
launch sequence.

The launch sequence uses the supplied Drovixa mark, respects the operating
system's reduced-motion accessibility setting, runs for approximately 2.8
seconds, and plays an original 2.37-second Drovixa sonic mark on native clients.
Web autoplay is intentionally disabled because browsers require user consent.

## Included files

- `mobile/app/(tabs)/discover.tsx`
- `mobile/app/_layout.tsx`
- `mobile/src/components/AnimatedDrovixaSplash.tsx`
- `mobile/assets/audio/drovixa-intro.mp3`
- `mobile/package.json`
- `mobile/app.json`
- root `package.json` and `package-lock.json`

After applying the hotfix, run `npm install`, then restart Expo with a clean
Metro cache using `npm run start --workspace @drovixa/mobile -- --clear`.
