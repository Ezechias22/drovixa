import * as SecureStore from 'expo-secure-store';
import { create } from 'zustand';

const KEY = 'drovixa.playback.settings.v1';

type PlaybackState = {
  autoplay: boolean;
  hydrated: boolean;
  hydrate: () => Promise<void>;
  setAutoplay: (autoplay: boolean) => Promise<void>;
};

export const usePlaybackStore = create<PlaybackState>((set) => ({
  autoplay: true,
  hydrated: false,
  hydrate: async () => {
    const raw = await SecureStore.getItemAsync(KEY);
    set({ autoplay: raw === null ? true : raw === 'true', hydrated: true });
  },
  setAutoplay: async (autoplay) => {
    await SecureStore.setItemAsync(KEY, String(autoplay));
    set({ autoplay });
  },
}));
