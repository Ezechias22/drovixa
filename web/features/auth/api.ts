import { apiClient } from '@/lib/api';
import type { ApiEnvelope, UserData } from '@/features/catalog/types';

type SessionResponse = { access_token: string; refresh_token: string; expires_in: number; user: UserData };
function device() { const key = 'drovixa.web.device'; let id = localStorage.getItem(key); if (!id) { id = crypto.randomUUID(); localStorage.setItem(key, id); } return { device_id: id, name: 'Drovixa Web', platform: 'web' }; }
export async function login(email: string, password: string) { return (await apiClient.post<ApiEnvelope<SessionResponse>>('/auth/login', { email, password, device: device() })).data.data; }
export async function register(name: string, email: string, password: string) { return (await apiClient.post<ApiEnvelope<SessionResponse>>('/auth/register', { name, email, password, device: device() })).data.data; }
export async function logout() { await apiClient.post('/auth/logout'); }
