'use client';

import { useMutation, useQuery } from '@tanstack/react-query';
import axios from 'axios';
import Link from 'next/link';

import { EmptyState, ErrorState, PageLoader } from '@/components/states';
import { useAuthStore } from '@/stores/auth-store';

import { createCoinCheckout, getCoinPackages, getWallet } from './api';
import type { CoinPackage } from './types';

function money(value: string | number, currency: string) {
  return new Intl.NumberFormat(undefined, { style: 'currency', currency }).format(Number(value));
}

function errorCode(error: unknown) {
  return axios.isAxiosError(error) ? (error.response?.data?.error?.code as string | undefined) : undefined;
}

export function CoinsExperience() {
  const token = useAuthStore((state) => state.accessToken);
  const hydrated = useAuthStore((state) => state.hydrated);
  const wallet = useQuery({ queryKey: ['wallet'], queryFn: getWallet, enabled: Boolean(token) });
  const packages = useQuery({ queryKey: ['coin-packages', 'web'], queryFn: getCoinPackages });
  const checkout = useMutation({
    mutationFn: (item: CoinPackage) => createCoinCheckout(item.id),
    onSuccess: (result) => {
      if (result.checkout_url) window.location.assign(result.checkout_url);
    },
  });

  if (!hydrated) return <PageLoader />;
  if (!token) {
    return (
      <div className="mx-auto grid min-h-[70vh] max-w-xl place-items-center px-5 text-center">
        <div>
          <p className="text-5xl">✦</p>
          <h1 className="mt-4 text-4xl font-black">Your Drovixa wallet</h1>
          <p className="mt-3 text-[var(--muted)]">Sign in to buy coins and unlock episodes.</p>
          <Link className="primary-button mt-7" href="/login?next=/coins">Sign in</Link>
        </div>
      </div>
    );
  }

  const disabled = errorCode(packages.error) === 'COINS_DISABLED';
  return (
    <div className="mx-auto max-w-6xl px-5 py-10 md:px-8 md:py-16">
      <section className="overflow-hidden rounded-[2rem] bg-[radial-gradient(circle_at_top_right,rgba(255,61,113,.28),transparent_42%),linear-gradient(135deg,#171120,#101217)] p-7 md:p-11">
        <p className="text-xs font-black tracking-[.25em] text-pink-300">DROVIXA WALLET</p>
        <div className="mt-6 flex flex-col justify-between gap-8 md:flex-row md:items-end">
          <div>
            <p className="text-sm text-white/55">Available balance</p>
            <p className="mt-2 text-6xl font-black tracking-tight md:text-7xl">
              {wallet.data?.total_balance ?? '—'}
              <span className="ml-3 text-xl font-bold text-pink-300">coins</span>
            </p>
          </div>
          {wallet.data && (
            <div className="grid grid-cols-2 gap-3 text-sm">
              <div className="rounded-2xl bg-white/[.07] px-5 py-4">
                <span className="block text-white/45">Purchased</span>
                <strong className="mt-1 block text-xl">{wallet.data.coin_balance}</strong>
              </div>
              <div className="rounded-2xl bg-white/[.07] px-5 py-4">
                <span className="block text-white/45">Bonus</span>
                <strong className="mt-1 block text-xl">{wallet.data.bonus_coin_balance}</strong>
              </div>
            </div>
          )}
        </div>
      </section>

      <div className="mt-11">
        <p className="text-xs font-black tracking-[.2em] text-[var(--accent)]">TOP UP SECURELY</p>
        <h1 className="mt-2 text-3xl font-black md:text-5xl">Choose your coin pack</h1>
        <p className="mt-3 max-w-2xl text-[var(--muted)]">
          Payments are confirmed by the server before your balance changes.
        </p>
      </div>

      {(wallet.isPending || packages.isPending) && <PageLoader />}
      {disabled && (
        <div className="mt-8"><EmptyState title="Coins are not available yet" body="This module is currently disabled by Drovixa administration." /></div>
      )}
      {packages.isError && !disabled && <ErrorState retry={() => void packages.refetch()} />}
      {packages.data && !packages.data.length && (
        <div className="mt-8"><EmptyState title="No coin packs yet" body="New packages will appear here when they are published." /></div>
      )}
      {packages.data && packages.data.length > 0 && (
        <div className="mt-8 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {packages.data.map((item) => (
            <article
              key={item.id}
              className={`relative rounded-3xl p-6 ${item.featured ? 'bg-gradient-to-br from-fuchsia-500/25 to-[var(--card)] ring-1 ring-pink-400/40' : 'bg-[var(--card)]'}`}
            >
              {item.featured && <span className="absolute right-5 top-5 rounded-full bg-white px-3 py-1 text-[10px] font-black text-black">BEST VALUE</span>}
              <p className="text-sm font-bold text-white/55">{item.name}</p>
              <p className="mt-4 text-4xl font-black">{item.coins.toLocaleString()}</p>
              <p className="mt-1 text-sm text-[var(--muted)]">coins</p>
              {item.bonus_coins > 0 && <p className="mt-4 font-bold text-pink-300">+ {item.bonus_coins.toLocaleString()} bonus</p>}
              <button
                type="button"
                disabled={checkout.isPending}
                onClick={() => checkout.mutate(item)}
                className="mt-7 w-full rounded-full bg-white py-3.5 font-black text-black disabled:opacity-50"
              >
                {checkout.isPending ? 'Opening checkout…' : money(item.price, item.currency)}
              </button>
            </article>
          ))}
        </div>
      )}
      {checkout.isError && <p className="mt-5 text-sm font-semibold text-red-300">Payment checkout could not be opened. Please try again.</p>}
    </div>
  );
}
