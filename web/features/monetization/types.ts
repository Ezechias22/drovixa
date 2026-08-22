export type Wallet = {
  user_id: string;
  coin_balance: number;
  bonus_coin_balance: number;
  total_balance: number;
  updated_at: string;
};

export type CoinPackage = {
  id: string;
  name: string;
  coins: number;
  bonus_coins: number;
  price: string | number;
  currency: string;
  platform: 'web' | 'android' | 'ios';
  store_product_id?: string | null;
  featured: boolean;
};

export type SubscriptionPlan = {
  id: string;
  name: string;
  slug: string;
  interval: 'monthly' | 'quarterly' | 'annual';
  price: string | number;
  currency: string;
  featured: boolean;
  trial_days: number;
  benefits: Record<string, boolean | number | string>;
};

export type Subscription = {
  id: string;
  plan: SubscriptionPlan;
  provider: string;
  status: string;
  starts_at: string;
  current_period_end: string;
  cancel_at_period_end: boolean;
  cancelled_at?: string | null;
};

export type Checkout = {
  payment_id: string;
  status: string;
  checkout_url: string | null;
  provider: string;
};

export type ApiEnvelope<T> = {
  success: boolean;
  data: T;
  meta: Record<string, unknown>;
};
