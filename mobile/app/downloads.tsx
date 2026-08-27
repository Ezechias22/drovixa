import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useRouter } from 'expo-router';
import { Alert, Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';

import { EmptyState, LoadingState } from '@/components/ScreenStates';
import type { OfflineDownload } from '@/features/personalization/types';
import { getOfflineDownloads, removeOfflineDownload } from '@/services/offline-downloads';
import { useI18n } from '@/i18n';
import { colors } from '@/theme';

export default function DownloadsScreen() {
  const { t } = useI18n();
  const router = useRouter();
  const queryClient = useQueryClient();
  const downloads = useQuery({ queryKey: ['offline-downloads'], queryFn: getOfflineDownloads });
  const remove = useMutation({
    mutationFn: removeOfflineDownload,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['offline-downloads'] }),
  });
  if (downloads.isPending) return <LoadingState />;
  return (
    <ScrollView style={styles.screen} contentContainerStyle={styles.content}>
      <Text style={styles.eyebrow}>{t('downloads.eyebrow')}</Text>
      <Text style={styles.title}>{t('downloads.title')}</Text>
      <Text style={styles.muted}>{t('downloads.subtitle')}</Text>
      {!downloads.data?.length ? (
        <EmptyState title={t('downloads.emptyTitle')} body={t('downloads.emptyBody')} />
      ) : downloads.data.map((item) => (
        <DownloadRow
          key={item.id}
          item={item}
          onPlay={() => router.push({ pathname: '/offline/[id]', params: { id: item.id } })}
          onRemove={() => Alert.alert(t('downloads.deleteTitle'), item.title, [
            { text: t('common.cancel'), style: 'cancel' },
            { text: t('common.delete'), style: 'destructive', onPress: () => remove.mutate(item) },
          ])}
        />
      ))}
    </ScrollView>
  );
}

function DownloadRow({ item, onPlay, onRemove }: { item: OfflineDownload; onPlay: () => void; onRemove: () => void }) {
  const { locale, t } = useI18n();
  const expired = Date.parse(item.expiresAt) <= Date.now();
  return (
    <View style={styles.card}>
      <Pressable disabled={expired} onPress={onPlay} style={styles.flex}>
        <Text style={styles.name}>{item.title}</Text>
        <Text style={styles.muted}>{item.quality} · {(item.bytes / 1024 / 1024).toFixed(1)} MB</Text>
        <Text style={expired ? styles.expired : styles.valid}>
          {expired ? t('downloads.expired') : t('downloads.validUntil', { date: new Date(item.expiresAt).toLocaleString(locale) })}
        </Text>
      </Pressable>
      <Pressable onPress={onRemove}><Text style={styles.remove}>{t('common.delete')}</Text></Pressable>
    </View>
  );
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: colors.background }, content: { gap: 15, padding: 20, paddingBottom: 48 },
  eyebrow: { color: colors.accent, fontSize: 10, fontWeight: '900', letterSpacing: 1.5 },
  title: { color: colors.text, fontSize: 36, fontWeight: '900' }, muted: { color: colors.muted, lineHeight: 20 },
  card: { flexDirection: 'row', alignItems: 'center', padding: 17, borderRadius: 18, backgroundColor: colors.card },
  flex: { flex: 1, gap: 5 }, name: { color: colors.text, fontSize: 17, fontWeight: '900' },
  valid: { color: colors.success, fontSize: 9, fontWeight: '900' }, expired: { color: colors.danger, fontSize: 9, fontWeight: '900' },
  remove: { color: colors.danger, fontWeight: '900', padding: 8 },
});
