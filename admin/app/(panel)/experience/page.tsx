'use client';

import { useQuery } from '@tanstack/react-query';

import { PageHeading, QueryState, StatCard } from '@/components/ui';
import { apiRequest } from '@/lib/api';

type Summary = {
  profiles: number;
  kids_profiles: number;
  ratings: number;
  average_score: number;
  downloads: Record<string, number>;
  cast_sessions: Record<string, number>;
};

export default function ExperiencePage() {
  const query = useQuery({
    queryKey: ['phase10-experience'],
    queryFn: async () => (await apiRequest<Summary>('/experience/summary')).data,
  });
  return (
    <div className="page">
      <PageHeading
        eyebrow="Phase 10"
        title="Profiles & device experience"
        description="Kids safety, user ratings, secure offline licenses and living-room playback."
      />
      <QueryState loading={query.isLoading} error={query.error}>
        {query.data ? (
          <>
            <section className="grid-stats">
              <StatCard label="Viewer profiles" value={query.data.profiles} detail={`${query.data.kids_profiles} Kids profiles`} color="#8b5cf6" />
              <StatCard label="Ratings" value={query.data.ratings} detail={`${query.data.average_score.toFixed(1)}/5 average`} color="#f59e0b" />
              <StatCard label="Offline ready" value={query.data.downloads.ready ?? 0} detail={`${query.data.downloads.authorized ?? 0} authorized`} color="#22c55e" />
              <StatCard label="Active casting" value={(query.data.cast_sessions.connected ?? 0) + (query.data.cast_sessions.playing ?? 0)} detail="Chromecast and AirPlay sessions" color="#ff3d71" />
            </section>
            <section className="content-grid">
              <article className="panel"><div className="panel-header"><div><h3>Download licenses</h3><p>Server-authorized offline state</p></div></div><div className="warning-list">{Object.entries(query.data.downloads).map(([key, value]) => <div className="warning-row" key={key}><span>{key}</span><strong>{value}</strong></div>)}</div></article>
              <article className="panel"><div className="panel-header"><div><h3>Casting sessions</h3><p>Living-room playback state</p></div></div><div className="warning-list">{Object.entries(query.data.cast_sessions).map(([key, value]) => <div className="warning-row" key={key}><span>{key}</span><strong>{value}</strong></div>)}</div></article>
            </section>
          </>
        ) : null}
      </QueryState>
    </div>
  );
}
