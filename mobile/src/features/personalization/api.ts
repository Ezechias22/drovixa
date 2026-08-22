import { apiClient } from '@/api/client';

import type {
  ApiEnvelope,
  DeviceSession,
  RatingSummary,
  ViewerProfile,
} from './types';

export async function getProfiles(): Promise<ViewerProfile[]> {
  return (await apiClient.get<ApiEnvelope<ViewerProfile[]>>('/profiles')).data.data;
}

export async function createProfile(input: {
  name: string;
  is_kids: boolean;
  age_limit: number;
  language_code: string;
  pin?: string;
  avatar_key?: string;
}): Promise<ViewerProfile> {
  return (await apiClient.post<ApiEnvelope<ViewerProfile>>('/profiles', input)).data.data;
}

export async function verifyProfilePin(profileId: string, pin: string): Promise<boolean> {
  return (
    await apiClient.post<ApiEnvelope<{ valid: boolean }>>(
      `/profiles/${profileId}/verify-pin`,
      { pin },
    )
  ).data.data.valid;
}

export async function getDevices(): Promise<DeviceSession[]> {
  return (await apiClient.get<ApiEnvelope<DeviceSession[]>>('/users/me/devices')).data.data;
}

export async function removeDevice(id: string): Promise<void> {
  await apiClient.delete(`/users/me/devices/${id}`);
}

export async function getRating(contentId: string): Promise<RatingSummary> {
  return (await apiClient.get<ApiEnvelope<RatingSummary>>(`/ratings/${contentId}`)).data.data;
}

export async function setRating(contentId: string, score: number): Promise<RatingSummary> {
  return (
    await apiClient.put<ApiEnvelope<RatingSummary>>(`/ratings/${contentId}`, { score })
  ).data.data;
}

export async function registerCast(input: {
  playbackSessionId: string;
  targetDeviceId: string;
  targetDeviceName: string;
}): Promise<void> {
  await apiClient.post('/cast-sessions', {
    playback_session_id: input.playbackSessionId,
    target_device_id: input.targetDeviceId,
    target_device_name: input.targetDeviceName,
    target_type: 'chromecast',
  });
}
