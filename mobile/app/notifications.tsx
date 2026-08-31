import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useRouter } from 'expo-router';
import { Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';

import { EmptyState, ErrorState, LoadingState } from '@/components/ScreenStates';
import { getNotifications, readNotification } from '@/features/catalog/api';
import type { NotificationData } from '@/features/catalog/types';
import { useI18n } from '@/i18n';
import { safeNotificationRoute } from '@/services/push-notifications';
import { useAuthStore } from '@/stores/auth-store';
import { colors } from '@/theme';

export default function NotificationsScreen() {
  const { locale, t } = useI18n();
  const session = useAuthStore((state) => state.session);
  const router = useRouter();
  const client = useQueryClient();
  const query = useQuery({
    queryKey: ['notifications'],
    queryFn: getNotifications,
    enabled: Boolean(session),
  });

  const open = async (item: NotificationData) => {
    if (!item.read) {
      await readNotification(item.id).catch(() => undefined);
      await client.invalidateQueries({ queryKey: ['notifications'] });
    }
    const route = safeNotificationRoute(item.action_url);
    if (route) router.push(route);
  };

  if (!session) return <View style={s.center}>
    <Text style={s.title}>{t('notifications.guestTitle')}</Text>
    <Text style={s.muted}>{t('notifications.guestBody')}</Text>
    <Pressable style={s.button} onPress={() => router.push('/login')}><Text style={s.buttonText}>{t('common.signIn')}</Text></Pressable>
  </View>;
  if (query.isPending) return <LoadingState />;
  if (query.isError) return <ErrorState retry={() => void query.refetch()} />;
  return <ScrollView style={s.screen} contentContainerStyle={s.content}>
    {query.data.items.length ? query.data.items.map((item) => <Pressable key={item.id} onPress={() => void open(item)} style={[s.card, !item.read && s.unread]}>
      <View style={[s.dot, item.read && s.dotRead]} />
      <View style={s.copy}>
        <Text style={s.cardTitle}>{item.title}</Text>
        <Text style={s.body}>{item.body}</Text>
        <Text style={s.date}>{new Date(item.created_at).toLocaleDateString(locale)}</Text>
      </View>
    </Pressable>) : <EmptyState title={t('notifications.emptyTitle')} body={t('notifications.emptyBody')} />}
  </ScrollView>;
}

const s = StyleSheet.create({
  screen: { flex: 1, backgroundColor: colors.background },
  content: { padding: 18, gap: 10 },
  card: { flexDirection: 'row', gap: 12, padding: 17, borderRadius: 18, backgroundColor: colors.card },
  unread: { backgroundColor: colors.cardSecondary },
  dot: { width: 8, height: 8, borderRadius: 4, marginTop: 7, backgroundColor: colors.accent },
  dotRead: { backgroundColor: '#4b5563' },
  copy: { flex: 1, gap: 5 },
  cardTitle: { color: colors.text, fontSize: 16, fontWeight: '900' },
  body: { color: colors.muted, lineHeight: 20 },
  date: { color: '#6b7280', fontSize: 11, marginTop: 4 },
  center: { flex: 1, alignItems: 'center', justifyContent: 'center', gap: 13, padding: 30, backgroundColor: colors.background },
  title: { color: colors.text, fontSize: 24, fontWeight: '900' },
  muted: { color: colors.muted, textAlign: 'center', lineHeight: 21 },
  button: { marginTop: 8, paddingHorizontal: 25, paddingVertical: 13, borderRadius: 99, backgroundColor: colors.text },
  buttonText: { color: colors.background, fontWeight: '900' },
});
