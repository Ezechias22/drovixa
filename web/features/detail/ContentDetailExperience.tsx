'use client';

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import Link from 'next/link';
import { useRouter } from 'next/navigation';

import { CheckIcon, PlayIcon, PlusIcon } from '@/components/icons';
import { ErrorState, PageLoader } from '@/components/states';
import { getContentDetail, getEpisodes, toggleFavorite } from '@/features/catalog/api';
import type { ContentDetail } from '@/features/catalog/types';
import { CommentsPanel } from '@/features/community/CommentsPanel';
import { setLike } from '@/features/community/api';
import { getFeatureFlags } from '@/features/configuration/api';
import { useAuthStore } from '@/stores/auth-store';

export function ContentDetailExperience({ type, slug }: { type: 'series' | 'movie'; slug: string }) {
  const router = useRouter();
  const client = useQueryClient();
  const authenticated = useAuthStore((state) => Boolean(state.accessToken));
  const detailKey = ['content', type, slug] as const;
  const detail = useQuery({ queryKey: detailKey, queryFn: () => getContentDetail(type, slug) });
  const flags = useQuery({ queryKey: ['feature-flags'], queryFn: getFeatureFlags });
  const episodes = useQuery({ queryKey: ['episodes', detail.data?.series_id], queryFn: () => getEpisodes(detail.data!.series_id!), enabled: type === 'series' && Boolean(detail.data?.series_id) });
  const favorite = useMutation({ mutationFn: () => toggleFavorite(detail.data!.id, Boolean(detail.data!.is_favorite)), onSuccess: () => client.invalidateQueries({ queryKey: detailKey }) });
  const like = useMutation({
    mutationFn: () => setLike('content', detail.data!.id, Boolean(detail.data!.is_liked)),
    onMutate: async () => { await client.cancelQueries({ queryKey: detailKey }); client.setQueryData(detailKey, (old: ContentDetail | undefined) => old ? { ...old, is_liked: !old.is_liked, like_count: Math.max(0, (old.like_count ?? 0) + (old.is_liked ? -1 : 1)) } : old); },
    onSettled: () => client.invalidateQueries({ queryKey: detailKey }),
  });
  if (detail.isPending) return <PageLoader/>;
  if (detail.isError) return <ErrorState retry={() => void detail.refetch()}/>;
  const item = detail.data;
  const watchId = type === 'movie' ? item.movie_id : episodes.data?.[0]?.id;
  const gate = (action: () => void) => authenticated ? action() : router.push('/login');

  return <div className="min-h-screen">
    <section className="relative isolate min-h-[620px] overflow-hidden">
      {item.backdrop_url ? <img alt="" className="absolute inset-0 -z-20 h-full w-full object-cover" src={item.backdrop_url}/> : <div className="absolute inset-0 -z-20 bg-[#20232b]"/>}
      <div className="absolute inset-0 -z-10 bg-[linear-gradient(90deg,#08090bf5_3%,#08090baa_50%,transparent_80%),linear-gradient(0deg,#08090b,transparent_62%)]"/>
      <div className="mx-auto flex min-h-[620px] max-w-[1600px] items-end px-5 pb-16 md:items-center md:px-8"><div className="max-w-2xl pt-24">
        <p className="text-xs font-black tracking-[.25em] text-[var(--accent)]">{type === 'series' ? 'DROVIXA SERIES' : 'DROVIXA FILM'}</p>
        <h1 className="mt-4 text-5xl font-black tracking-[-.05em] md:text-7xl">{item.title}</h1>
        <div className="mt-5 flex gap-3 text-sm font-semibold text-white/70"><span>★ {Number(item.rating).toFixed(1)}</span><span>{item.age_rating}</span>{item.premium && <span>Premium</span>}</div>
        <p className="mt-6 max-w-xl text-lg leading-8 text-white/65">{item.description ?? item.short_description}</p>
        <div className="mt-8 flex flex-wrap gap-3">
          {watchId ? <Link className="primary-button" href={`/watch/${watchId}?target=${type === 'movie' ? 'movie' : 'episode'}`}><PlayIcon size={18}/> Play</Link> : <button disabled className="primary-button opacity-50">Video unavailable</button>}
          <button className="secondary-button" onClick={() => gate(() => favorite.mutate())}>{item.is_favorite ? <CheckIcon/> : <PlusIcon/>}{item.is_favorite ? 'In My List' : 'My List'}</button>
          <button className={`secondary-button ${item.is_liked ? 'text-[var(--accent)]' : ''}`} onClick={() => gate(() => like.mutate())}>{item.is_liked ? '♥' : '♡'} {item.like_count ?? 0}</button>
        </div>
      </div></div>
    </section>
    <div className="mx-auto max-w-[1600px] space-y-12 px-5 pb-20 md:px-8">
      {!!item.genres.length && <div className="flex flex-wrap gap-2">{item.genres.map((genre) => <Link key={genre.id} className="rounded-full bg-white/[.07] px-4 py-2 text-sm font-semibold" href={`/discover?genre=${genre.slug}`}>{genre.name}</Link>)}</div>}
      {type === 'series' && <section><h2 className="text-2xl font-black">Episodes</h2><div className="mt-5 grid gap-3">{episodes.data?.map((episode) => <Link key={episode.id} className="flex items-center gap-4 rounded-2xl bg-[var(--card)] p-3" href={`/watch/${episode.id}?target=episode`}><div className="grid aspect-video w-32 place-items-center overflow-hidden rounded-xl bg-[#20232b]">{episode.thumbnail_url ? <img alt="" className="h-full w-full object-cover" src={episode.thumbnail_url}/> : <PlayIcon/>}</div><div><p className="text-xs font-black text-[var(--accent)]">EPISODE {episode.episode_number}</p><h3 className="mt-1 font-bold">{episode.title}</h3><p className="mt-1 text-xs text-[var(--muted)]">{episode.access_type === 'free' || episode.unlocked ? 'Ready to watch' : `${episode.coin_price} coins · Unlock to watch`}</p></div></Link>)}</div></section>}
      {!!item.cast.length && <section><h2 className="text-2xl font-black">Cast</h2><div className="scrollbar-hidden mt-5 flex gap-5 overflow-x-auto">{item.cast.map((credit) => <div key={credit.actor.id} className="w-24 shrink-0 text-center"><div className="mx-auto h-20 w-20 overflow-hidden rounded-full bg-[#20232b]">{credit.actor.photo_url && <img alt={credit.actor.name} className="h-full w-full object-cover" src={credit.actor.photo_url}/>}</div><p className="mt-3 text-sm font-bold">{credit.actor.name}</p><p className="text-xs text-[var(--muted)]">{credit.character_name}</p></div>)}</div></section>}
      {flags.data?.comments_enabled?.enabled ? <CommentsPanel targetId={item.id} targetType="content"/> : null}
    </div>
  </div>;
}
