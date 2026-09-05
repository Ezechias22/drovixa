import { Ionicons } from '@expo/vector-icons';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import axios from 'axios';
import { useLocalSearchParams, useRouter } from 'expo-router';
import { useEffect, useMemo, useState } from 'react';
import { ActivityIndicator, Alert, Modal, Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';

import { CommentsPanel } from '@/features/community/CommentsPanel';
import { getEpisode, getEpisodes, toggleFavorite } from '@/features/catalog/api';
import { getFeatureFlags } from '@/features/configuration/api';
import { createWatchParty } from '@/features/growth/api';
import { DrovixaVideoPlayer } from '@/features/player/DrovixaVideoPlayer';
import { authorizePlayback, playbackRefreshInterval } from '@/features/player/api';
import type { PlaybackTarget, SubtitleTrack } from '@/features/player/types';
import { unlockEpisode } from '@/features/monetization/api';
import { useI18n } from '@/i18n';
import { getOrCreateDeviceId } from '@/services/device';
import { downloadForOffline, type DownloadProgress } from '@/services/offline-downloads';
import { useAuthStore } from '@/stores/auth-store';
import { usePlaybackStore } from '@/stores/playback-store';
import { useSubtitleStore } from '@/stores/subtitle-store';
import { colors } from '@/theme';

const unlockCopy = {
  ht: { title: 'Debloke epizòd la', body: (price: number) => `Sa ap itilize ${price} coins nan kont ou.`, button: (price: number) => `Debloke pou ${price} coins`, loading: 'Ap debloke…', insufficient: 'Ou pa gen ase coins.', failed: 'Nou pa t kapab debloke epizòd la.' },
  fr: { title: "Débloquer l'épisode", body: (price: number) => `${price} pièces seront utilisées sur votre compte.`, button: (price: number) => `Débloquer pour ${price} pièces`, loading: 'Déblocage…', insufficient: "Vous n'avez pas assez de pièces.", failed: "Impossible de débloquer l'épisode." },
  'pt-BR': { title: 'Desbloquear episódio', body: (price: number) => `${price} moedas serão usadas da sua conta.`, button: (price: number) => `Desbloquear por ${price} moedas`, loading: 'Desbloqueando…', insufficient: 'Você não tem moedas suficientes.', failed: 'Não foi possível desbloquear o episódio.' },
  es: { title: 'Desbloquear episodio', body: (price: number) => `Se usarán ${price} monedas de tu cuenta.`, button: (price: number) => `Desbloquear por ${price} monedas`, loading: 'Desbloqueando…', insufficient: 'No tienes suficientes monedas.', failed: 'No se pudo desbloquear el episodio.' },
  en: { title: 'Unlock this episode', body: (price: number) => `This will use ${price} coins from your account.`, button: (price: number) => `Unlock for ${price} coins`, loading: 'Unlocking…', insufficient: 'You do not have enough coins.', failed: 'The episode could not be unlocked.' },
} as const;

export default function WatchScreen() {
  const { t, language } = useI18n();
  const params = useLocalSearchParams<{ id: string; type?: string; target?: string }>();
  const router = useRouter();
  const queryClient = useQueryClient();
  const session = useAuthStore((state) => state.session);
  const autoplay = usePlaybackStore((state) => state.autoplay);
  const subtitlesEnabled = useSubtitleStore((state) => state.enabled);
  const preferredSubtitle = useSubtitleStore((state) => state.preferredLanguage);
  const [deviceId, setDeviceId] = useState<string | null>(null);
  const [commentsOpen, setCommentsOpen] = useState(false);
  const [episodesOpen, setEpisodesOpen] = useState(false);
  const [subtitleOpen, setSubtitleOpen] = useState(false);
  const [selectedSubtitleId, setSelectedSubtitleId] = useState<string | null>(null);
  const [downloadProgress, setDownloadProgress] = useState<DownloadProgress | null>(null);
  const [favoriteSaved, setFavoriteSaved] = useState(false);
  const target: PlaybackTarget = params.target === 'movie' || params.type === 'movie' ? 'movie' : 'episode';

  useEffect(() => { void getOrCreateDeviceId().then(setDeviceId); }, []);

  const grant = useQuery({
    queryKey: ['playback', target, params.id, deviceId],
    queryFn: () => authorizePlayback({ id: params.id, target, clientDeviceId: deviceId! }),
    enabled: Boolean(params.id && deviceId),
    retry: false,
    refetchInterval: (query) => playbackRefreshInterval(query.state.data),
  });
  const grantError = axios.isAxiosError(grant.error)
    ? grant.error.response?.data?.error
    : undefined;
  const needsCoinUnlock = target === 'episode' && grantError?.code === 'CONTENT_LOCKED';
  const lockedEpisode = useQuery({
    queryKey: ['episode', params.id],
    queryFn: () => getEpisode(params.id),
    enabled: needsCoinUnlock && Boolean(params.id),
    retry: false,
  });
  const flags = useQuery({ queryKey: ['feature-flags'], queryFn: getFeatureFlags });
  const episodes = useQuery({
    queryKey: ['episodes', grant.data?.content_id],
    queryFn: () => getEpisodes(grant.data!.content_id),
    enabled: target === 'episode' && Boolean(grant.data?.content_id),
  });

  useEffect(() => {
    if (!grant.data) return;
    setFavoriteSaved(grant.data.is_favorite);
    const tracks = grant.data.subtitles;
    if (!subtitlesEnabled || tracks.length === 0) {
      setSelectedSubtitleId(null);
      return;
    }
    const preferred = tracks.find((track) => track.language_code === preferredSubtitle);
    setSelectedSubtitleId((current) => current && tracks.some((track) => track.id === current)
      ? current
      : (preferred ?? tracks.find((track) => track.is_default) ?? tracks[0]).id);
  }, [grant.data, preferredSubtitle, subtitlesEnabled]);

  const selectedSubtitle = useMemo<SubtitleTrack | null>(() => (
    grant.data?.subtitles.find((track) => track.id === selectedSubtitleId) ?? null
  ), [grant.data?.subtitles, selectedSubtitleId]);

  const favorite = useMutation({
    mutationFn: () => toggleFavorite(grant.data!.content_id, favoriteSaved),
    onMutate: () => setFavoriteSaved((current) => !current),
    onError: () => setFavoriteSaved((current) => !current),
    onSettled: () => queryClient.invalidateQueries({ queryKey: ['favorites'] }),
  });
  const offline = useMutation({
    mutationFn: () => downloadForOffline({
      id: params.id,
      target,
      title: grant.data!.title,
      posterUrl: grant.data!.poster_url,
      onProgress: setDownloadProgress,
    }),
    onSuccess: () => { setDownloadProgress(null); Alert.alert(t('player.readyTitle'), t('player.readyBody')); },
    onError: (error) => {
      setDownloadProgress(null);
      const message = axios.isAxiosError(error) ? error.response?.data?.error?.message : null;
      Alert.alert(t('player.download'), message ?? 'Download failed. Please try again.');
    },
  });
  const party = useMutation({
    mutationFn: () => createWatchParty({ contentId: grant.data!.content_id, episodeId: grant.data!.episode_id, title: grant.data!.content_title }),
    onSuccess: (data) => router.push(`/watch-party/${data.invite_code}` as never),
    onError: (error) => Alert.alert('Watch Party', axios.isAxiosError(error) ? error.response?.data?.error?.message ?? 'Could not create party.' : 'Could not create party.'),
  });
  const unlock = useMutation({
    mutationFn: () => unlockEpisode(params.id),
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ['wallet'] }),
        queryClient.invalidateQueries({ queryKey: ['episodes'] }),
        queryClient.invalidateQueries({ queryKey: ['episode', params.id] }),
      ]);
      await grant.refetch();
    },
    onError: (error) => {
      const apiError = axios.isAxiosError(error) ? error.response?.data?.error : undefined;
      Alert.alert(
        unlockCopy[language].title,
        apiError?.code === 'INSUFFICIENT_COINS'
          ? unlockCopy[language].insufficient
          : (apiError?.message ?? unlockCopy[language].failed),
      );
    },
  });

  const playEpisode = (id: string) => {
    setEpisodesOpen(false);
    router.replace({ pathname: '/watch/[id]', params: { id, target: 'episode' } });
  };
  const playNext = () => {
    if (autoplay && grant.data?.autoplay_next && grant.data.next_episode_id) {
      playEpisode(grant.data.next_episode_id);
    }
  };

  if (grant.isPending) return <View style={styles.center}><ActivityIndicator color={colors.accent} size="large" /><Text style={styles.secondary}>{t('player.authorizing')}</Text></View>;
  if (needsCoinUnlock) {
    const price = lockedEpisode.data?.coin_price;
    const confirmUnlock = () => {
      if (!session) {
        router.push('/login');
        return;
      }
      if (price === undefined) return;
      Alert.alert(
        unlockCopy[language].title,
        unlockCopy[language].body(price),
        [
          { text: t('common.cancel'), style: 'cancel' },
          { text: unlockCopy[language].button(price), onPress: () => unlock.mutate() },
        ],
      );
    };
    return (
      <View style={styles.center}>
        <Ionicons color={colors.accent} name="lock-closed" size={36} />
        <Text style={styles.title}>{unlockCopy[language].title}</Text>
        <Text style={styles.secondary}>
          {price === undefined ? t('common.loading') : unlockCopy[language].body(price)}
        </Text>
        <Pressable
          disabled={price === undefined || unlock.isPending}
          onPress={confirmUnlock}
          style={[styles.unlockButton, (price === undefined || unlock.isPending) && styles.disabled]}
        >
          <Text style={styles.unlockButtonText}>
            {unlock.isPending
              ? unlockCopy[language].loading
              : price === undefined
                ? t('common.loading')
                : unlockCopy[language].button(price)}
          </Text>
        </Pressable>
      </View>
    );
  }
  if (grant.isError) {
    return <View style={styles.center}><Text style={styles.title}>{t('player.unavailable')}</Text><Text style={styles.secondary}>{grantError?.message ?? t('player.tryLater')}</Text></View>;
  }

  const currentEpisode = episodes.data?.find((episode) => episode.id === params.id);
  return (
    <ScrollView style={styles.screen} contentContainerStyle={styles.content}>
      <DrovixaVideoPlayer
        grant={grant.data}
        selectedSubtitle={selectedSubtitle}
        overlayActions={(
          <View style={[styles.playerActions, grant.data.orientation !== 'vertical' && styles.playerActionsHorizontal]}>
            <PlayerAction icon={favoriteSaved ? 'bookmark' : 'bookmark-outline'} label={favoriteSaved ? t('content.saved') : t('content.myList')} onPress={() => session ? favorite.mutate() : router.push('/login')} />
            {target === 'episode' && flags.data?.comments_enabled?.enabled ? <PlayerAction icon="chatbubble-ellipses-outline" label="Comments" onPress={() => setCommentsOpen(true)} /> : null}
            {session && flags.data?.downloads_enabled?.enabled ? <PlayerAction icon="download-outline" label={downloadProgress ? `${downloadProgress.percent}%` : t('player.download')} disabled={offline.isPending} onPress={() => offline.mutate()} /> : null}
            {grant.data.subtitles.length ? <PlayerAction icon="text-outline" label={selectedSubtitle?.label ?? 'Subtitles'} onPress={() => setSubtitleOpen(true)} /> : null}
            {session && flags.data?.watch_party_enabled?.enabled ? <PlayerAction icon="people-outline" label="Party" disabled={party.isPending} onPress={() => party.mutate()} /> : null}
          </View>
        )}
        onEnded={playNext}
        onRetry={() => void grant.refetch()}
      />
      <View style={styles.copy}>
        <Text style={styles.contentTitle}>{grant.data.content_title}</Text>
        <Text style={styles.episodeTitle}>{target === 'episode' && currentEpisode ? `Episode ${currentEpisode.episode_number} · ` : ''}{grant.data.title}</Text>
      </View>

      {target === 'episode' ? (
        <View style={styles.episodeSection}>
          <Pressable onPress={() => setEpisodesOpen((open) => !open)} style={styles.episodeToggle}>
            <View><Text style={styles.episodeToggleTitle}>Episodes</Text><Text style={styles.secondary}>{episodes.data?.length ?? 0} available</Text></View>
            <Ionicons color={colors.text} name={episodesOpen ? 'chevron-up' : 'chevron-down'} size={24} />
          </Pressable>
          {episodesOpen ? <View style={styles.episodeGrid}>{episodes.data?.map((episode) => (
            <Pressable key={episode.id} onPress={() => playEpisode(episode.id)} style={[styles.episodeCell, episode.id === params.id && styles.episodeCellActive]}>
              <Text style={[styles.episodeNumber, episode.id === params.id && styles.episodeNumberActive]}>{episode.episode_number}</Text>
            </Pressable>
          ))}</View> : null}
        </View>
      ) : null}

      <Modal animationType="slide" onRequestClose={() => setCommentsOpen(false)} visible={commentsOpen}>
        <View style={styles.modalScreen}><ModalHeader title="Episode comments" onClose={() => setCommentsOpen(false)} /><ScrollView contentContainerStyle={styles.modalContent}><CommentsPanel targetId={params.id} targetType="episode" /></ScrollView></View>
      </Modal>
      <Modal animationType="slide" transparent onRequestClose={() => setSubtitleOpen(false)} visible={subtitleOpen}>
        <Pressable onPress={() => setSubtitleOpen(false)} style={styles.sheetBackdrop}>
          <View style={styles.sheet}>
            <Text style={styles.sheetTitle}>Subtitles</Text>
            <Pressable onPress={() => { setSelectedSubtitleId(null); setSubtitleOpen(false); }} style={styles.track}><Text style={styles.trackText}>Off</Text>{selectedSubtitleId === null ? <Ionicons color={colors.accent} name="checkmark" size={22} /> : null}</Pressable>
            {grant.data.subtitles.map((track) => <Pressable key={track.id} onPress={() => { setSelectedSubtitleId(track.id); setSubtitleOpen(false); }} style={styles.track}><Text style={styles.trackText}>{track.label} · {track.language_code.toUpperCase()}</Text>{selectedSubtitleId === track.id ? <Ionicons color={colors.accent} name="checkmark" size={22} /> : null}</Pressable>)}
          </View>
        </Pressable>
      </Modal>
    </ScrollView>
  );
}

function PlayerAction({ icon, label, disabled, onPress }: { icon: keyof typeof Ionicons.glyphMap; label: string; disabled?: boolean; onPress: () => void }) {
  return <Pressable disabled={disabled} onPress={onPress} style={[styles.playerAction, disabled && styles.disabled]}><View style={styles.playerActionIcon}><Ionicons color="#fff" name={icon} size={21} /></View><Text numberOfLines={1} style={styles.playerActionLabel}>{label}</Text></Pressable>;
}

function ModalHeader({ title, onClose }: { title: string; onClose: () => void }) {
  return <View style={styles.modalHeader}><Text style={styles.modalTitle}>{title}</Text><Pressable onPress={onClose}><Text style={styles.close}>×</Text></Pressable></View>;
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: colors.background }, content: { paddingBottom: 46 },
  center: { flex: 1, alignItems: 'center', justifyContent: 'center', gap: 12, padding: 28, backgroundColor: colors.background },
  title: { color: colors.text, fontSize: 22, fontWeight: '800' }, secondary: { color: colors.muted, fontSize: 13 },
  unlockButton: { marginTop: 10, minWidth: 210, alignItems: 'center', paddingHorizontal: 20, paddingVertical: 14, borderRadius: 99, backgroundColor: colors.accent }, unlockButtonText: { color: '#fff', fontWeight: '900' },
  copy: { gap: 4, paddingHorizontal: 18, paddingTop: 17 }, contentTitle: { color: colors.text, fontSize: 22, fontWeight: '900' }, episodeTitle: { color: colors.muted, fontSize: 14 },
  playerActions: { position: 'absolute', right: 9, bottom: 54, gap: 8, alignItems: 'center' }, playerActionsHorizontal: { left: 10, right: 10, top: 8, bottom: undefined, flexDirection: 'row', justifyContent: 'space-evenly' }, playerAction: { width: 58, alignItems: 'center', gap: 3 }, playerActionIcon: { width: 38, height: 38, borderRadius: 19, alignItems: 'center', justifyContent: 'center', backgroundColor: '#05070BCC', borderWidth: 1, borderColor: '#FFFFFF30' }, playerActionLabel: { color: '#fff', fontSize: 8, fontWeight: '900', maxWidth: 58, textShadowColor: '#000', textShadowRadius: 4 }, disabled: { opacity: 0.55 },
  episodeSection: { marginHorizontal: 16, borderRadius: 22, overflow: 'hidden', backgroundColor: colors.card }, episodeToggle: { minHeight: 72, flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingHorizontal: 18 }, episodeToggleTitle: { color: colors.text, fontSize: 19, fontWeight: '900' }, episodeGrid: { flexDirection: 'row', flexWrap: 'wrap', gap: 9, padding: 14, paddingTop: 2 }, episodeCell: { width: 52, height: 52, alignItems: 'center', justifyContent: 'center', borderRadius: 13, backgroundColor: colors.cardSecondary }, episodeCellActive: { backgroundColor: colors.accent }, episodeNumber: { color: colors.text, fontWeight: '900' }, episodeNumberActive: { color: '#fff' },
  modalScreen: { flex: 1, backgroundColor: colors.background }, modalHeader: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingHorizontal: 20, paddingTop: 56, paddingBottom: 14, borderBottomWidth: StyleSheet.hairlineWidth, borderBottomColor: colors.line }, modalTitle: { color: colors.text, fontSize: 23, fontWeight: '900' }, close: { color: colors.text, fontSize: 32 }, modalContent: { padding: 20, paddingBottom: 48 },
  sheetBackdrop: { flex: 1, justifyContent: 'flex-end', backgroundColor: '#0009' }, sheet: { gap: 4, padding: 20, paddingBottom: 38, borderTopLeftRadius: 28, borderTopRightRadius: 28, backgroundColor: colors.card }, sheetTitle: { color: colors.text, fontSize: 23, fontWeight: '900', marginBottom: 10 }, track: { minHeight: 54, flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingHorizontal: 14, borderRadius: 14, backgroundColor: colors.cardSecondary }, trackText: { color: colors.text, fontWeight: '800' },
});
