'use client';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import type { ReactNode } from 'react';
import { useEffect } from 'react';
import { useQuery } from '@tanstack/react-query';
import { BellIcon, BookmarkIcon, CompassIcon, HomeIcon, PlayIcon, SearchIcon, UserIcon } from './icons';
import { Logo } from './logo';
import { useAuthStore } from '@/stores/auth-store';
import { getFeatureFlags } from '@/features/configuration/api';

const desktop = [{ href: '/', label: 'Home' }, { href: '/discover?type=series', label: 'Series' }, { href: '/discover?type=movie', label: 'Movies' }, { href: '/shorts', label: 'Shorts' }, { href: '/discover', label: 'Discover' }];
const mobile = [{ href: '/', label: 'Home', Icon: HomeIcon }, { href: '/discover', label: 'Discover', Icon: CompassIcon }, { href: '/shorts', label: 'Shorts', Icon: PlayIcon }, { href: '/library', label: 'My List', Icon: BookmarkIcon }, { href: '/profile', label: 'Profile', Icon: UserIcon }];
export function AppShell({ children }: { children: ReactNode }) {
  const path = usePathname(); const hydrate = useAuthStore((s) => s.hydrate); const user = useAuthStore((s) => s.user); const flags = useQuery({ queryKey: ['feature-flags'], queryFn: getFeatureFlags });
  useEffect(() => hydrate(), [hydrate]);
  if (path.startsWith('/watch/')) return children;
  const desktopItems = flags.data?.subscriptions_enabled?.enabled ? [...desktop, { href: '/premium', label: 'Premium' }] : desktop;
  return <div className="min-h-screen bg-[var(--background)] text-white"><header className="fixed inset-x-0 top-0 z-50 border-b border-white/[.06] bg-[#08090bdd] backdrop-blur-xl"><div className="mx-auto flex h-[72px] max-w-[1600px] items-center gap-8 px-5 md:px-8"><Logo /><nav className="hidden gap-7 lg:flex">{desktopItems.map((x) => <Link key={x.href} className="text-sm font-semibold text-white/65 hover:text-white" href={x.href}>{x.label}</Link>)}</nav><div className="ml-auto flex items-center gap-2"><Link className="icon-button" href="/search" aria-label="Search"><SearchIcon /></Link>{user && <Link className="icon-button" href="/notifications" aria-label="Notifications"><BellIcon /></Link>}<Link className="ml-1 hidden rounded-full bg-white px-4 py-2 text-sm font-bold text-black sm:block" href={user ? '/profile' : '/login'}>{user ? user.name.split(' ')[0] : 'Sign in'}</Link></div></div></header><main className="pb-24 pt-[72px] md:pb-8">{children}</main><nav className="fixed inset-x-0 bottom-0 z-50 grid grid-cols-5 border-t border-white/[.08] bg-[#0b0c0fee] px-2 pb-2 pt-2 md:hidden">{mobile.map(({ href, label, Icon }) => { const active = path === href || (href !== '/' && path.startsWith(href)); return <Link key={href} className={`flex min-h-14 flex-col items-center justify-center gap-1 text-[10px] font-semibold ${active ? 'text-[var(--accent)]' : 'text-[#8d929d]'}`} href={href}><Icon size={21} /><span>{label}</span></Link>; })}</nav></div>;
}
