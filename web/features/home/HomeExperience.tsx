'use client';
import { useQuery } from '@tanstack/react-query';
import { useEffect } from 'react';
import { Hero } from '@/components/hero';
import { SectionRow } from '@/components/section-row';
import { ErrorState, PageLoader } from '@/components/states';
import { getHome } from '@/features/catalog/api';
export function HomeExperience() { const home = useQuery({ queryKey: ['home'], queryFn: getHome }); useEffect(() => { const accent = home.data?.remote_config.accent_color; if (typeof accent === 'string' && /^#[0-9a-f]{6}$/i.test(accent)) document.documentElement.style.setProperty('--accent', accent); }, [home.data]); if (home.isPending) return <PageLoader />; if (home.isError) return <ErrorState retry={() => void home.refetch()} />; return <div className="min-h-screen"><Hero items={home.data.hero} /><div className="mx-auto -mt-1 max-w-[1600px] space-y-12 px-5 pb-20 md:px-8">{home.data.sections.map((s) => <SectionRow key={s.id} section={s} />)}{!home.data.hero.length && !home.data.sections.length && <div className="rounded-3xl bg-[var(--card)] p-10 text-center text-[var(--muted)]">The catalog is connected. Published content will appear here automatically.</div>}</div></div>; }
