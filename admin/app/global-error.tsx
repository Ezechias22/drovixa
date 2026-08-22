'use client';

import * as Sentry from '@sentry/nextjs';
import { useEffect } from 'react';

export default function GlobalError({ error }: { error: Error & { digest?: string } }) {
  useEffect(() => {
    Sentry.captureException(error);
  }, [error]);

  return (
    <html lang="en">
      <body>
        <main style={{ margin: '12vh auto', maxWidth: 560, padding: 24, textAlign: 'center' }}>
          <p>Drovixa Admin</p>
          <h1>Dashboard unavailable</h1>
          <p>The incident was recorded. Reload the page or check platform health.</p>
          <button onClick={() => location.reload()}>Reload</button>
        </main>
      </body>
    </html>
  );
}
