import Link from 'next/link';

export default function PaymentCancelledPage() {
  return <div className="mx-auto grid min-h-[70vh] max-w-xl place-items-center px-5 text-center"><div><p className="text-5xl">◇</p><h1 className="mt-5 text-4xl font-black">Checkout cancelled</h1><p className="mt-3 text-[var(--muted)]">No charge was confirmed and your balance has not changed.</p><Link className="primary-button mt-7" href="/">Return to Drovixa</Link></div></div>;
}
