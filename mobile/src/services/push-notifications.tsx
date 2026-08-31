import Constants from 'expo-constants';
import * as Device from 'expo-device';
import * as Notifications from 'expo-notifications';
import { type Href, useRouter } from 'expo-router';
import { useEffect } from 'react';
import { Platform } from 'react-native';

import { apiClient } from '@/api/client';
import { useAuthStore } from '@/stores/auth-store';

Notifications.setNotificationHandler({
  handleNotification: async () => ({
    shouldPlaySound: true,
    shouldSetBadge: false,
    shouldShowBanner: true,
    shouldShowList: true,
  }),
});

export function safeNotificationRoute(value: unknown): Href | null {
  if (typeof value !== 'string') return null;
  const path = value.startsWith('drovixa://') ? `/${value.slice('drovixa://'.length)}` : value;
  const allowed = /^\/(notifications|coins|premium|series\/[^/?#]+|movie\/[^/?#]+|watch\/[^/?#]+)(?:\?target=(episode|movie))?$/;
  return allowed.test(path) ? (path as Href) : null;
}

async function registerNativePushToken(): Promise<void> {
  if (process.env.EXPO_PUBLIC_PUSH_ENABLED === 'false') return;
  if (!Device.isDevice || Platform.OS !== 'android') return;
  if (Constants.appOwnership === 'expo') {
    if (__DEV__) console.info('Remote push requires an EAS development build, not Expo Go.');
    return;
  }
  await Notifications.setNotificationChannelAsync('drovixa_updates', {
    name: 'Drovixa updates',
    description: 'New releases, account activity, and recommendations.',
    importance: Notifications.AndroidImportance.HIGH,
    sound: 'default',
    vibrationPattern: [0, 180, 100, 180],
    lightColor: '#FF4D8D',
  });
  const existing = await Notifications.getPermissionsAsync();
  const permission =
    existing.status === 'granted' ? existing : await Notifications.requestPermissionsAsync();
  if (permission.status !== 'granted') return;
  const nativeToken = await Notifications.getDevicePushTokenAsync();
  const token =
    typeof nativeToken.data === 'string' ? nativeToken.data : JSON.stringify(nativeToken.data);
  await apiClient.post('/push-tokens', {
    provider: 'fcm',
    platform: 'android',
    token,
    app_version: Constants.expoConfig?.version ?? '0.9.0',
    locale: Intl.DateTimeFormat().resolvedOptions().locale,
  });
}

export async function unregisterCurrentPushToken(): Promise<void> {
  await apiClient.delete('/push-tokens/current');
}

export function PushNotificationsBridge() {
  const router = useRouter();
  const accessToken = useAuthStore((state) => state.session?.accessToken);

  useEffect(() => {
    if (!accessToken) return;
    void registerNativePushToken().catch((error: unknown) => {
      if (__DEV__) console.warn('Drovixa push registration failed.', error);
    });
  }, [accessToken]);

  useEffect(() => {
    function openNotification(notification: Notifications.Notification) {
      const route = safeNotificationRoute(notification.request.content.data?.action_url);
      if (route) router.push(route);
    }
    const lastResponse = Notifications.getLastNotificationResponse();
    if (lastResponse?.notification) openNotification(lastResponse.notification);
    const subscription = Notifications.addNotificationResponseReceivedListener(
      (response: Notifications.NotificationResponse) => {
        openNotification(response.notification);
      },
    );
    return () => subscription.remove();
  }, [router]);

  return null;
}
