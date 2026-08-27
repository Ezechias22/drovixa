import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import * as Sentry from '@sentry/react-native';
import { Stack } from 'expo-router';
import { StatusBar } from 'expo-status-bar';
import { useCallback, useEffect, useState } from 'react';
import { SafeAreaProvider } from 'react-native-safe-area-context';
import { AnimatedDrovixaSplash } from '@/components/AnimatedDrovixaSplash';
import { useI18n, useLanguageStore } from '@/i18n';
import { useAuthStore } from '@/stores/auth-store';
import { usePlaybackStore } from '@/stores/playback-store';
import { useProfileStore } from '@/stores/profile-store';
import { PushNotificationsBridge } from '@/services/push-notifications';
import { colors } from '@/theme';

Sentry.init({
  dsn: process.env.EXPO_PUBLIC_SENTRY_DSN,
  environment: process.env.EXPO_PUBLIC_APP_ENV ?? 'development',
  release: process.env.EXPO_PUBLIC_RELEASE ?? 'drovixa-mobile@0.11.0',
  tracesSampleRate: Number(process.env.EXPO_PUBLIC_SENTRY_TRACES_SAMPLE_RATE ?? '0.1'),
  sendDefaultPii: false,
  enabled: Boolean(process.env.EXPO_PUBLIC_SENTRY_DSN),
});

function RootLayout() {
  const { t } = useI18n();
  const hydrated = useAuthStore((state) => state.hydrated);
  const hydrate = useAuthStore((state) => state.hydrate);
  const profileHydrated = useProfileStore((state) => state.hydrated);
  const hydrateProfile = useProfileStore((state) => state.hydrate);
  const languageHydrated = useLanguageStore((state) => state.hydrated);
  const hydrateLanguage = useLanguageStore((state) => state.hydrate);
  const playbackHydrated = usePlaybackStore((state) => state.hydrated);
  const hydratePlayback = usePlaybackStore((state) => state.hydrate);
  const [introComplete, setIntroComplete] = useState(false);
  const [client] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: { retry: 1, staleTime: 15_000 },
          mutations: { retry: 0 },
        },
      }),
  );

  useEffect(() => {
    void hydrate();
    void hydrateProfile();
    void hydrateLanguage();
    void hydratePlayback();
  }, [hydrate, hydrateLanguage, hydratePlayback, hydrateProfile]);

  const finishIntro = useCallback(() => setIntroComplete(true), []);

  if (!hydrated || !profileHydrated || !languageHydrated || !playbackHydrated || !introComplete) {
    return <AnimatedDrovixaSplash onFinished={finishIntro} />;
  }

  return (
    <SafeAreaProvider>
      <QueryClientProvider client={client}>
        <PushNotificationsBridge />
        <StatusBar style="light" />
        <Stack
          screenOptions={{
            contentStyle: { backgroundColor: colors.background },
            headerStyle: { backgroundColor: colors.background },
            headerTintColor: colors.text,
            headerShadowVisible: false,
          }}
        >
          <Stack.Screen name="index" options={{ headerShown: false }} />
          <Stack.Screen name="(tabs)" options={{ headerShown: false }} />
          <Stack.Screen name="search" options={{ title: t('discover.search') }} />
          <Stack.Screen name="notifications" options={{ title: t('profile.notifications') }} />
          <Stack.Screen name="profiles" options={{ title: t('profile.profiles') }} />
          <Stack.Screen name="devices" options={{ title: t('profile.devices') }} />
          <Stack.Screen name="downloads" options={{ title: t('profile.downloads') }} />
          <Stack.Screen name="language" options={{ title: t('language.title') }} />
          <Stack.Screen name="playback-settings" options={{ title: t('playback.title') }} />
          <Stack.Screen name="security" options={{ title: t('security.title') }} />
          <Stack.Screen name="help" options={{ title: t('help.title') }} />
          <Stack.Screen name="growth" options={{ title: 'Rewards & referrals' }} />
          <Stack.Screen name="watch-party/[code]" options={{ title: 'Watch Party' }} />
          <Stack.Screen name="offline/[id]" options={{ title: 'Offline playback' }} />
          <Stack.Screen name="coins" options={{ title: 'Coins', headerShown: false }} />
          <Stack.Screen name="premium" options={{ title: 'Premium', headerShown: false }} />
          <Stack.Screen
            name="login"
            options={{ headerShown: false, title: 'Sign in', presentation: 'modal' }}
          />
          <Stack.Screen
            name="register"
            options={{ headerShown: false, title: 'Create account', presentation: 'modal' }}
          />
          <Stack.Screen name="series/[slug]" options={{ title: '' }} />
          <Stack.Screen name="movie/[slug]" options={{ title: '' }} />
          <Stack.Screen name="watch/[id]" options={{ title: 'Now Playing' }} />
        </Stack>
      </QueryClientProvider>
    </SafeAreaProvider>
  );
}

export default Sentry.wrap(RootLayout);
