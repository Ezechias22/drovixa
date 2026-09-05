import { apiClient } from '@/lib/api';

import type {
  ApiEnvelope,
  Checkout,
  CoinPackage,
  Subscription,
  SubscriptionPlan,
  Wallet,
} from './types';

export async function getWallet() {
  return (await apiClient.get<ApiEnvelope<Wallet>>('/wallet')).data.data;
}

export async function unlockEpisode(episodeId: string) {
  return (
    await apiClient.post<
      ApiEnvelope<{
        episode_id: string;
        unlocked: boolean;
        already_unlocked: boolean;
        wallet: Wallet;
      }>
    >(
      `/episodes/${episodeId}/unlock`,
      undefined,
      { headers: { 'Idempotency-Key': crypto.randomUUID() } },
    )
  ).data.data;
}

export async function getCoinPackages() {
  return (
    await apiClient.get<ApiEnvelope<CoinPackage[]>>('/coins/packages', {
      params: { platform: 'web' },
    })
  ).data.data;
}

export async function createCoinCheckout(productId: string) {
  return (
    await apiClient.post<ApiEnvelope<Checkout>>(
      '/coins/purchase',
      { product_id: productId },
      { headers: { 'Idempotency-Key': crypto.randomUUID() } },
    )
  ).data.data;
}

export async function getSubscriptionPlans() {
  return (await apiClient.get<ApiEnvelope<SubscriptionPlan[]>>('/subscriptions/plans')).data.data;
}

export async function getCurrentSubscription() {
  return (await apiClient.get<ApiEnvelope<Subscription | null>>('/subscriptions/current')).data
    .data;
}

export async function createSubscriptionCheckout(productId: string) {
  return (
    await apiClient.post<ApiEnvelope<Checkout>>(
      '/subscriptions/checkout',
      { product_id: productId },
      { headers: { 'Idempotency-Key': crypto.randomUUID() } },
    )
  ).data.data;
}

export async function cancelSubscription(reason?: string) {
  return (
    await apiClient.post<ApiEnvelope<Subscription>>('/subscriptions/cancel', { reason })
  ).data.data;
}
