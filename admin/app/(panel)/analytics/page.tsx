'use client';

import { useQuery } from '@tanstack/react-query';
import { useState } from 'react';

import { Badge, PageHeading, QueryState, StatCard } from '@/components/ui';
import { apiRequest, formatMoney } from '@/lib/api';

type Overview = { period_days: number; unique_viewers: number; playback_sessions: number; watch_hours: number; completion_rate: number; gross_revenue: string; timeline: { date: string; revenue: string }[] };
type ContentMetric = { id: string; title: string; type: string; views: number; likes: number; rating: string; unique_viewers: number; average_completion: number; average_watch_seconds: number };

export default function AnalyticsPage() {
  const [days, setDays] = useState(30);
  const overview = useQuery({ queryKey: ['analytics-overview', days], queryFn: async () => (await apiRequest<Overview>(`/analytics/overview?days=${days}`)).data });
  const content = useQuery({ queryKey: ['analytics-content'], queryFn: async () => (await apiRequest<ContentMetric[]>('/analytics/content?limit=50')).data });
  return <div className="page">
    <PageHeading eyebrow="Decision intelligence" title="Analytics" description="Real database metrics for viewing, completion and revenue—never frontend-invented numbers." action={<select className="select" value={days} onChange={(event) => setDays(Number(event.target.value))}><option value={7}>7 days</option><option value={30}>30 days</option><option value={90}>90 days</option><option value={365}>365 days</option></select>} />
    <QueryState loading={overview.isLoading} error={overview.error}>
      {overview.data ? <section className="grid-stats">
        <StatCard label="Unique viewers" value={overview.data.unique_viewers.toLocaleString()} detail={`${days}-day audience`} color="#8b5cf6" />
        <StatCard label="Playback sessions" value={overview.data.playback_sessions.toLocaleString()} detail="Authorized streams" color="#ff3d71" />
        <StatCard label="Watch hours" value={overview.data.watch_hours.toLocaleString()} detail={`${overview.data.completion_rate}% completion`} color="#22c55e" />
        <StatCard label="Gross revenue" value={formatMoney(overview.data.gross_revenue)} detail="Paid transaction value" color="#f59e0b" />
      </section> : null}
    </QueryState>
    <section className="panel" style={{ marginTop: 16 }}>
      <div className="panel-header"><div><h3>Content performance</h3><p>Viewer engagement by title</p></div></div>
      <QueryState loading={content.isLoading} error={content.error} empty={content.data?.length === 0}>
        <div className="table-wrap"><table className="data-table"><thead><tr><th>Title</th><th>Views</th><th>Unique viewers</th><th>Completion</th><th>Avg watch</th><th>Likes</th></tr></thead><tbody>{content.data?.map((item) => <tr key={item.id}><td className="primary-cell"><strong>{item.title}</strong><small><Badge>{item.type}</Badge></small></td><td>{item.views.toLocaleString()}</td><td>{item.unique_viewers.toLocaleString()}</td><td>{item.average_completion}%</td><td>{Math.round(item.average_watch_seconds / 60)} min</td><td>{item.likes.toLocaleString()}</td></tr>)}</tbody></table></div>
      </QueryState>
    </section>
  </div>;
}
