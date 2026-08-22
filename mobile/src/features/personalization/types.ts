export type ViewerProfile = {
  id: string;
  name: string;
  avatar_key: string;
  is_kids: boolean;
  age_limit: number;
  language_code: string;
  autoplay_next: boolean;
  autoplay_previews: boolean;
  pin_protected: boolean;
  is_default: boolean;
  active: boolean;
};

export type DeviceSession = {
  id: string;
  device_id: string;
  name: string;
  platform: string;
  last_ip: string | null;
  last_seen_at: string;
  current: boolean;
};

export type RatingSummary = {
  content_id: string;
  profile_id: string;
  score: number | null;
  average: number | string;
  count: number;
};

export type DownloadGrant = {
  id: string;
  profile_id: string;
  content_id: string;
  episode_id: string | null;
  quality: string;
  status: string;
  expires_at: string;
  download_url: string;
  license_token: string;
};

export type OfflineDownload = {
  id: string;
  contentId: string;
  episodeId: string | null;
  title: string;
  posterUrl: string | null;
  localUri: string;
  expiresAt: string;
  quality: string;
  bytes: number;
};

export type ApiEnvelope<T> = { success: true; data: T; meta: Record<string, unknown> };
