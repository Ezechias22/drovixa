import * as SecureStore from 'expo-secure-store';
import { create } from 'zustand';

const KEY = 'drovixa.subtitle.settings.v1';

type SubtitleSettings = {
  enabled: boolean;
  preferredLanguage: string;
};

type SubtitleState = SubtitleSettings & {
  hydrated: boolean;
  hydrate: () => Promise<void>;
  update: (input: Partial<SubtitleSettings>) => Promise<void>;
};

export const useSubtitleStore = create<SubtitleState>((set, get) => ({
  enabled: true,
  preferredLanguage: 'ht',
  hydrated: false,
  hydrate: async () => {
    const raw = await SecureStore.getItemAsync(KEY);
    if (raw) {
      try {
        set({ ...(JSON.parse(raw) as SubtitleSettings), hydrated: true });
        return;
      } catch {
        await SecureStore.deleteItemAsync(KEY);
      }
    }
    set({ hydrated: true });
  },
  update: async (input) => {
    const next = {
      enabled: input.enabled ?? get().enabled,
      preferredLanguage: input.preferredLanguage ?? get().preferredLanguage,
    };
    set(next);
    await SecureStore.setItemAsync(KEY, JSON.stringify(next));
  },
}));
