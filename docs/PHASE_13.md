# Phase 13 — AdMob rewards and viewer engagement

## What ships

- Voluntary Google AdMob rewarded ads for authenticated non-Premium viewers.
- Ten bonus coins per verified completion by default, capped at five per day.
- Google server-side verification (SSV), idempotent wallet entries, transaction
  deduplication, expiry checks, user/ad-unit matching, and a per-user database
  lock around the daily cap.
- Consent collection before Google Mobile Ads initialization.
- Premium offers limited per app session and per calendar day. Offers never
  interrupt playback, offline playback, authentication, or the Premium screen.
- Scheduled Premium push campaigns for non-Premium users who allow promotions.
- Automatic in-app and push notifications when a series, movie, or episode is
  published, respecting notification preferences.
- Continue-watching reminders with a direct link to the saved movie or episode,
  respecting recommendation preferences and per-user cooldowns.
- Admin controls under Growth for all switches, coin values, daily caps, prompt
  frequency, and reminder cooldowns.

## Production configuration

Create an Android app and a Rewarded ad unit in Google AdMob. Configure:

- EAS `preview` and `production`: `EXPO_PUBLIC_ADMOB_ANDROID_APP_ID`
- Render API: `ADMOB_ANDROID_REWARDED_AD_UNIT_ID`
- AdMob Rewarded ad unit SSV callback:
  `https://drovixa-api-free.onrender.com/api/v1/webhooks/admob/reward`

The AdMob app ID and ad-unit ID are identifiers, not secret credentials. Never
use live ads while developing; staging defaults to Google's official test app
ID when no app ID is supplied. The backend remains fail-closed until a rewarded
ad-unit ID is configured.

## Release boundary

This phase adds a native Android dependency, so it requires one new APK/AAB.
After users install version `0.13.0`, later JavaScript/UI-only changes can again
use the existing Expo OTA publishing flow. Any later native dependency or app
configuration change still requires another store/native build.
