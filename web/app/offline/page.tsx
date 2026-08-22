import Link from 'next/link';

export default function OfflinePage() {
  return (
    <main style={{ minHeight: '70vh', display: 'grid', placeItems: 'center', padding: '2rem' }}>
      <section style={{ maxWidth: 520, textAlign: 'center' }}>
        <div style={{ color: '#ff3d71', fontWeight: 900, letterSpacing: '.18em' }}>DROVIXA</div>
        <h1 style={{ fontSize: 'clamp(2rem, 8vw, 4rem)', marginBottom: '.75rem' }}>You’re offline</h1>
        <p style={{ color: '#9ca3af', lineHeight: 1.7 }}>
          Reconnect to continue streaming and synchronize your account.
        </p>
        <Link className="primary-button" href="/" style={{ marginTop: '1rem' }}>
          Try again
        </Link>
      </section>
    </main>
  );
}
