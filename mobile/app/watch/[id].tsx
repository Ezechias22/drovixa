import { useQuery } from '@tanstack/react-query';
import axios from 'axios';
import { useLocalSearchParams } from 'expo-router';
import { useEffect, useState } from 'react';
import { ActivityIndicator, Modal, Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';

import { CommentsPanel } from '@/features/community/CommentsPanel';
import { getFeatureFlags } from '@/features/configuration/api';
import { DrovixaVideoPlayer } from '@/features/player/DrovixaVideoPlayer';
import { authorizePlayback, playbackRefreshInterval } from '@/features/player/api';
import type { PlaybackTarget } from '@/features/player/types';
import { getOrCreateDeviceId } from '@/services/device';

export default function WatchScreen() {
  const params = useLocalSearchParams<{ id: string; type?: string; target?: string }>();
  const [deviceId, setDeviceId] = useState<string | null>(null);
  const [commentsOpen, setCommentsOpen] = useState(false);
  const target: PlaybackTarget = params.target === 'movie' || params.type === 'movie' ? 'movie' : 'episode';

  useEffect(() => {
    void getOrCreateDeviceId().then(setDeviceId);
  }, []);

  const grant = useQuery({
    queryKey: ['playback', target, params.id, deviceId],
    queryFn: () => authorizePlayback({ id: params.id, target, clientDeviceId: deviceId! }),
    enabled: Boolean(params.id && deviceId),
    retry: false,
    refetchInterval: (query) => playbackRefreshInterval(query.state.data),
  });
  const flags = useQuery({ queryKey: ['feature-flags'], queryFn: getFeatureFlags });

  if (grant.isPending) {
    return (
      <View style={styles.center}>
        <ActivityIndicator color="#FF3D71" size="large" />
        <Text style={styles.secondary}>Authorizing secure playback…</Text>
      </View>
    );
  }
  if (grant.isError) {
    const message = axios.isAxiosError(grant.error)
      ? grant.error.response?.data?.error?.message
      : null;
    return (
      <View style={styles.center}>
        <Text style={styles.title}>Playback unavailable</Text>
        <Text style={styles.secondary}>{message ?? 'Please try again later.'}</Text>
      </View>
    );
  }
  return (
    <View style={styles.screen}>
      <DrovixaVideoPlayer grant={grant.data} />
      {target === 'episode' && flags.data?.comments_enabled?.enabled ? (
        <Pressable onPress={() => setCommentsOpen(true)} style={styles.commentsButton}>
          <Text style={styles.commentsButtonText}>◌ Comments</Text>
        </Pressable>
      ) : null}
      <Modal animationType="slide" onRequestClose={() => setCommentsOpen(false)} visible={commentsOpen}>
        <View style={styles.commentsScreen}>
          <View style={styles.commentsHeader}>
            <Text style={styles.commentsTitle}>Episode comments</Text>
            <Pressable onPress={() => setCommentsOpen(false)}><Text style={styles.close}>×</Text></Pressable>
          </View>
          <ScrollView contentContainerStyle={styles.commentsContent}>
            <CommentsPanel targetId={params.id} targetType="episode" />
          </ScrollView>
        </View>
      </Modal>
    </View>
  );
}

const styles = StyleSheet.create({
  screen: { flex: 1, justifyContent: 'center', backgroundColor: '#08090B' },
  center: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    gap: 12,
    padding: 28,
    backgroundColor: '#08090B',
  },
  title: { color: '#FFFFFF', fontSize: 22, fontWeight: '700' },
  secondary: { color: '#9CA3AF', fontSize: 15, textAlign: 'center' },
  commentsButton: { position: 'absolute', right: 18, bottom: 22, paddingHorizontal: 16, paddingVertical: 11, borderRadius: 99, backgroundColor: '#111318e8' },
  commentsButtonText: { color: '#FFFFFF', fontWeight: '900' },
  commentsScreen: { flex: 1, backgroundColor: '#08090B' },
  commentsHeader: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingHorizontal: 20, paddingTop: 56, paddingBottom: 14, borderBottomWidth: StyleSheet.hairlineWidth, borderBottomColor: '#ffffff18' },
  commentsTitle: { color: '#FFFFFF', fontSize: 23, fontWeight: '900' },
  close: { color: '#FFFFFF', fontSize: 32 },
  commentsContent: { padding: 20, paddingBottom: 48 },
});
