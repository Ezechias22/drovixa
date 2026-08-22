import { useEvent, useEventListener } from 'expo';
import { useVideoPlayer, VideoAirPlayButton, VideoView } from 'expo-video';
import { useCallback, useEffect, useRef, useState } from 'react';
import { ActivityIndicator, Platform, Pressable, StyleSheet, Text, View } from 'react-native';
import { CastButton, MediaStreamType, useCastDevice, useRemoteMediaClient } from 'react-native-google-cast';

import { registerCast } from '@/features/personalization/api';
import { useAuthStore } from '@/stores/auth-store';

import { syncWatchProgress } from './api';
import type { PlaybackGrant } from './types';

type Props = { grant: PlaybackGrant };

export function DrovixaVideoPlayer({ grant }: Props) {
  const isAuthenticated = useAuthStore((state) => Boolean(state.session?.accessToken));
  const syncInFlight = useRef(false);
  const resumePosition = useRef(0);
  const shouldPlay = useRef(true);
  const castClient = useRemoteMediaClient();
  const castDevice = useCastDevice();
  const castLoaded = useRef<string | null>(null);
  const [speed, setSpeed] = useState(1);
  const player = useVideoPlayer(
    { uri: grant.hls_url, contentType: 'hls' },
    (instance) => {
      instance.timeUpdateEventInterval = grant.progress_sync_interval_seconds;
      instance.allowsExternalPlayback = true;
      if (resumePosition.current > 0) instance.currentTime = resumePosition.current;
      if (shouldPlay.current) instance.play();
    },
  );
  const { status } = useEvent(player, 'statusChange', { status: player.status });
  const { isPlaying } = useEvent(player, 'playingChange', { isPlaying: player.playing });

  useEffect(() => {
    if (!castClient || !castDevice || castLoaded.current === grant.playback_session_id) return;
    castLoaded.current = grant.playback_session_id;
    player.pause();
    void castClient.loadMedia({
      autoplay: true,
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

  const cycleSpeed = () => {
    const speeds = [0.5, 1, 1.25, 1.5, 2];
    const next = speeds[(speeds.indexOf(speed) + 1) % speeds.length];
    setSpeed(next);
    player.playbackRate = next;
    if (castClient) void castClient.setPlaybackRate(next);
  };

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
        <CastButton accessibilityLabel="Cast to TV" style={styles.routeButton} tintColor="#FFFFFF" />
        {Platform.OS === 'ios' ? <VideoAirPlayButton style={styles.routeButton} tint="#FFFFFF" activeTint="#FF3D71" /> : null}
        <Pressable
          accessibilityRole="button"
          accessibilityLabel="Go back ten seconds"
          style={styles.button}
          onPress={() => player.seekBy(-10)}
        >
          <Text style={styles.buttonText}>−10s</Text>
        </Pressable>
        <Pressable accessibilityRole="button" accessibilityLabel="Playback speed" style={styles.button} onPress={cycleSpeed}>
          <Text style={styles.buttonText}>{speed}×</Text>
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
  routeButton: { width: 38, height: 38 },
});
