import { create } from 'zustand';

import type { UserData } from '@/features/catalog/types';

type StoredSession = { accessToken: string; refreshToken: string; user: UserData };

type AuthState = {
  accessToken: string | null;
  refreshToken: string | null;
  user: UserData | null;
  hydrated: boolean;
  setSession: (session: StoredSession | null) => void;
  hydrate: () => void;
};

export const useAuthStore = create<AuthState>((set) => ({
  accessToken: null,
  refreshToken: null,
  user: null,
  hydrated: false,
  setSession: (session) => {
    if (typeof window !== 'undefined') {
      if (session) sessionStorage.setItem('drovixa.web.session', JSON.stringify(session));
      else sessionStorage.removeItem('drovixa.web.session');
    }
    set(session ? { ...session, hydrated: true } : { accessToken: null, refreshToken: null, user: null, hydrated: true });
  },
  hydrate: () => {
    if (typeof window === 'undefined') return;
    try {
      const raw = sessionStorage.getItem('drovixa.web.session');
      set(raw ? { ...(JSON.parse(raw) as StoredSession), hydrated: true } : { hydrated: true });
    } catch {
      sessionStorage.removeItem('drovixa.web.session');
      set({ accessToken: null, refreshToken: null, user: null, hydrated: true });
    }
  },
}));
