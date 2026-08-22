'use client';

import { useQuery } from '@tanstack/react-query';
import axios from 'axios';
import Hls from 'hls.js';
import { useEffect, useRef, useState } from 'react';

import { useAuthStore } from '@/stores/auth-store';

import {
  authorizePlayback,
  getOrCreateWebDeviceId,
  playbackRefreshInterval,
  syncWatchProgress,
} from './api';
import type { PlaybackTarget } from './types';

type Props = { id: string; target: PlaybackTarget };

export function DrovixaWebPlayer({ id, target }: Props) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const hlsRef = useRef<Hls | null>(null);
  const syncInFlight = useRef(false);
  const lastSyncAt = useRef(0);
  const resumePosition = useRef(0);
  const shouldResumePlaying = useRef(true);
  const [deviceId, setDeviceId] = useState<string | null>(null);
  const [qualityLevels, setQualityLevels] = useState<Array<{ index: number; label: string }>>([]);
  const [quality, setQuality] = useState(-1);
  const isAuthenticated = useAuthStore((state) => Boolean(state.accessToken));

  useEffect(() => setDeviceId(getOrCreateWebDeviceId()), []);

  const grant = useQuery({
    queryKey: ['playback', target, id, deviceId],
    queryFn: () => authorizePlayback({ id, target, clientDeviceId: deviceId! }),
    enabled: Boolean(id && deviceId),
    retry: false,
    refetchInterval: (query) => playbackRefreshInterval(query.state.data),
  });

  useEffect(() => {
    const video = videoRef.current;
    const playback = grant.data;
    if (!video || !playback) return;
    const restorePlayback = () => {
      if (resumePosition.current > 0 && Number.isFinite(video.duration)) {
        video.currentTime = Math.min(resumePosition.current, video.duration);
      }
      if (shouldResumePlaying.current) void video.play().catch(() => undefined);
    };
    setQualityLevels([]);
    setQuality(-1);
    if (video.canPlayType('application/vnd.apple.mpegurl')) {
      video.src = playback.hls_url;
      video.addEventListener('loadedmetadata', restorePlayback, { once: true });
      return () => {
        resumePosition.current = video.currentTime;
        shouldResumePlaying.current = !video.paused;
        video.removeEventListener('loadedmetadata', restorePlayback);
        video.removeAttribute('src');
        video.load();
      };
    }
    if (!Hls.isSupported()) return;
    const hls = new Hls({ enableWorker: true });
    hlsRef.current = hls;
    video.addEventListener('loadedmetadata', restorePlayback, { once: true });
    hls.loadSource(playback.hls_url);
    hls.attachMedia(video);
    hls.on(Hls.Events.MANIFEST_PARSED, () => {
      const levels = hls.levels.map((level, index) => ({
        index,
        label: level.height ? `${level.height}p` : `${Math.round(level.bitrate / 1000)} kbps`,
      }));
      setQualityLevels(levels);
      restorePlayback();
    });
    return () => {
      resumePosition.current = video.currentTime;
      shouldResumePlaying.current = !video.paused;
      video.removeEventListener('loadedmetadata', restorePlayback);
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

  if (grant.isPending) {
    return <PlayerState title="Authorizing secure playback…" />;
  }
  if (grant.isError) {
    const data = axios.isAxiosError(grant.error) ? grant.error.response?.data : null;
    const message = data?.error?.message;
    return <PlayerState title="Playback unavailable" detail={message ?? 'Please try again later.'} />;
  }

  return (
    <section className="w-full" aria-label="Drovixa video player">
      <div className="relative aspect-video overflow-hidden rounded-2xl bg-black shadow-2xl">
        <video ref={videoRef} className="h-full w-full" controls playsInline preload="metadata">
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
