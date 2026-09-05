'use client';

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import axios from 'axios';
import Hls, { ErrorTypes } from 'hls.js';
import { useEffect, useRef, useState } from 'react';

import { useAuthStore } from '@/stores/auth-store';
import { getEpisode } from '@/features/catalog/api';
import { unlockEpisode } from '@/features/monetization/api';

import {
  authorizePlayback,
  getOrCreateWebDeviceId,
  playbackRefreshInterval,
  syncWatchProgress,
} from './api';
import type { PlaybackTarget } from './types';

type Props = { id: string; target: PlaybackTarget };
type PlayerFailure = { title: string; detail: string };

export function DrovixaWebPlayer({ id, target }: Props) {
  const queryClient = useQueryClient();
  const videoRef = useRef<HTMLVideoElement>(null);
  const hlsRef = useRef<Hls | null>(null);
  const syncInFlight = useRef(false);
  const lastSyncAt = useRef(0);
  const resumePosition = useRef(0);
  const shouldResumePlaying = useRef(true);
  const recoveryAttempts = useRef({ network: 0, media: 0 });
  const [deviceId, setDeviceId] = useState<string | null>(null);
  const [qualityLevels, setQualityLevels] = useState<Array<{ index: number; label: string }>>([]);
  const [quality, setQuality] = useState(-1);
  const [playerError, setPlayerError] = useState<PlayerFailure | null>(null);
  const isAuthenticated = useAuthStore((state) => Boolean(state.accessToken));

  useEffect(() => setDeviceId(getOrCreateWebDeviceId()), []);

  const grant = useQuery({
    queryKey: ['playback', target, id, deviceId],
    queryFn: () => authorizePlayback({ id, target, clientDeviceId: deviceId! }),
    enabled: Boolean(id && deviceId),
    retry: false,
    refetchInterval: (query) => playbackRefreshInterval(query.state.data),
  });
  const grantError = axios.isAxiosError(grant.error)
    ? grant.error.response?.data?.error
    : undefined;
  const needsCoinUnlock = target === 'episode' && grantError?.code === 'CONTENT_LOCKED';
  const lockedEpisode = useQuery({
    queryKey: ['episode', id],
    queryFn: () => getEpisode(id),
    enabled: needsCoinUnlock,
    retry: false,
  });
  const unlock = useMutation({
    mutationFn: () => unlockEpisode(id),
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ['wallet'] }),
        queryClient.invalidateQueries({ queryKey: ['episodes'] }),
        queryClient.invalidateQueries({ queryKey: ['episode', id] }),
      ]);
      await grant.refetch();
    },
  });

  useEffect(() => {
    const video = videoRef.current;
    const playback = grant.data;
    if (!video || !playback) return;
    recoveryAttempts.current = { network: 0, media: 0 };
    setPlayerError(null);
    const restorePlayback = () => {
      if (resumePosition.current > 0 && Number.isFinite(video.duration)) {
        video.currentTime = Math.min(resumePosition.current, video.duration);
      }
      if (shouldResumePlaying.current) void video.play().catch(() => undefined);
    };
    const markPlaying = () => setPlayerError(null);
    const markNativeError = () => {
      setPlayerError({
        title: 'Secure video could not be loaded',
        detail: 'Refresh the secure playback link and try again.',
      });
    };
    setQualityLevels([]);
    setQuality(-1);
    video.addEventListener('playing', markPlaying);
    if (video.canPlayType('application/vnd.apple.mpegurl')) {
      video.src = playback.hls_url;
      video.addEventListener('loadedmetadata', restorePlayback, { once: true });
      video.addEventListener('error', markNativeError);
      return () => {
        resumePosition.current = video.currentTime;
        shouldResumePlaying.current = !video.paused;
        video.removeEventListener('loadedmetadata', restorePlayback);
        video.removeEventListener('error', markNativeError);
        video.removeEventListener('playing', markPlaying);
        video.removeAttribute('src');
        video.load();
      };
    }
    if (!Hls.isSupported()) {
      setPlayerError({
        title: 'This browser cannot play HLS video',
        detail: 'Use a recent version of Chrome, Edge, Firefox or Safari.',
      });
      video.removeEventListener('playing', markPlaying);
      return;
    }
    const hls = new Hls({ enableWorker: true });
    hlsRef.current = hls;
    video.addEventListener('loadedmetadata', restorePlayback, { once: true });
    hls.loadSource(playback.hls_url);
    hls.attachMedia(video);
    hls.on(Hls.Events.MANIFEST_PARSED, () => {
      setPlayerError(null);
      const levels = hls.levels.map((level, index) => ({
        index,
        label: level.height ? `${level.height}p` : `${Math.round(level.bitrate / 1000)} kbps`,
      }));
      setQualityLevels(levels);
      restorePlayback();
    });
    hls.on(Hls.Events.ERROR, (_event, data) => {
      if (!data.fatal) return;

      if (data.type === ErrorTypes.NETWORK_ERROR && recoveryAttempts.current.network < 1) {
        recoveryAttempts.current.network += 1;
        window.setTimeout(() => {
          if (hlsRef.current === hls) hls.startLoad();
        }, 750);
        return;
      }

      if (data.type === ErrorTypes.MEDIA_ERROR && recoveryAttempts.current.media < 1) {
        recoveryAttempts.current.media += 1;
        hls.recoverMediaError();
        return;
      }

      const statusCode = data.response?.code;
      const rejectedSecureUrl = statusCode === 401 || statusCode === 403;
      setPlayerError({
        title: rejectedSecureUrl ? 'Mux rejected the secure playback link' : 'Video playback failed',
        detail: rejectedSecureUrl
          ? 'The playback token or Mux signing key must be refreshed.'
          : 'The video CDN could not be reached. Refresh the secure playback link and try again.',
      });
      hls.stopLoad();
    });
    return () => {
      resumePosition.current = video.currentTime;
      shouldResumePlaying.current = !video.paused;
      video.removeEventListener('loadedmetadata', restorePlayback);
      video.removeEventListener('playing', markPlaying);
      hlsRef.current = null;
      hls.destroy();
    };
  }, [grant.data]);

  useEffect(() => {
    const video = videoRef.current;
    const playback = grant.data;
    if (!video || !playback || !isAuthenticated) return;

    const sync = async (force = false) => {
      const now = Date.now();
      if (
        syncInFlight.current ||
        (!force && now - lastSyncAt.current < playback.progress_sync_interval_seconds * 1000)
      ) {
        return;
      }
      const duration = Math.round(playback.duration_seconds ?? video.duration);
      if (!Number.isFinite(duration) || duration < 1) return;
      lastSyncAt.current = now;
      syncInFlight.current = true;
      try {
        await syncWatchProgress({
          playbackSessionId: playback.playback_session_id,
          positionSeconds: Math.max(0, Math.round(video.currentTime)),
          durationSeconds: duration,
        });
      } finally {
        syncInFlight.current = false;
      }
    };
    const periodic = () => void sync();
    const final = () => void sync(true);
    video.addEventListener('timeupdate', periodic);
    video.addEventListener('pause', final);
    video.addEventListener('ended', final);
    window.addEventListener('pagehide', final);
    return () => {
      video.removeEventListener('timeupdate', periodic);
      video.removeEventListener('pause', final);
      video.removeEventListener('ended', final);
      window.removeEventListener('pagehide', final);
    };
  }, [grant.data, isAuthenticated]);

  const chooseQuality = (value: number) => {
    setQuality(value);
    if (hlsRef.current) hlsRef.current.currentLevel = value;
  };

  const retryPlayback = () => {
    setPlayerError(null);
    recoveryAttempts.current = { network: 0, media: 0 };
    void grant.refetch();
  };

  if (grant.isPending) {
    return <PlayerState title="Authorizing secure playback…" />;
  }
  if (needsCoinUnlock) {
    const unlockError = axios.isAxiosError(unlock.error)
      ? unlock.error.response?.data?.error
      : undefined;
    return (
      <div className="flex aspect-video w-full flex-col items-center justify-center rounded-2xl bg-[var(--card)] px-6 text-center">
        <p className="text-lg font-semibold text-white">Unlock this episode</p>
        <p className="mt-2 text-sm text-[var(--muted)]">
          {lockedEpisode.data
            ? `Use ${lockedEpisode.data.coin_price} coins to watch it permanently.`
            : 'Loading the episode price…'}
        </p>
        {unlockError && (
          <p className="mt-3 text-sm text-red-300">
            {unlockError.code === 'INSUFFICIENT_COINS'
              ? 'You do not have enough coins.'
              : (unlockError.message ?? 'The episode could not be unlocked.')}
          </p>
        )}
        <button
          type="button"
          className="mt-5 rounded-full bg-[var(--accent)] px-5 py-2.5 text-sm font-semibold text-white transition hover:brightness-110 disabled:cursor-not-allowed disabled:opacity-50"
          disabled={!lockedEpisode.data || unlock.isPending}
          onClick={() => unlock.mutate()}
        >
          {unlock.isPending
            ? 'Unlocking…'
            : `Unlock for ${lockedEpisode.data?.coin_price ?? '…'} coins`}
        </button>
      </div>
    );
  }
  if (grant.isError) {
    return <PlayerState title="Playback unavailable" detail={grantError?.message ?? 'Please try again later.'} />;
  }

  return (
    <section className="w-full" aria-label="Drovixa video player">
      <div className="relative aspect-video overflow-hidden rounded-2xl bg-black shadow-2xl">
        <video
          ref={videoRef}
          className="h-full w-full"
          controls
          crossOrigin="anonymous"
          playsInline
          preload="metadata"
        >
          {grant.data.subtitles
            .filter((subtitle) => subtitle.format === 'vtt')
            .map((subtitle) => (
              <track
                key={subtitle.id}
                kind="subtitles"
                src={subtitle.url}
                srcLang={subtitle.language_code}
                label={subtitle.label}
                default={subtitle.is_default}
              />
            ))}
        </video>
        {playerError && (
          <div className="absolute inset-0 flex flex-col items-center justify-center bg-black/85 px-6 text-center">
            <p className="text-lg font-semibold text-white">{playerError.title}</p>
            <p className="mt-2 max-w-lg text-sm text-[var(--muted)]">{playerError.detail}</p>
            <button
              type="button"
              className="mt-5 rounded-full bg-[var(--accent)] px-5 py-2.5 text-sm font-semibold text-white transition hover:brightness-110"
              onClick={retryPlayback}
            >
              Retry secure playback
            </button>
          </div>
        )}
      </div>
      {qualityLevels.length > 0 && (
        <label className="mt-4 flex items-center justify-end gap-3 text-sm text-[var(--muted)]">
          Quality
          <select
            className="rounded-lg bg-[var(--card)] px-3 py-2 text-white outline-none ring-[var(--accent)] focus:ring-2"
            value={quality}
            onChange={(event) => chooseQuality(Number(event.target.value))}
          >
            <option value={-1}>Auto</option>
            {qualityLevels.map((level) => (
              <option key={level.index} value={level.index}>
                {level.label}
              </option>
            ))}
          </select>
        </label>
      )}
    </section>
  );
}

function PlayerState({ title, detail }: { title: string; detail?: string }) {
  return (
    <div className="flex aspect-video w-full flex-col items-center justify-center rounded-2xl bg-[var(--card)] px-6 text-center">
      <p className="text-lg font-semibold text-white">{title}</p>
      {detail && <p className="mt-2 text-sm text-[var(--muted)]">{detail}</p>}
    </div>
  );
}
