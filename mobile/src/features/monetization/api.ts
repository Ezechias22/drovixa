import * as Crypto from 'expo-crypto';

import { apiClient } from '@/api/client';

import type {
  ApiEnvelope,
  CoinPackage,
  Subscription,
  SubscriptionPlan,
  Wallet,
} from './types';

export async function getWallet() {
  return (await apiClient.get<ApiEnvelope<Wallet>>('/wallet')).data.data;
}

export async function getCoinPackages(platform: 'android' | 'ios') {
  return (
    await apiClient.get<ApiEnvelope<CoinPackage[]>>('/coins/packages', { params: { platform } })
  ).data.data;
}

export async function getSubscriptionPlans() {
  return (await apiClient.get<ApiEnvelope<SubscriptionPlan[]>>('/subscriptions/plans')).data.data;
}

export async function getCurrentSubscription() {
  return (await apiClient.get<ApiEnvelope<Subscription | null>>('/subscriptions/current')).data
    .data;
}

export async function cancelSubscription() {
  return (
    await apiClient.post<ApiEnvelope<Subscription>>('/subscriptions/cancel', {
      reason: 'Cancelled from mobile app',
    })
  ).data.data;
}

export type StoreReceipt = {
  platform: 'android' | 'ios';
  productType: 'coins' | 'subscription';
  productId: string;
  storeProductId: string;
  transactionId: string;
  receipt: string;
};

export async function verifyStoreReceipt(purchase: StoreReceipt) {
  const response = await apiClient.post(
    '/iap/verify',
    {
      platform: purchase.platform,
      product_type: purchase.productType,
      product_id: purchase.productId,
      store_product_id: purchase.storeProductId,
      transaction_id: purchase.transactionId,
      receipt: purchase.receipt,
    },
    { headers: { 'Idempotency-Key': Crypto.randomUUID() } },
  );
  return response.data.data as { payment_id: string; status: string; verified: boolean };
}
