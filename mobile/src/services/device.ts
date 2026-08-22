import { randomUUID } from 'expo-crypto';
import * as SecureStore from 'expo-secure-store';

const DEVICE_KEY = 'drovixa.device_id';

export async function getOrCreateDeviceId(): Promise<string> {
  const existing = await SecureStore.getItemAsync(DEVICE_KEY);
  if (existing) return existing;
  const created = `mobile-${randomUUID()}`;
  await SecureStore.setItemAsync(DEVICE_KEY, created);
  return created;
}
