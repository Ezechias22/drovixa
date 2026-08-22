# Drovixa Mobile 0.5.3 authentication hotfix

This cumulative mobile hotfix makes authentication reachable from the Home
header and Profile tab, improves the login/register forms for phone keyboards,
and prevents password auto-capitalization on Android.

It also aligns registration validation with the backend requirement of at least
eight characters containing a letter and a number, and displays a useful
development message when the phone cannot reach the configured API URL.

After applying the hotfix, restart Expo with a clean Metro cache:

```text
npm run start --workspace @drovixa/mobile -- --clear
```
