import { useVideoPlayer, VideoView } from 'expo-video';
import { useLocalSearchParams } from 'expo-router';
import { useEffect, useState } from 'react';
import { ActivityIndicator, StyleSheet, Text, View } from 'react-native';

import type { OfflineDownload } from '@/features/personalization/types';
import { getOfflineDownloads, verifyOfflineDownload } from '@/services/offline-downloads';
import { colors } from '@/theme';

export default function OfflinePlayerScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const [item, setItem] = useState<OfflineDownload | null>(null);
  const [allowed, setAllowed] = useState<boolean | null>(null);

  useEffect(() => {
    void getOfflineDownloads().then(async (items) => {
      const found = items.find((entry) => entry.id === id) ?? null;
      setItem(found);
      setAllowed(found ? await verifyOfflineDownload(found) : false);
    });
  }, [id]);

  if (allowed === null) return <View style={styles.center}><ActivityIndicator color={colors.accent} /></View>;
  if (!allowed || !item) return <View style={styles.center}><Text style={styles.title}>Download unavailable</Text><Text style={styles.muted}>Reconnect to renew this expired or revoked license.</Text></View>;
  return <OfflineVideo item={item} />;
}

function OfflineVideo({ item }: { item: OfflineDownload }) {
  const player = useVideoPlayer({ uri: item.localUri }, (instance) => instance.play());
  return (
    <View style={styles.screen}>
      <VideoView player={player} nativeControls allowsPictureInPicture style={styles.video} />
      <Text style={styles.title}>{item.title}</Text>
      <Text style={styles.muted}>Offline · {item.quality} · Private app storage</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  screen: { flex: 1, justifyContent: 'center', gap: 16, padding: 18, backgroundColor: colors.background },
  center: { flex: 1, alignItems: 'center', justifyContent: 'center', gap: 12, padding: 28, backgroundColor: colors.background },
  video: { width: '100%', aspectRatio: 16 / 9, backgroundColor: '#000' },
  title: { color: colors.text, fontSize: 23, fontWeight: '900' }, muted: { color: colors.muted, textAlign: 'center' },
});
