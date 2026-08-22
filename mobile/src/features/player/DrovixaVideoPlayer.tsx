import { useEvent, useEventListener } from 'expo';
import { useVideoPlayer, VideoView } from 'expo-video';
import { useCallback, useRef } from 'react';
import { ActivityIndicator, Pressable, StyleSheet, Text, View } from 'react-native';

import { useAuthStore } from '@/stores/auth-store';

import { syncWatchProgress } from './api';
import type { PlaybackGrant } from './types';

type Props = { grant: PlaybackGrant };

export function DrovixaVideoPlayer({ grant }: Props) {
  const isAuthenticated = useAuthStore((state) => Boolean(state.session?.accessToken));
  const syncInFlight = useRef(false);
  const resumePosition = useRef(0);
  const shouldPlay = useRef(true);
  const player = useVideoPlayer(
    { uri: grant.hls_url, contentType: 'hls' },
    (instance) => {
      instance.timeUpdateEventInterval = grant.progress_sync_interval_seconds;
      if (resumePosition.current > 0) instance.currentTime = resumePosition.current;
      if (shouldPlay.current) instance.play();
    },
  );
  const { status } = useEvent(player, 'statusChange', { status: player.status });
  const { isPlaying } = useEvent(player, 'playingChange', { isPlaying: player.playing });

  const sync = useCallback(
    async (position: number) => {
      if (!isAuthenticated || syncInFlight.current) return;
      const duration = Math.round(grant.duration_seconds ?? player.duration);
      if (!Number.isFinite(duration) || duration < 1) return;
      syncInFlight.current = true;
      try {
        await syncWatchProgress({
          playbackSessionId: grant.playback_session_id,
          positionSeconds: Math.max(0, Math.round(position)),
          durationSeconds: duration,
        });
      } finally {
        syncInFlight.current = false;
      }
    },
    [grant, isAuthenticated, player],
  );

  useEventListener(player, 'timeUpdate', ({ currentTime }) => {
    resumePosition.current = currentTime;
    void sync(currentTime);
  });
  useEventListener(player, 'playingChange', ({ isPlaying: playing }) => {
    shouldPlay.current = playing;
  });
  useEventListener(player, 'playToEnd', () => {
    void sync(grant.duration_seconds ?? player.duration);
  });

  return (
    <View style={styles.container}>
      <VideoView
        player={player}
        style={styles.video}
        nativeControls
        contentFit="contain"
        fullscreenOptions={{ enable: true }}
        allowsPictureInPicture
        startsPictureInPictureAutomatically
      />
      {status === 'loading' && (
        <View style={styles.overlay}>
          <ActivityIndicator color="#FFFFFF" size="large" />
        </View>
      )}
      {status === 'error' && (
        <View style={styles.overlay}>
          <Text style={styles.error}>Video playback failed. Please try again.</Text>
        </View>
      )}
      <View style={styles.quickControls}>
        <Pressable
          accessibilityRole="button"
          accessibilityLabel="Go back ten seconds"
          style={styles.button}
          onPress={() => player.seekBy(-10)}
        >
          <Text style={styles.buttonText}>−10s</Text>
        </Pressable>
        <Pressable
          accessibilityRole="button"
          accessibilityLabel={isPlaying ? 'Pause video' : 'Play video'}
          style={styles.primaryButton}
          onPress={() => (isPlaying ? player.pause() : player.play())}
        >
          <Text style={styles.buttonText}>{isPlaying ? 'Pause' : 'Play'}</Text>
        </Pressable>
        <Pressable
          accessibilityRole="button"
          accessibilityLabel="Go forward ten seconds"
          style={styles.button}
          onPress={() => player.seekBy(10)}
        >
          <Text style={styles.buttonText}>+10s</Text>
        </Pressable>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { width: '100%', aspectRatio: 16 / 9, backgroundColor: '#000000' },
  video: { width: '100%', height: '100%' },
  overlay: {
    ...StyleSheet.absoluteFill,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: 'rgba(0,0,0,0.55)',
    padding: 24,
  },
  error: { color: '#FFFFFF', textAlign: 'center' },
  quickControls: {
    position: 'absolute',
    left: 16,
    right: 16,
    bottom: 12,
    flexDirection: 'row',
    justifyContent: 'center',
    gap: 10,
  },
  button: {
    backgroundColor: '#16181D',
    borderRadius: 20,
    paddingHorizontal: 14,
    paddingVertical: 8,
  },
  primaryButton: {
    backgroundColor: '#FF3D71',
    borderRadius: 20,
    paddingHorizontal: 20,
    paddingVertical: 8,
  },
  buttonText: { color: '#FFFFFF', fontSize: 13, fontWeight: '700' },
});
