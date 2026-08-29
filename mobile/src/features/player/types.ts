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
  width: number | null;
  height: number | null;
  aspect_ratio: string | null;
  orientation: 'vertical' | 'horizontal' | 'mixed';
  title: string;
  content_title: string;
  poster_url: string | null;
  profile_id: string | null;
  autoplay_next: boolean;
  resume_position_seconds: number;
  previous_episode_id: string | null;
  next_episode_id: string | null;
  is_favorite: boolean;
  subtitles: SubtitleTrack[];
  progress_sync_interval_seconds: number;
};

export type ApiEnvelope<T> = { success: true; data: T; meta: Record<string, unknown> };
