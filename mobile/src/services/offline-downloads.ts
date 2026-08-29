import * as FileSystem from 'expo-file-system/legacy';
import * as SecureStore from 'expo-secure-store';
import axios from 'axios';

import { apiClient } from '@/api/client';
import type {
  ApiEnvelope,
  DownloadGrant,
  OfflineDownload,
} from '@/features/personalization/types';

const DIRECTORY = `${FileSystem.documentDirectory}drovixa-downloads/`;
const INDEX = `${DIRECTORY}index.json`;
const PREPARATION_ATTEMPTS = 36;
const PREPARATION_DELAY_MS = 5_000;

export type DownloadProgress =
  | { phase: 'preparing'; percent: number }
  | { phase: 'downloading'; percent: number }
  | { phase: 'saving'; percent: 100 };

function delay(milliseconds: number) {
  return new Promise((resolve) => setTimeout(resolve, milliseconds));
}

function apiErrorCode(error: unknown): string | null {
  if (!axios.isAxiosError(error)) return null;
  return error.response?.data?.error?.code ?? null;
}

async function authorizeWithPreparationRetry(
  path: string,
  onProgress?: (progress: DownloadProgress) => void,
): Promise<DownloadGrant> {
  for (let attempt = 0; attempt < PREPARATION_ATTEMPTS; attempt += 1) {
    try {
      return (
        await apiClient.post<ApiEnvelope<DownloadGrant>>(path, { quality: '720p' })
      ).data.data;
    } catch (error) {
      if (apiErrorCode(error) !== 'DOWNLOAD_PREPARING' || attempt === PREPARATION_ATTEMPTS - 1) {
        throw error;
      }
      onProgress?.({
        phase: 'preparing',
        percent: Math.min(95, Math.round(((attempt + 1) / PREPARATION_ATTEMPTS) * 100)),
      });
      await delay(PREPARATION_DELAY_MS);
    }
  }
  throw new Error('The offline video could not be prepared.');
}

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
  onProgress?: (progress: DownloadProgress) => void;
}): Promise<OfflineDownload> {
  const path =
    input.target === 'movie'
      ? `/downloads/movies/${input.id}/authorize`
      : `/downloads/episodes/${input.id}/authorize`;
  input.onProgress?.({ phase: 'preparing', percent: 0 });
  const grant = await authorizeWithPreparationRetry(path, input.onProgress);
  await FileSystem.makeDirectoryAsync(DIRECTORY, { intermediates: true });
  const localUri = `${DIRECTORY}${grant.id}.mp4`;
  const temporaryUri = `${localUri}.part`;
  await FileSystem.deleteAsync(temporaryUri, { idempotent: true });
  await apiClient.patch(`/downloads/${grant.id}`, { status: 'downloading', bytes_downloaded: 0 }).catch(() => undefined);
  try {
    const resumable = FileSystem.createDownloadResumable(
      grant.download_url,
      temporaryUri,
      {},
      ({ totalBytesWritten, totalBytesExpectedToWrite }) => {
        const percent = totalBytesExpectedToWrite > 0
          ? Math.min(99, Math.round((totalBytesWritten / totalBytesExpectedToWrite) * 100))
          : 0;
        input.onProgress?.({ phase: 'downloading', percent });
      },
    );
    const result = await resumable.downloadAsync();
    if (!result?.uri) throw new Error('The video download did not produce a local file.');
    const partialInfo = await FileSystem.getInfoAsync(result.uri);
    const partialBytes = partialInfo.exists && 'size' in partialInfo ? partialInfo.size : 0;
    if (partialBytes < 1) throw new Error('The downloaded video file is empty.');
    await FileSystem.deleteAsync(localUri, { idempotent: true });
    await FileSystem.moveAsync({ from: result.uri, to: localUri });
    const info = await FileSystem.getInfoAsync(localUri);
    const bytes = info.exists && 'size' in info ? info.size : 0;
    const item: OfflineDownload = {
      id: grant.id,
      contentId: grant.content_id,
      episodeId: grant.episode_id,
      title: input.title,
      posterUrl: input.posterUrl,
      localUri,
      expiresAt: grant.expires_at,
      quality: grant.quality,
      bytes,
    };
    await SecureStore.setItemAsync(`drovixa.download.${grant.id}`, grant.license_token);
    input.onProgress?.({ phase: 'saving', percent: 100 });
    const items = (await readIndex()).filter((entry) => entry.id !== item.id);
    await writeIndex([item, ...items]);
    void apiClient.patch(`/downloads/${grant.id}`, {
      status: 'ready',
      bytes_downloaded: bytes,
    }, { timeout: 10_000 }).catch(() => undefined);
    return item;
  } catch (error) {
    await FileSystem.deleteAsync(temporaryUri, { idempotent: true });
    void apiClient.patch(`/downloads/${grant.id}`, { status: 'failed', bytes_downloaded: 0 }, { timeout: 10_000 }).catch(() => undefined);
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
