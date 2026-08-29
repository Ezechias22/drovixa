import * as SecureStore from 'expo-secure-store';
import { create } from 'zustand';

const SETTINGS_KEY = 'drovixa.playback.settings.v1';
const PROGRESS_KEY = 'drovixa.playback.progress.v2';

export type LocalPlaybackProgress = {
  targetId: string;
  seriesId: string | null;
  episodeId: string | null;
  positionSeconds: number;
  durationSeconds: number;
  updatedAt: number;
};

type SavedPlaybackState = {
  progressByTarget: Record<string, LocalPlaybackProgress>;
  lastEpisodeBySeries: Record<string, string>;
};

type PlaybackState = SavedPlaybackState & {
  autoplay: boolean;
  hydrated: boolean;
  hydrate: () => Promise<void>;
  setAutoplay: (autoplay: boolean) => Promise<void>;
  rememberProgress: (progress: Omit<LocalPlaybackProgress, 'updatedAt'>) => Promise<void>;
  completeTarget: (targetId: string) => Promise<void>;
};

async function persist(state: SavedPlaybackState) {
  await SecureStore.setItemAsync(PROGRESS_KEY, JSON.stringify(state));
}

export const usePlaybackStore = create<PlaybackState>((set, get) => ({
  autoplay: true,
  hydrated: false,
  progressByTarget: {},
  lastEpisodeBySeries: {},
  hydrate: async () => {
    const [autoplayRaw, progressRaw] = await Promise.all([
      SecureStore.getItemAsync(SETTINGS_KEY),
      SecureStore.getItemAsync(PROGRESS_KEY),
    ]);
    let saved: SavedPlaybackState = { progressByTarget: {}, lastEpisodeBySeries: {} };
    if (progressRaw) {
      try {
        saved = { ...saved, ...(JSON.parse(progressRaw) as SavedPlaybackState) };
      } catch {
        await SecureStore.deleteItemAsync(PROGRESS_KEY);
      }
    }
    set({
      autoplay: autoplayRaw === null ? true : autoplayRaw === 'true',
      progressByTarget: saved.progressByTarget ?? {},
      lastEpisodeBySeries: saved.lastEpisodeBySeries ?? {},
      hydrated: true,
    });
  },
  setAutoplay: async (autoplay) => {
    await SecureStore.setItemAsync(SETTINGS_KEY, String(autoplay));
    set({ autoplay });
  },
  rememberProgress: async (progress) => {
    const current = get();
    const entry: LocalPlaybackProgress = { ...progress, updatedAt: Date.now() };
    const next: SavedPlaybackState = {
      progressByTarget: { ...current.progressByTarget, [progress.targetId]: entry },
      lastEpisodeBySeries: progress.seriesId && progress.episodeId
        ? { ...current.lastEpisodeBySeries, [progress.seriesId]: progress.episodeId }
        : current.lastEpisodeBySeries,
    };
    set(next);
    await persist(next);
  },
  completeTarget: async (targetId) => {
    const current = get();
    const nextProgress = { ...current.progressByTarget };
    delete nextProgress[targetId];
    const next = {
      progressByTarget: nextProgress,
      lastEpisodeBySeries: current.lastEpisodeBySeries,
    };
    set(next);
    await persist(next);
  },
}));
