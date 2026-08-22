'use client';

import { useMutation, useQuery } from '@tanstack/react-query';
import Image from 'next/image';
import Link from 'next/link';
import { usePathname, useRouter } from 'next/navigation';
import { useEffect, useMemo, useState } from 'react';

import { sessionRequest } from '@/lib/api';
import type { AdminUser } from '@/lib/types';

const groups = [
  {
    label: 'Overview',
    items: [
      ['/dashboard', 'Dashboard', '◆'],
      ['/analytics', 'Analytics', '⌁'],
      ['/experience', 'Profiles & devices', '◈'],
    ],
  },
  {
    label: 'Platform',
    items: [
      ['/content', 'Content', '▶'],
      ['/homepage', 'Homepage', '▦'],
      ['/users', 'Users', '◉'],
      ['/comments', 'Comments', '◌'],
      ['/reports', 'Reports', '!'],
    ],
  },
  {
    label: 'Revenue',
    items: [
      ['/payments', 'Payments', '$'],
      ['/subscriptions', 'Subscriptions', '◇'],
      ['/coins', 'Coins', '●'],
    ],
  },
  {
    label: 'Operations',
    items: [
      ['/notifications', 'Notifications', '✦'],
      ['/feature-flags', 'Feature flags', '⌘'],
      ['/settings', 'Settings', '⚙'],
      ['/audit-logs', 'Audit logs', '≡'],
    ],
  },
] as const;

const pageNames = new Map<string, string>(
  groups.flatMap((group) => group.items.map((item) => [item[0], item[1]])),
);

export function AdminShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const session = useQuery({
    queryKey: ['admin-session'],
    queryFn: () => sessionRequest<AdminUser>('/me'),
    retry: false,
  });
  useEffect(() => {
    if (session.isError) router.replace('/login');
  }, [router, session.isError]);
  useEffect(() => setOpen(false), [pathname]);
  const logout = useMutation({
    mutationFn: () => sessionRequest<{ logged_out: boolean }>('/logout', { method: 'POST' }),
    onSettled: () => router.replace('/login'),
  });
  const title = useMemo(
    () => pageNames.get(pathname) ?? 'Drovixa Administration',
    [pathname],
  );

  if (session.isLoading)
    return <div className="skeleton" style={{ width: '100%', height: '100vh', borderRadius: 0 }} />;
  if (!session.data) return null;

  return (
    <div className="admin-shell">
      <aside className={`sidebar ${open ? 'open' : ''}`}>
        <Link className="brand" href="/dashboard">
          <Image
            className="brand-logo"
            src="/brand/drovixa-logo.png"
            alt="Drovixa"
            width={42}
            height={42}
            priority
          />
          <span className="brand-copy">
            <strong>DROVIXA</strong>
            <small>Control center</small>
          </span>
        </Link>
        <nav className="nav-list" aria-label="Admin navigation">
          {groups.map((group) => (
            <div key={group.label}>
              <div className="nav-group-label">{group.label}</div>
              {group.items.map(([href, label, icon]) => (
                <Link
                  key={href}
                  className={`nav-link ${pathname === href ? 'active' : ''}`}
                  href={href}
                >
                  <span className="nav-icon">{icon}</span>
                  <span>{label}</span>
                </Link>
              ))}
            </div>
          ))}
        </nav>
        <div className="sidebar-user">
          <strong>{session.data.name}</strong>
          <span>{session.data.email}</span>
          <span>{session.data.roles.join(' · ')}</span>
          <button className="signout" onClick={() => logout.mutate()} disabled={logout.isPending}>
            {logout.isPending ? 'Signing out…' : 'Sign out securely'}
          </button>
        </div>
      </aside>
      <main className="main-area">
        <header className="topbar">
          <div style={{ display: 'flex', gap: 12, alignItems: 'center' }}>
            <button className="mobile-menu" onClick={() => setOpen((value) => !value)}>
              ☰
            </button>
            <h1>{title}</h1>
          </div>
          <span className="topbar-meta">Phase 10 · Profiles, offline & casting</span>
        </header>
        {children}
      </main>
    </div>
  );
}
