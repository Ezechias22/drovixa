import { useMutation, useQuery } from '@tanstack/react-query';
import axios from 'axios';
import { useLocalSearchParams, useRouter } from 'expo-router';
import { useEffect, useState } from 'react';
import { ActivityIndicator, Alert, Modal, Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';

import { CommentsPanel } from '@/features/community/CommentsPanel';
import { getFeatureFlags } from '@/features/configuration/api';
import { createWatchParty } from '@/features/growth/api';
import { DrovixaVideoPlayer } from '@/features/player/DrovixaVideoPlayer';
import { authorizePlayback, playbackRefreshInterval } from '@/features/player/api';
import type { PlaybackTarget } from '@/features/player/types';
import { getOrCreateDeviceId } from '@/services/device';
import { downloadForOffline, type DownloadProgress } from '@/services/offline-downloads';
import { useI18n } from '@/i18n';
import { useAuthStore } from '@/stores/auth-store';

export default function WatchScreen() {
  const { t } = useI18n();
  const params = useLocalSearchParams<{ id: string; type?: string; target?: string }>();
  const [deviceId, setDeviceId] = useState<string | null>(null);
  const [commentsOpen, setCommentsOpen] = useState(false);
  const [downloadProgress, setDownloadProgress] = useState<DownloadProgress | null>(null);
  const session = useAuthStore((state) => state.session);
  const router = useRouter();
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
  const offline = useMutation({
    mutationFn: () => downloadForOffline({
      id: params.id,
      target,
      title: grant.data!.title,
      posterUrl: grant.data!.poster_url,
      onProgress: setDownloadProgress,
    }),
    onSuccess: () => {
      setDownloadProgress(null);
      Alert.alert(t('player.readyTitle'), t('player.readyBody'));
    },
    onError: (error) => {
      setDownloadProgress(null);
      const message = axios.isAxiosError(error) ? error.response?.data?.error?.message : null;
      Alert.alert('Download', message ?? 'Download failed. Please try again.');
    },
  });
  const party = useMutation({
    mutationFn: () => createWatchParty({ contentId: grant.data!.content_id, episodeId: grant.data!.episode_id, title: grant.data!.content_title }),
    onSuccess: (data) => router.push(`/watch-party/${data.invite_code}` as never),
    onError: (error) => Alert.alert('Watch Party', axios.isAxiosError(error) ? error.response?.data?.error?.message ?? 'Could not create party.' : 'Could not create party.'),
  });

  if (grant.isPending) {
    return (
      <View style={styles.center}>
        <ActivityIndicator color="#FF3D71" size="large" />
        <Text style={styles.secondary}>{t('player.authorizing')}</Text>
      </View>
    );
  }
  if (grant.isError) {
    const message = axios.isAxiosError(grant.error)
      ? grant.error.response?.data?.error?.message
      : null;
    return (
      <View style={styles.center}>
        <Text style={styles.title}>{t('player.unavailable')}</Text>
        <Text style={styles.secondary}>{message ?? t('player.tryLater')}</Text>
      </View>
    );
  }
  return (
    <View style={styles.screen}>
      <DrovixaVideoPlayer grant={grant.data} onRetry={() => void grant.refetch()} />
      {session && flags.data?.downloads_enabled?.enabled ? (
        <Pressable disabled={offline.isPending} onPress={() => offline.mutate()} style={styles.downloadButton}>
          <Text style={styles.commentsButtonText}>{downloadProgress
            ? `${downloadProgress.phase === 'preparing' ? t('player.preparing') : downloadProgress.phase === 'saving' ? t('player.saving') : t('player.downloading')} ${downloadProgress.percent}%`
            : `↓ ${t('player.download')}`}</Text>
        </Pressable>
      ) : null}
      {session && flags.data?.watch_party_enabled?.enabled ? <Pressable disabled={party.isPending} onPress={()=>party.mutate()} style={styles.partyButton}><Text style={styles.commentsButtonText}>{party.isPending?'Creating…':'◉ Watch Party'}</Text></Pressable>:null}
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
  downloadButton: { position: 'absolute', left: 18, bottom: 22, paddingHorizontal: 16, paddingVertical: 11, borderRadius: 99, backgroundColor: '#111318e8' },
  partyButton: { position: 'absolute', left: 18, top: 22, paddingHorizontal: 16, paddingVertical: 11, borderRadius: 99, backgroundColor: '#ff3d71dd' },
  commentsButtonText: { color: '#FFFFFF', fontWeight: '900' },
  commentsScreen: { flex: 1, backgroundColor: '#08090B' },
  commentsHeader: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingHorizontal: 20, paddingTop: 56, paddingBottom: 14, borderBottomWidth: StyleSheet.hairlineWidth, borderBottomColor: '#ffffff18' },
  commentsTitle: { color: '#FFFFFF', fontSize: 23, fontWeight: '900' },
  close: { color: '#FFFFFF', fontSize: 32 },
  commentsContent: { padding: 20, paddingBottom: 48 },
});
