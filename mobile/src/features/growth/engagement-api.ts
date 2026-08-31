import { Platform } from 'react-native';

import { apiClient } from '@/api/client';
import type { ApiEnvelope } from '@/features/catalog/types';

export type EngagementConfig = {
  premium: boolean;
  rewarded_ad: {
    enabled: boolean;
    coins_per_ad: number;
    daily_limit: number;
    watched_today: number;
    remaining_today: number;
    configured: boolean;
  };
  premium_offer: {
    enabled: boolean;
    max_per_session: number;
    max_per_day: number;
    first_delay_seconds: number;
    repeat_delay_seconds: number;
  };
};

export type RewardedAdSession = {
  id: string;
  user_id: string;
  custom_data: string;
  ad_unit_id: string;
  reward_coins: number;
  expires_at: string;
  status: string;
};

function mobilePlatform(): 'android' | 'ios' {
  return Platform.OS === 'ios' ? 'ios' : 'android';
}

export async function getEngagementConfig() {
  return (
    await apiClient.get<ApiEnvelope<EngagementConfig>>('/engagement/config', {
      params: { platform: mobilePlatform() },
    })
  ).data.data;
}

export async function createRewardedAdSession() {
  return (
    await apiClient.post<ApiEnvelope<RewardedAdSession>>('/rewards/ads/session', {
      platform: mobilePlatform(),
    })
  ).data.data;
}
