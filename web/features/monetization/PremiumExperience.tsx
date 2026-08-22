'use client';

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import axios from 'axios';
import Link from 'next/link';

import { EmptyState, ErrorState, PageLoader } from '@/components/states';
import { useAuthStore } from '@/stores/auth-store';

import {
  cancelSubscription,
  createSubscriptionCheckout,
  getCurrentSubscription,
  getSubscriptionPlans,
} from './api';
import type { SubscriptionPlan } from './types';

const benefitLabels: Record<string, string> = {
  no_ads: 'No interruptions',
  premium_content: 'Premium Originals',
  offline_download: 'Offline downloads',
  hd: 'HD streaming',
  full_hd: 'Full HD streaming',
  early_access: 'Early access',
  bonus_coins: 'Bonus coins',
  exclusive_content: 'Exclusive episodes',
  device_limit: 'Registered devices',
};

function money(value: string | number, currency: string) {
  return new Intl.NumberFormat(undefined, { style: 'currency', currency }).format(Number(value));
}

function errorCode(error: unknown) {
  return axios.isAxiosError(error) ? (error.response?.data?.error?.code as string | undefined) : undefined;
}

function benefits(plan: SubscriptionPlan) {
  return Object.entries(plan.benefits)
    .filter(([, value]) => Boolean(value))
    .map(([key, value]) => `${benefitLabels[key] ?? key.replaceAll('_', ' ')}${typeof value === 'number' ? `: ${value}` : ''}`);
}

export function PremiumExperience() {
  const token = useAuthStore((state) => state.accessToken);
  const hydrated = useAuthStore((state) => state.hydrated);
  const queryClient = useQueryClient();
  const plans = useQuery({ queryKey: ['subscription-plans'], queryFn: getSubscriptionPlans });
  const current = useQuery({ queryKey: ['subscription-current'], queryFn: getCurrentSubscription, enabled: Boolean(token) });
  const checkout = useMutation({
    mutationFn: (plan: SubscriptionPlan) => createSubscriptionCheckout(plan.id),
    onSuccess: (result) => {
      if (result.checkout_url) window.location.assign(result.checkout_url);
    },
  });
  const cancel = useMutation({
    mutationFn: () => cancelSubscription('Cancelled by user'),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: ['subscription-current'] }),
  });

  if (!hydrated) return <PageLoader />;
  const disabled = errorCode(plans.error) === 'SUBSCRIPTIONS_DISABLED';
  return (
    <div className="mx-auto max-w-7xl px-5 py-10 md:px-8 md:py-16">
      <div className="mx-auto max-w-3xl text-center">
        <p className="text-xs font-black tracking-[.28em] text-pink-300">DROVIXA PREMIUM</p>
        <h1 className="mt-4 text-5xl font-black tracking-tight md:text-7xl">Stories without limits.</h1>
        <p className="mx-auto mt-5 max-w-2xl text-lg text-[var(--muted)]">Premium benefits remain configurable by Drovixa administration, so every plan displays exactly what it includes.</p>
      </div>

      {current.data && (
        <section className="mx-auto mt-10 max-w-3xl rounded-3xl bg-gradient-to-r from-fuchsia-500/20 to-purple-500/10 p-6 ring-1 ring-pink-400/30 md:p-8">
          <div className="flex flex-col justify-between gap-5 sm:flex-row sm:items-center">
            <div>
              <p className="text-xs font-black tracking-[.2em] text-pink-300">ACTIVE MEMBERSHIP</p>
              <h2 className="mt-2 text-2xl font-black">{current.data.plan.name}</h2>
              <p className="mt-1 text-sm text-white/55">Renews through {new Date(current.data.current_period_end).toLocaleDateString()}</p>
            </div>
            {!current.data.cancel_at_period_end ? (
              <button className="secondary-button" disabled={cancel.isPending} onClick={() => cancel.mutate()}>{cancel.isPending ? 'Updating…' : 'Cancel renewal'}</button>
            ) : <span className="rounded-full bg-white/10 px-4 py-2 text-sm font-bold">Ends this period</span>}
          </div>
        </section>
      )}

      {plans.isPending && <PageLoader />}
      {disabled && <div className="mt-10"><EmptyState title="Premium is coming soon" body="Subscriptions are currently disabled by Drovixa administration." /></div>}
      {plans.isError && !disabled && <ErrorState retry={() => void plans.refetch()} />}
      {plans.data && !plans.data.length && <div className="mt-10"><EmptyState title="No plans published" body="Premium plans will appear here when they are ready." /></div>}
      {plans.data && plans.data.length > 0 && (
        <div className="mt-12 grid gap-5 md:grid-cols-2 xl:grid-cols-3">
          {plans.data.map((plan) => (
            <article key={plan.id} className={`flex min-h-[430px] flex-col rounded-[2rem] p-7 ${plan.featured ? 'bg-gradient-to-b from-fuchsia-500/25 to-[var(--card)] ring-1 ring-pink-400/45' : 'bg-[var(--card)]'}`}>
              <div className="flex items-center justify-between gap-4"><h2 className="text-2xl font-black">{plan.name}</h2>{plan.featured && <span className="rounded-full bg-pink-300 px-3 py-1 text-[10px] font-black text-black">RECOMMENDED</span>}</div>
              <p className="mt-6 text-4xl font-black">{money(plan.price, plan.currency)} <span className="text-sm font-semibold text-white/45">/ {plan.interval}</span></p>
              {plan.trial_days > 0 && <p className="mt-2 text-sm font-bold text-pink-300">{plan.trial_days}-day trial</p>}
              <ul className="mt-7 space-y-3 text-sm text-white/75">{benefits(plan).map((item) => <li key={item} className="flex gap-3"><span className="text-pink-300">✓</span>{item}</li>)}</ul>
              {token ? <button disabled={checkout.isPending || Boolean(current.data)} onClick={() => checkout.mutate(plan)} className="mt-auto rounded-full bg-white py-3.5 font-black text-black disabled:cursor-not-allowed disabled:opacity-40">{current.data ? 'Membership active' : checkout.isPending ? 'Opening checkout…' : 'Choose plan'}</button> : <Link href="/login?next=/premium" className="primary-button mt-auto">Sign in to continue</Link>}
            </article>
          ))}
        </div>
      )}
      {(checkout.isError || cancel.isError) && <p className="mt-6 text-center text-sm font-semibold text-red-300">We could not complete that request. Please try again.</p>}
    </div>
  );
}
