import { useEvent, useEventListener } from 'expo';
import { useVideoPlayer, VideoView } from 'expo-video';
import { type ReactNode, useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { ActivityIndicator, Pressable, StyleSheet, Text, View } from 'react-native';
import { MediaStreamType, useCastDevice, useRemoteMediaClient } from 'react-native-google-cast';

import { registerCast } from '@/features/personalization/api';
import { useI18n } from '@/i18n';
import { useAuthStore } from '@/stores/auth-store';
import { usePlaybackStore } from '@/stores/playback-store';

import { syncWatchProgress } from './api';
import { parseSubtitleFile, type SubtitleCue } from './subtitle-cues';
import type { PlaybackGrant, SubtitleTrack } from './types';

type Props = {
  grant: PlaybackGrant;
  selectedSubtitle: SubtitleTrack | null;
  overlayActions?: ReactNode;
  onEnded?: () => void;
  onRetry?: () => void;
};

function videoRatio(grant: PlaybackGrant) {
  if (grant.width && grant.height) return Math.min(2.4, Math.max(0.5, grant.width / grant.height));
  if (grant.aspect_ratio?.includes(':')) {
    const [width, height] = grant.aspect_ratio.split(':').map(Number);
    if (width > 0 && height > 0) return Math.min(2.4, Math.max(0.5, width / height));
  }
  return grant.orientation === 'vertical' ? 9 / 16 : 16 / 9;
}

export function DrovixaVideoPlayer({ grant, selectedSubtitle, overlayActions, onEnded, onRetry }: Props) {
  const { t } = useI18n();
  const autoplay = usePlaybackStore((state) => state.autoplay);
  const rememberProgress = usePlaybackStore((state) => state.rememberProgress);
  const completeTarget = usePlaybackStore((state) => state.completeTarget);
  const targetId = grant.episode_id ?? grant.content_id;
  const isAuthenticated = useAuthStore((state) => Boolean(state.session?.accessToken));
  const syncInFlight = useRef(false);
  const localPersistedAt = useRef(0);
  const serverPersistedAt = useRef(0);
  const resumePosition = useRef(Math.max(
    grant.resume_position_seconds ?? 0,
    usePlaybackStore.getState().progressByTarget[targetId]?.positionSeconds ?? 0,
  ));
  const shouldPlay = useRef(autoplay);
  const castClient = useRemoteMediaClient();
  const castDevice = useCastDevice();
  const castLoaded = useRef<string | null>(null);
  const [cues, setCues] = useState<SubtitleCue[]>([]);
  const [subtitleText, setSubtitleText] = useState('');
  const [actionsVisible, setActionsVisible] = useState(false);
  const actionTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const ratio = useMemo(() => videoRatio(grant), [grant]);
  const player = useVideoPlayer(null, (instance) => {
    instance.timeUpdateEventInterval = 1;
    instance.allowsExternalPlayback = true;
  });
  const { status, error } = useEvent(player, 'statusChange', { status: player.status });

  const revealActions = useCallback(() => {
    setActionsVisible(true);
    if (actionTimer.current) clearTimeout(actionTimer.current);
    actionTimer.current = setTimeout(() => setActionsVisible(false), 3_500);
  }, []);

  useEffect(() => () => {
    if (actionTimer.current) clearTimeout(actionTimer.current);
  }, []);

  useEffect(() => {
    resumePosition.current = Math.max(
      grant.resume_position_seconds ?? 0,
      usePlaybackStore.getState().progressByTarget[targetId]?.positionSeconds ?? 0,
    );
    shouldPlay.current = autoplay;
    let active = true;
    const load = async () => {
      await player.replaceAsync({ uri: grant.hls_url, contentType: 'hls' });
      if (!active) return;
      if (resumePosition.current > 1) player.currentTime = resumePosition.current;
      if (shouldPlay.current) player.play();
    };
    void load();
    return () => {
      active = false;
    };
  }, [autoplay, grant.hls_url, grant.resume_position_seconds, player, targetId]);

  useEffect(() => {
    let active = true;
    setCues([]);
    setSubtitleText('');
    if (!selectedSubtitle) return () => { active = false; };
    void fetch(selectedSubtitle.url)
      .then((response) => {
        if (!response.ok) throw new Error(`Subtitle request failed (${response.status}).`);
        return response.text();
      })
      .then((raw) => { if (active) setCues(parseSubtitleFile(raw)); })
      .catch(() => { if (active) setCues([]); });
    return () => { active = false; };
  }, [selectedSubtitle]);

  useEffect(() => {
    if (!castClient || !castDevice || castLoaded.current === grant.playback_session_id) return;
    castLoaded.current = grant.playback_session_id;
    player.pause();
    void castClient.loadMedia({
      autoplay: shouldPlay.current,
      startTime: Math.max(0, resumePosition.current),
      mediaInfo: {
        contentUrl: grant.hls_url,
        contentType: 'application/x-mpegURL',
        streamType: MediaStreamType.BUFFERED,
        streamDuration: grant.duration_seconds ?? undefined,
        metadata: {
          type: grant.content_type === 'movie' ? 'movie' : 'tvShow',
          title: grant.title,
          images: grant.poster_url ? [{ url: grant.poster_url }] : [],
        },
      },
    });
    void registerCast({
      playbackSessionId: grant.playback_session_id,
      targetDeviceId: castDevice.deviceId,
      targetDeviceName: castDevice.friendlyName,
    });
  }, [castClient, castDevice, grant, player]);

  const sync = useCallback(async (position: number, forceServer = false) => {
    const duration = Math.round(grant.duration_seconds ?? player.duration);
    if (!Number.isFinite(duration) || duration < 1) return;
    const normalizedPosition = Math.max(0, Math.min(duration, Math.round(position)));
    await rememberProgress({
      targetId,
      seriesId: grant.content_type === 'series' ? grant.content_id : null,
      episodeId: grant.episode_id,
      positionSeconds: normalizedPosition,
      durationSeconds: duration,
    });
    const serverInterval = Math.max(5, grant.progress_sync_interval_seconds);
    if (!isAuthenticated || syncInFlight.current || (!forceServer && Math.abs(normalizedPosition - serverPersistedAt.current) < serverInterval)) return;
    syncInFlight.current = true;
    try {
      await syncWatchProgress({
        playbackSessionId: grant.playback_session_id,
        positionSeconds: normalizedPosition,
        durationSeconds: duration,
      });
      serverPersistedAt.current = normalizedPosition;
    } finally {
      syncInFlight.current = false;
    }
  }, [grant, isAuthenticated, player, rememberProgress, targetId]);

  useEventListener(player, 'timeUpdate', ({ currentTime }) => {
    resumePosition.current = currentTime;
    const cue = cues.find((item) => currentTime >= item.start && currentTime < item.end);
    setSubtitleText(cue?.text ?? '');
    const currentSecond = Math.floor(currentTime);
    if (Math.abs(currentSecond - localPersistedAt.current) >= 3) {
      localPersistedAt.current = currentSecond;
      void sync(currentTime);
    }
  });
  useEventListener(player, 'playingChange', ({ isPlaying }) => {
    shouldPlay.current = isPlaying;
  });
  useEventListener(player, 'playToEnd', () => {
    void sync(grant.duration_seconds ?? player.duration, true).finally(async () => {
      await completeTarget(targetId);
      onEnded?.();
    });
  });

  return (
    <View onTouchStart={revealActions} style={[styles.container, { aspectRatio: ratio }]}>
      <VideoView
        player={player}
        style={styles.video}
        nativeControls
        contentFit="contain"
        fullscreenOptions={{
          enable: true,
          orientation: grant.orientation === 'vertical' ? 'portrait' : 'landscape',
        }}
        buttonOptions={{ showSubtitles: false }}
        allowsPictureInPicture
        startsPictureInPictureAutomatically
      />
      {actionsVisible && overlayActions ? <View pointerEvents="box-none" style={styles.viewerActions}>{overlayActions}</View> : null}
      {subtitleText ? <View pointerEvents="none" style={styles.subtitleWrap}><Text style={styles.subtitle}>{subtitleText}</Text></View> : null}
      {status === 'loading' ? <View pointerEvents="none" style={styles.overlay}><ActivityIndicator color="#FFFFFF" size="large" /></View> : null}
      {status === 'error' ? (
        <View style={styles.overlay}>
          <Text style={styles.error}>{t('player.failed')}</Text>
          <Text numberOfLines={3} style={styles.errorDetail}>{error?.message ?? t('player.refresh')}</Text>
          {onRetry ? <Pressable onPress={onRetry} style={styles.retryButton}><Text style={styles.buttonText}>{t('player.retry')}</Text></Pressable> : null}
        </View>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  container: { width: '100%', maxHeight: 760, backgroundColor: '#000000' },
  video: { width: '100%', height: '100%' },
  overlay: {
    position: 'absolute', left: 0, right: 0, top: 0, bottom: 0,
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
    backgroundColor: 'rgba(0,0,0,0.56)',
    padding: 24,
  },
  subtitleWrap: { position: 'absolute', left: 20, right: 20, bottom: 55, alignItems: 'center' },
  viewerActions: { position: 'absolute', left: 0, right: 0, top: 0, bottom: 0 },
  subtitle: { color: '#fff', fontSize: 18, lineHeight: 24, textAlign: 'center', fontWeight: '800', backgroundColor: '#000c', paddingHorizontal: 10, paddingVertical: 5, borderRadius: 6 },
  error: { color: '#FFFFFF', textAlign: 'center', fontWeight: '800' },
  errorDetail: { color: '#C9CDD5', fontSize: 12, lineHeight: 18, textAlign: 'center' },
  retryButton: { marginTop: 8, borderRadius: 20, backgroundColor: '#FF3D71', paddingHorizontal: 18, paddingVertical: 10 },
  buttonText: { color: '#FFFFFF', fontSize: 13, fontWeight: '800' },
});
