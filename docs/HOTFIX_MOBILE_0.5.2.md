# Drovixa Mobile 0.5.2 hotfix

This hotfix removes an explicit `AudioPlayer.pause()` cleanup call from the
animated splash. `useAudioPlayer` owns and automatically releases its shared
native player when the splash unmounts. Calling `pause()` during that teardown
could race with the automatic release in Expo Go and produce an
`AudioPlayer.pause has been rejected` error.

After applying the hotfix, restart Expo with a clean Metro cache:

```text
npm run start --workspace @drovixa/mobile -- --clear
```
