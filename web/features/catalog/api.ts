import { apiClient } from '@/lib/api';
import type { ApiEnvelope, ContentCardData, ContentDetail, EpisodeData, HomePayload, NotificationData, ShortData } from './types';

export async function getHome() { return (await apiClient.get<ApiEnvelope<HomePayload>>('/home')).data.data; }
export async function getDiscover(params: Record<string, string | number | boolean | undefined>) { return (await apiClient.get<ApiEnvelope<ContentCardData[]>>('/discover', { params })).data; }
export async function getGenres() { return (await apiClient.get<ApiEnvelope<Array<{ id: string; name: string; slug: string }>>>('/genres', { params: { limit: 100 } })).data.data; }
export async function searchContent(query: string) { return (await apiClient.get<ApiEnvelope<ContentCardData[]>>('/search', { params: { q: query } })).data.data; }
export async function getTrendingSearches() { return (await apiClient.get<ApiEnvelope<string[]>>('/search/trending')).data.data; }
export async function getContentDetail(type: 'series' | 'movie', slug: string) { return (await apiClient.get<ApiEnvelope<ContentDetail>>(`/${type === 'series' ? 'series' : 'movies'}/${slug}`)).data.data; }
export async function getEpisodes(seriesId: string) { return (await apiClient.get<ApiEnvelope<EpisodeData[]>>(`/series/${seriesId}/episodes`, { params: { limit: 100 } })).data.data; }
export async function getEpisode(episodeId: string) { return (await apiClient.get<ApiEnvelope<EpisodeData>>(`/episodes/${episodeId}`)).data.data; }
export async function getShorts() { return (await apiClient.get<ApiEnvelope<ShortData[]>>('/shorts', { params: { limit: 20 } })).data.data; }
export async function getFavorites() { return (await apiClient.get<ApiEnvelope<ContentCardData[]>>('/favorites')).data.data; }
export async function toggleFavorite(contentId: string, saved: boolean) { if (saved) await apiClient.delete(`/favorites/${contentId}`); else await apiClient.post(`/favorites/${contentId}`); }
export async function getNotifications() { const response = await apiClient.get<ApiEnvelope<NotificationData[]>>('/notifications'); return { items: response.data.data, unread: Number(response.data.meta.unread ?? 0) }; }
export async function readNotification(id: string) { await apiClient.patch(`/notifications/${id}/read`); }
