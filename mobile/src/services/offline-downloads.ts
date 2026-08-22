import * as FileSystem from 'expo-file-system/legacy';
import * as SecureStore from 'expo-secure-store';

import { apiClient } from '@/api/client';
import type {
  ApiEnvelope,
  DownloadGrant,
  OfflineDownload,
} from '@/features/personalization/types';

const DIRECTORY = `${FileSystem.documentDirectory}drovixa-downloads/`;
const INDEX = `${DIRECTORY}index.json`;

async function readIndex(): Promise<OfflineDownload[]> {
  const info = await FileSystem.getInfoAsync(INDEX);
  if (!info.exists) return [];
  try {
    return JSON.parse(await FileSystem.readAsStringAsync(INDEX)) as OfflineDownload[];
  } catch {
    return [];
  }
}

async function writeIndex(items: OfflineDownload[]) {
  await FileSystem.makeDirectoryAsync(DIRECTORY, { intermediates: true });
  await FileSystem.writeAsStringAsync(INDEX, JSON.stringify(items));
}

export async function getOfflineDownloads(): Promise<OfflineDownload[]> {
  const items = await readIndex();
  const checked = await Promise.all(
    items.map(async (item) => ({ item, exists: (await FileSystem.getInfoAsync(item.localUri)).exists })),
  );
  const valid = checked.filter(({ exists }) => exists).map(({ item }) => item);
  if (valid.length !== items.length) await writeIndex(valid);
  return valid;
}

export async function downloadForOffline(input: {
  id: string;
  target: 'episode' | 'movie';
  title: string;
  posterUrl: string | null;
}): Promise<OfflineDownload> {
  const path =
    input.target === 'movie'
      ? `/downloads/movies/${input.id}/authorize`
      : `/downloads/episodes/${input.id}/authorize`;
  const grant = (
    await apiClient.post<ApiEnvelope<DownloadGrant>>(path, { quality: '720p' })
  ).data.data;
  await FileSystem.makeDirectoryAsync(DIRECTORY, { intermediates: true });
  const localUri = `${DIRECTORY}${grant.id}.mp4`;
  await apiClient.patch(`/downloads/${grant.id}`, { status: 'downloading', bytes_downloaded: 0 });
  try {
    const result = await FileSystem.downloadAsync(grant.download_url, localUri);
    const info = await FileSystem.getInfoAsync(result.uri);
    const bytes = info.exists && 'size' in info ? info.size : 0;
    const item: OfflineDownload = {
      id: grant.id,
      contentId: grant.content_id,
      episodeId: grant.episode_id,
      title: input.title,
      posterUrl: input.posterUrl,
      localUri: result.uri,
      expiresAt: grant.expires_at,
      quality: grant.quality,
      bytes,
    };
    await SecureStore.setItemAsync(`drovixa.download.${grant.id}`, grant.license_token);
    const items = (await readIndex()).filter((entry) => entry.id !== item.id);
    await writeIndex([item, ...items]);
    await apiClient.patch(`/downloads/${grant.id}`, {
      status: 'ready',
      bytes_downloaded: bytes,
    });
    return item;
  } catch (error) {
    await apiClient.patch(`/downloads/${grant.id}`, { status: 'failed', bytes_downloaded: 0 });
    throw error;
  }
}

export async function verifyOfflineDownload(item: OfflineDownload): Promise<boolean> {
  if (Date.parse(item.expiresAt) <= Date.now()) return false;
  const token = await SecureStore.getItemAsync(`drovixa.download.${item.id}`);
  if (!token) return false;
  try {
    const response = await apiClient.post<ApiEnvelope<{ valid: boolean }>>(
      `/downloads/${item.id}/verify`,
      {},
      { headers: { 'X-Drovixa-Download-License': token } },
    );
    return response.data.data.valid;
  } catch {
    // A valid, unexpired token in encrypted device storage keeps true offline playback working.
    return true;
  }
}

export async function removeOfflineDownload(item: OfflineDownload): Promise<void> {
  const info = await FileSystem.getInfoAsync(item.localUri);
  if (info.exists) await FileSystem.deleteAsync(item.localUri, { idempotent: true });
  await SecureStore.deleteItemAsync(`drovixa.download.${item.id}`);
  await writeIndex((await readIndex()).filter((entry) => entry.id !== item.id));
  try {
    await apiClient.patch(`/downloads/${item.id}`, {
      status: 'deleted',
      bytes_downloaded: item.bytes,
    });
  } catch {
    // Local removal must still succeed while the device is temporarily offline.
  }
}
