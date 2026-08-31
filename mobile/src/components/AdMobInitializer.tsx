import { useEffect } from 'react';
import { Platform } from 'react-native';

let initialized = false;

export function AdMobInitializer() {
  useEffect(() => {
    if (initialized || (Platform.OS !== 'android' && Platform.OS !== 'ios')) return;
    initialized = true;
    void (async () => {
      try {
        const ads = await import('react-native-google-mobile-ads');
        await ads.AdsConsent.gatherConsent({ tagForUnderAgeOfConsent: false });
        await ads.default().initialize();
      } catch (error) {
        initialized = false;
        if (__DEV__) console.warn('AdMob initialization skipped', error);
      }
    })();
  }, []);

  return null;
}
