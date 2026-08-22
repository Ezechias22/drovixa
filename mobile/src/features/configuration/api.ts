import { apiClient } from '@/api/client';

type Flag = { enabled: boolean; rollout_percentage: number; rules: Record<string, unknown> };

export async function getFeatureFlags() {
  return (
    await apiClient.get<{ success: true; data: Record<string, Flag> }>('/feature-flags')
  ).data.data;
}
