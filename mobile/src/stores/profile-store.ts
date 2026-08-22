import * as SecureStore from 'expo-secure-store';
import { create } from 'zustand';

import type { ViewerProfile } from '@/features/personalization/types';

const KEY = 'drovixa.active-profile.v1';

type ProfileState = {
  activeProfile: ViewerProfile | null;
  hydrated: boolean;
  setActiveProfile: (profile: ViewerProfile | null) => Promise<void>;
  hydrate: () => Promise<void>;
};

export const useProfileStore = create<ProfileState>((set) => ({
  activeProfile: null,
  hydrated: false,
  setActiveProfile: async (profile) => {
    if (profile) await SecureStore.setItemAsync(KEY, JSON.stringify(profile));
    else await SecureStore.deleteItemAsync(KEY);
    set({ activeProfile: profile });
  },
  hydrate: async () => {
    try {
      const raw = await SecureStore.getItemAsync(KEY);
      set({ activeProfile: raw ? (JSON.parse(raw) as ViewerProfile) : null, hydrated: true });
    } catch {
      await SecureStore.deleteItemAsync(KEY);
      set({ activeProfile: null, hydrated: true });
    }
  },
}));
