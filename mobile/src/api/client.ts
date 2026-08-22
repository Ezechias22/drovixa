import axios from 'axios';

import { useAuthStore } from '@/stores/auth-store';
import { useProfileStore } from '@/stores/profile-store';

const baseURL = process.env.EXPO_PUBLIC_API_URL;

if (!baseURL) console.warn('EXPO_PUBLIC_API_URL is not configured.');

export const apiClient = axios.create({
  baseURL: baseURL ?? 'http://localhost:8000/api/v1',
  timeout: 15_000,
  headers: { Accept: 'application/json' },
});

apiClient.interceptors.request.use((config) => {
  const accessToken = useAuthStore.getState().session?.accessToken;
  if (accessToken) config.headers.Authorization = `Bearer ${accessToken}`;
  const profileId = useProfileStore.getState().activeProfile?.id;
  if (profileId) config.headers['X-Drovixa-Profile-ID'] = profileId;
  return config;
});

let refreshPromise: Promise<string | null> | null = null;
async function refreshAccessToken() { const state = useAuthStore.getState(); if (!state.session) return null; try { const response = await axios.post(`${apiClient.defaults.baseURL}/auth/refresh`, { refresh_token: state.session.refreshToken }); const data = response.data.data; await state.setSession({ accessToken: data.access_token, refreshToken: data.refresh_token, user: data.user }); return data.access_token as string; } catch { await state.setSession(null); return null; } }
apiClient.interceptors.response.use((r)=>r,async(error)=>{const config=error.config as (typeof error.config&{_drovixaRetried?:boolean})|undefined;if(error.response?.status!==401||!config||config._drovixaRetried)return Promise.reject(error);config._drovixaRetried=true;refreshPromise??=refreshAccessToken().finally(()=>{refreshPromise=null});const token=await refreshPromise;if(!token)return Promise.reject(error);config.headers.Authorization=`Bearer ${token}`;return apiClient.request(config)});
