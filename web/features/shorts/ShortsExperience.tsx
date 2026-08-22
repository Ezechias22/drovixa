'use client';

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import Link from 'next/link';
import { useState } from 'react';

import { EmptyState, ErrorState, PageLoader } from '@/components/states';
import { getShorts } from '@/features/catalog/api';
import type { ShortData } from '@/features/catalog/types';
import { CommentsPanel } from '@/features/community/CommentsPanel';
import { getLikeStatus, setLike } from '@/features/community/api';
import { getFeatureFlags } from '@/features/configuration/api';
import { useAuthStore } from '@/stores/auth-store';

export function ShortsExperience() {
  const [commentingOn, setCommentingOn] = useState<ShortData | null>(null);
  const shorts = useQuery({ queryKey: ['shorts'], queryFn: getShorts });
  const flags = useQuery({ queryKey: ['feature-flags'], queryFn: getFeatureFlags });
  if (shorts.isPending) return <PageLoader/>;
  if (shorts.isError) return <ErrorState retry={() => void shorts.refetch()}/>;
  if (!shorts.data.length) return <div className="mx-auto max-w-xl px-5 py-16"><EmptyState title="No shorts yet" body="Published vertical episodes will appear here."/></div>;
  return <>
    <div className="mx-auto h-[calc(100vh-72px)] max-w-xl snap-y snap-mandatory overflow-y-auto">{shorts.data.map((short) => <ShortCard commentsEnabled={flags.data?.comments_enabled?.enabled === true} item={short} key={short.id} onComments={() => setCommentingOn(short)}/>)}</div>
    {commentingOn ? <div className="fixed inset-0 z-[90] bg-black/75 p-0 md:grid md:place-items-center md:p-6"><div className="h-full w-full overflow-y-auto bg-[var(--background)] p-5 md:max-h-[90vh] md:max-w-3xl md:rounded-3xl md:p-8"><div className="flex items-center justify-between"><div><h2 className="text-2xl font-black">Comments</h2><p className="text-sm text-[var(--muted)]">{commentingOn.series.title}</p></div><button className="text-3xl" onClick={() => setCommentingOn(null)}>×</button></div><CommentsPanel targetId={commentingOn.id} targetType="short"/></div></div> : null}
  </>;
}

function ShortCard({ commentsEnabled, item, onComments }: { commentsEnabled: boolean; item: ShortData; onComments: () => void }) {
  const client = useQueryClient();
  const authenticated = useAuthStore((state) => Boolean(state.accessToken));
  const key = ['like', 'short', item.id] as const;
  const status = useQuery({ queryKey: key, queryFn: () => getLikeStatus('short', item.id), enabled: authenticated });
  const like = useMutation({ mutationFn: () => setLike('short', item.id, Boolean(status.data?.liked)), onSuccess: () => client.invalidateQueries({ queryKey: key }) });
  return <section className="relative h-full snap-start overflow-hidden bg-[#181b21]">{item.thumbnail_url && <img alt="" className="absolute inset-0 h-full w-full object-cover" src={item.thumbnail_url}/>}<div className="absolute inset-0 bg-gradient-to-t from-black via-transparent to-black/20"/><div className="absolute inset-x-0 bottom-0 p-7 pr-24"><h1 className="text-2xl font-black">{item.series.title}</h1><p className="mt-2 font-bold">Episode {item.episode_number} · {item.title}</p><p className="mt-2 text-sm text-white/70">{item.description}</p><Link className="primary-button mt-5" href={`/watch/${item.id}?target=episode`}>▶ Watch</Link></div><div className="absolute bottom-10 right-5 grid gap-4 text-center"><button className={`grid h-14 w-14 place-items-center rounded-full bg-black/65 text-xl ${status.data?.liked ? 'text-[var(--accent)]' : ''}`} onClick={() => authenticated ? like.mutate() : window.location.assign('/login')}><span>{status.data?.liked ? '♥' : '♡'}</span><span className="text-[9px] font-bold">{status.data?.count ?? 0}</span></button>{commentsEnabled ? <button className="grid h-14 w-14 place-items-center rounded-full bg-black/65" onClick={onComments}><span className="text-xl">◌</span><span className="text-[9px] font-bold">Talk</span></button> : null}<div className="grid h-14 w-14 place-items-center rounded-full bg-black/65"><span className="text-xl">↗</span><span className="text-[9px] font-bold">Share</span></div></div></section>;
}
