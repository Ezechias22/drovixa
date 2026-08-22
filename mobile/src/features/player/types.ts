export type PlaybackTarget = 'episode' | 'movie';

export type SubtitleTrack = {
  id: string;
  language_code: string;
  label: string;
  format: 'vtt' | 'srt';
  url: string;
  is_default: boolean;
};

export type PlaybackGrant = {
  playback_session_id: string;
  content_type: 'series' | 'movie';
  content_id: string;
  episode_id: string | null;
  hls_url: string;
  dash_url: string;
  expires_at: string;
  duration_seconds: number | null;
  subtitles: SubtitleTrack[];
  progress_sync_interval_seconds: number;
};

export type ApiEnvelope<T> = { success: true; data: T; meta: Record<string, unknown> };
