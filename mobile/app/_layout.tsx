import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import * as Sentry from '@sentry/react-native';
import { Stack } from 'expo-router';
import { StatusBar } from 'expo-status-bar';
import { useCallback, useEffect, useState } from 'react';
import { SafeAreaProvider } from 'react-native-safe-area-context';
import { AnimatedDrovixaSplash } from '@/components/AnimatedDrovixaSplash';
import { useAuthStore } from '@/stores/auth-store';
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
  const hydrated = useAuthStore((state) => state.hydrated);
  const hydrate = useAuthStore((state) => state.hydrate);
  const profileHydrated = useProfileStore((state) => state.hydrated);
  const hydrateProfile = useProfileStore((state) => state.hydrate);
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
  }, [hydrate, hydrateProfile]);

  const finishIntro = useCallback(() => setIntroComplete(true), []);

  if (!hydrated || !profileHydrated || !introComplete) {
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
          <Stack.Screen name="search" options={{ title: 'Search' }} />
          <Stack.Screen name="notifications" options={{ title: 'Notifications' }} />
          <Stack.Screen name="profiles" options={{ title: 'Profiles' }} />
          <Stack.Screen name="devices" options={{ title: 'Devices' }} />
          <Stack.Screen name="downloads" options={{ title: 'Downloads' }} />
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
