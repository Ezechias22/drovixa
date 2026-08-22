import { apiClient } from '@/api/client';

import type { ApiEnvelope, PlaybackGrant, PlaybackTarget } from './types';

export function playbackRefreshInterval(grant: PlaybackGrant | undefined): number | false {
  if (!grant) return false;
  const expiresAt = Date.parse(grant.expires_at);
  if (!Number.isFinite(expiresAt)) return false;
  return Math.max(10_000, expiresAt - Date.now() - 60_000);
}

export async function authorizePlayback(input: {
  id: string;
  target: PlaybackTarget;
  clientDeviceId: string;
}): Promise<PlaybackGrant> {
  const path =
    input.target === 'movie'
      ? `/playback/movies/${input.id}/authorize`
      : `/playback/episodes/${input.id}/authorize`;
  const response = await apiClient.post<ApiEnvelope<PlaybackGrant>>(path, {
    client_device_id: input.clientDeviceId,
  });
  return response.data.data;
}

export async function syncWatchProgress(input: {
  playbackSessionId: string;
  positionSeconds: number;
  durationSeconds: number;
}): Promise<void> {
  await apiClient.post('/progress', {
    playback_session_id: input.playbackSessionId,
    position_seconds: input.positionSeconds,
    duration_seconds: input.durationSeconds,
  });
}
