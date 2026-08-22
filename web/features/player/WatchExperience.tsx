'use client';

import { useQuery } from '@tanstack/react-query';
import { useState } from 'react';

import { CommentsPanel } from '@/features/community/CommentsPanel';
import { getFeatureFlags } from '@/features/configuration/api';
import { DrovixaWebPlayer } from './DrovixaWebPlayer';
import type { PlaybackTarget } from './types';

export function WatchExperience({ id, target }: { id: string; target: PlaybackTarget }) {
  const [commentsOpen, setCommentsOpen] = useState(false);
  const flags = useQuery({ queryKey: ['feature-flags'], queryFn: getFeatureFlags });
  const commentsEnabled = target === 'episode' && flags.data?.comments_enabled?.enabled === true;
  return <>
    <main className="mx-auto flex min-h-screen w-full max-w-7xl flex-col justify-center gap-5 px-4 py-8 md:px-8">
      <DrovixaWebPlayer id={id} target={target}/>
      {commentsEnabled ? <button className="secondary-button self-end" onClick={() => setCommentsOpen(true)}>◌ Episode comments</button> : null}
    </main>
    {commentsOpen ? <div className="fixed inset-0 z-[90] bg-black/75 p-0 md:grid md:place-items-center md:p-6"><div className="h-full w-full overflow-y-auto bg-[var(--background)] p-5 md:max-h-[90vh] md:max-w-3xl md:rounded-3xl md:p-8"><div className="flex items-center justify-between"><h2 className="text-2xl font-black">Episode comments</h2><button className="text-3xl" onClick={() => setCommentsOpen(false)}>×</button></div><CommentsPanel targetId={id} targetType="episode"/></div></div> : null}
  </>;
}
