import { apiClient } from '@/api/client';
import type { ApiEnvelope } from '@/features/catalog/types';
import { getOrCreateDeviceId } from '@/services/device';

export type GrowthConfig = {
  google_login: boolean;
  apple_login: boolean;
  daily_rewards: number[];
  referral: { inviter_coins: number; invitee_coins: number };
  watch_party_max_members: number;
};

export type DailyReward = {
  claimed_today: boolean;
  claim: { date: string; streak_day: number; coins: number } | null;
  next_streak_day: number;
  next_coins: number;
  calendar: number[];
};

export type ReferralSummary = {
  code: string;
  share_url: string;
  invited: number;
  earned_coins: number;
  applied: boolean;
  inviter_reward: number;
  invitee_reward: number;
};

export type DrovixaAd = {
  id: string;
  delivery_id: string;
  session_key: string;
  format: string;
  placement: string;
  headline: string;
  body: string | null;
  media_url: string | null;
  click_url: string | null;
  sponsor: string | null;
  reward_coins: number;
};

export type WatchParty = {
  id: string;
  invite_code: string;
  share_url: string;
  title: string;
  content_id: string;
  episode_id: string | null;
  host_id: string;
  is_host: boolean;
  status: 'lobby' | 'playing' | 'paused' | 'ended';
  position_seconds: number;
  paused: boolean;
  max_members: number;
  members: { user_id: string; name: string; role: string; status: string }[];
  messages: { id: string; user_id: string; name: string; message: string; created_at: string }[];
};

export async function getGrowthConfig() {
  return (await apiClient.get<ApiEnvelope<GrowthConfig>>('/growth/config')).data.data;
}

export async function getDailyReward() {
  return (await apiClient.get<ApiEnvelope<DailyReward>>('/rewards/daily')).data.data;
}

export async function claimDailyReward() {
  return (await apiClient.post<ApiEnvelope<DailyReward>>('/rewards/daily/claim')).data.data;
}

export async function getReferralSummary() {
  return (await apiClient.get<ApiEnvelope<ReferralSummary>>('/referrals/me')).data.data;
}

export async function applyReferral(code: string) {
  return (
    await apiClient.post<ApiEnvelope<ReferralSummary>>('/referrals/apply', { code })
  ).data.data;
}

export async function getNextAd(placement = 'home_feed') {
  const deviceId = await getOrCreateDeviceId();
  return (
    await apiClient.get<ApiEnvelope<DrovixaAd | null>>('/ads/next', {
      params: { placement },
      headers: { 'X-Drovixa-Device-ID': deviceId },
    })
  ).data.data;
}

export async function trackAd(ad: DrovixaAd, eventType: 'impression' | 'click' | 'completed') {
  return apiClient.post('/ads/events', {
    delivery_id: ad.delivery_id,
    session_key: ad.session_key,
    event_type: eventType,
  });
}

export async function createWatchParty(input: {
  contentId: string;
  episodeId: string | null;
  title: string;
}) {
  return (
    await apiClient.post<ApiEnvelope<WatchParty>>('/watch-parties', {
      content_id: input.contentId,
      episode_id: input.episodeId,
      title: input.title,
      max_members: 10,
    })
  ).data.data;
}

export async function joinWatchParty(code: string) {
  return (
    await apiClient.post<ApiEnvelope<WatchParty>>(`/watch-parties/${code}/join`, {})
  ).data.data;
}

export async function getWatchParty(code: string) {
  return (await apiClient.get<ApiEnvelope<WatchParty>>(`/watch-parties/${code}`)).data.data;
}

export async function updateWatchParty(
  code: string,
  input: { position_seconds: number; paused: boolean; status: WatchParty['status'] },
) {
  return (
    await apiClient.patch<ApiEnvelope<WatchParty>>(`/watch-parties/${code}/state`, input)
  ).data.data;
}

export async function sendWatchPartyMessage(code: string, message: string) {
  await apiClient.post(`/watch-parties/${code}/messages`, { message });
}
