'use client';

import * as Sentry from '@sentry/nextjs';
import { useEffect } from 'react';

export default function GlobalError({ error }: { error: Error & { digest?: string } }) {
  useEffect(() => {
    Sentry.captureException(error);
  }, [error]);

  return (
    <html lang="en">
      <body className="grid min-h-screen place-items-center bg-black p-6 text-white">
        <main className="max-w-lg text-center">
          <p className="text-sm font-bold uppercase tracking-[0.2em] text-pink-400">Drovixa</p>
          <h1 className="mt-3 text-4xl font-black">Something went wrong</h1>
          <p className="mt-3 text-white/60">Please reload the page. The incident was recorded.</p>
          <button className="mt-7 rounded-full bg-white px-7 py-3 font-bold text-black" onClick={() => location.reload()}>
            Reload
          </button>
        </main>
      </body>
    </html>
  );
}
