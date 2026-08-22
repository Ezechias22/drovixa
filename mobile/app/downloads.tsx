import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useRouter } from 'expo-router';
import { Alert, Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';

import { EmptyState, LoadingState } from '@/components/ScreenStates';
import type { OfflineDownload } from '@/features/personalization/types';
import { getOfflineDownloads, removeOfflineDownload } from '@/services/offline-downloads';
import { colors } from '@/theme';

export default function DownloadsScreen() {
  const router = useRouter();
  const queryClient = useQueryClient();
  const downloads = useQuery({ queryKey: ['offline-downloads'], queryFn: getOfflineDownloads });
  const remove = useMutation({
    mutationFn: removeOfflineDownload,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['offline-downloads'] }),
  });
  if (downloads.isPending) return <LoadingState label="Loading downloads…" />;
  return (
    <ScrollView style={styles.screen} contentContainerStyle={styles.content}>
      <Text style={styles.eyebrow}>OFFLINE & PRIVATE</Text>
      <Text style={styles.title}>Downloads</Text>
      <Text style={styles.muted}>Videos stay inside Drovixa's private app storage and stop playing when their license expires.</Text>
      {!downloads.data?.length ? (
        <EmptyState title="No downloads yet" body="Use Download from a movie or episode player." />
      ) : downloads.data.map((item) => (
        <DownloadRow
          key={item.id}
          item={item}
          onPlay={() => router.push({ pathname: '/offline/[id]', params: { id: item.id } })}
          onRemove={() => Alert.alert('Delete download?', item.title, [
            { text: 'Cancel', style: 'cancel' },
            { text: 'Delete', style: 'destructive', onPress: () => remove.mutate(item) },
          ])}
        />
      ))}
    </ScrollView>
  );
}

function DownloadRow({ item, onPlay, onRemove }: { item: OfflineDownload; onPlay: () => void; onRemove: () => void }) {
  const expired = Date.parse(item.expiresAt) <= Date.now();
  return (
    <View style={styles.card}>
      <Pressable disabled={expired} onPress={onPlay} style={styles.flex}>
        <Text style={styles.name}>{item.title}</Text>
        <Text style={styles.muted}>{item.quality} · {(item.bytes / 1024 / 1024).toFixed(1)} MB</Text>
        <Text style={expired ? styles.expired : styles.valid}>
          {expired ? 'LICENSE EXPIRED' : `VALID UNTIL ${new Date(item.expiresAt).toLocaleString()}`}
        </Text>
      </Pressable>
      <Pressable onPress={onRemove}><Text style={styles.remove}>Delete</Text></Pressable>
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
