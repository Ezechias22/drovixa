'use client';

import { useQueryClient } from '@tanstack/react-query';
import Link from 'next/link';
import { useEffect } from 'react';

export default function PaymentSuccessPage() {
  const queryClient = useQueryClient();
  useEffect(() => {
    void queryClient.invalidateQueries({ queryKey: ['wallet'] });
    void queryClient.invalidateQueries({ queryKey: ['subscription-current'] });
  }, [queryClient]);
  return <div className="mx-auto grid min-h-[70vh] max-w-xl place-items-center px-5 text-center"><div><div className="mx-auto grid h-20 w-20 place-items-center rounded-full bg-green-400/15 text-4xl text-green-300">✓</div><h1 className="mt-6 text-4xl font-black">Payment received</h1><p className="mt-3 text-[var(--muted)]">Drovixa is confirming the provider webhook. Your wallet or membership will update automatically.</p><div className="mt-7 flex justify-center gap-3"><Link className="primary-button" href="/">Go home</Link><Link className="secondary-button" href="/coins">View wallet</Link></div></div></div>;
}
