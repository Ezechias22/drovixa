import axios from 'axios';

import { useAuthStore } from '@/stores/auth-store';

export const apiClient = axios.create({
  baseURL: process.env.NEXT_PUBLIC_API_URL ?? '/api/drovixa',
  timeout: 15_000,
  withCredentials: true,
  headers: { Accept: 'application/json' },
});

apiClient.interceptors.request.use((config) => {
  const accessToken = useAuthStore.getState().accessToken;
  if (accessToken) config.headers.Authorization = `Bearer ${accessToken}`;
  if (typeof window !== 'undefined') {
    const profileId = sessionStorage.getItem('drovixa.web.profile');
    if (profileId) config.headers['X-Drovixa-Profile-ID'] = profileId;
  }
  return config;
});

let refreshPromise: Promise<string | null> | null = null;

async function refreshAccessToken() {
  const state = useAuthStore.getState();
  if (!state.refreshToken) return null;
  try {
    const response = await axios.post(`${apiClient.defaults.baseURL}/auth/refresh`, { refresh_token: state.refreshToken });
    const data = response.data.data;
    state.setSession({ accessToken: data.access_token, refreshToken: data.refresh_token, user: data.user });
    return data.access_token as string;
  } catch {
    state.setSession(null);
    return null;
  }
}

apiClient.interceptors.response.use((response) => response, async (error) => {
  const config = error.config as (typeof error.config & { _drovixaRetried?: boolean }) | undefined;
  if (error.response?.status !== 401 || !config || config._drovixaRetried) return Promise.reject(error);
  config._drovixaRetried = true;
  refreshPromise ??= refreshAccessToken().finally(() => { refreshPromise = null; });
  const token = await refreshPromise;
  if (!token) return Promise.reject(error);
  config.headers.Authorization = `Bearer ${token}`;
  return apiClient.request(config);
});
