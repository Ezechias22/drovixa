'use client';

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useRouter } from 'next/navigation';
import { useState } from 'react';

import { Badge, PageHeading, QueryState } from '@/components/ui';
import { apiRequest, formatDate } from '@/lib/api';

type ContentRow = {
  id: string;
  type: 'series' | 'movie';
  title: string;
  slug: string;
  status: string;
  visibility: string;
  premium: boolean;
  featured: boolean;
  published_at?: string | null;
  total_episodes?: number;
};

type StudioMode = 'series' | 'movies' | 'shorts';

export default function ContentPage() {
  const router = useRouter();
  const client = useQueryClient();
  const [mode, setMode] = useState<StudioMode>('series');
  const [title, setTitle] = useState('');
  const endpoint = mode === 'movies' ? 'movies' : 'series';
  const query = useQuery({
    queryKey: ['admin-content', endpoint],
    queryFn: async () => (await apiRequest<ContentRow[]>(`/${endpoint}?page=1&limit=100`)).data,
  });
  const refresh = () => client.invalidateQueries({ queryKey: ['admin-content'] });
  const create = useMutation({
    mutationFn: () => apiRequest<ContentRow>(`/${endpoint}`, { method: 'POST', body: JSON.stringify({ title }) }),
    onSuccess: (response) => {
      setTitle('');
      refresh();
      router.push(`/content/${endpoint}/${response.data.id}${mode === 'shorts' ? '?mode=short' : ''}`);
    },
  });
  const archive = useMutation({ mutationFn: (id: string) => apiRequest(`/${endpoint}/${id}`, { method: 'DELETE' }), onSuccess: refresh });

  return (
    <div className="page">
      <PageHeading
        eyebrow="Catalog studio"
        title="Content"
        description="Publish series, movies and short vertical videos from one clear workspace."
      />
      <section className="panel">
        <div className="toolbar">
          <button className={`button ${mode === 'series' ? 'button-accent' : 'button-quiet'}`} onClick={() => setMode('series')}>Series</button>
          <button className={`button ${mode === 'movies' ? 'button-accent' : 'button-quiet'}`} onClick={() => setMode('movies')}>Movies</button>
          <button className={`button ${mode === 'shorts' ? 'button-accent' : 'button-quiet'}`} onClick={() => setMode('shorts')}>Short videos</button>
          <span style={{ flex: 1 }} />
          {mode !== 'shorts' ? <>
            <input className="field" placeholder={`New ${mode === 'series' ? 'series' : 'movie'} title`} value={title} onChange={(event) => setTitle(event.target.value)} />
            <button className="button button-primary" disabled={title.trim().length < 1 || create.isPending} onClick={() => create.mutate()}>Start publishing</button>
          </> : null}
        </div>
        {mode === 'shorts' ? <div className="notice success">Choose the series that owns the short. Drovixa will mark the episode vertical so it appears automatically in the Shorts feed.</div> : null}
        {create.error || archive.error ? <div className="notice">{(create.error ?? archive.error)?.message}</div> : null}
        <QueryState loading={query.isLoading} error={query.error} empty={query.data?.length === 0}>
          <div className="table-wrap">
            <table className="data-table">
              <thead><tr><th>Title</th><th>ID</th><th>Status</th><th>Access</th><th>Published</th><th>Actions</th></tr></thead>
              <tbody>{query.data?.map((row) => <tr key={row.id}>
                <td className="primary-cell"><strong>{row.title}</strong><small>/{row.slug}{row.total_episodes !== undefined ? ` · ${row.total_episodes} episodes` : ''}</small></td>
                <td><button className="button button-quiet" onClick={() => navigator.clipboard.writeText(row.id)} title={row.id}>Copy ID</button></td>
                <td><Badge tone={row.status === 'published' ? 'success' : 'warning'}>{row.status}</Badge></td>
                <td><Badge tone={row.premium ? 'accent' : ''}>{row.premium ? 'premium' : row.visibility}</Badge></td>
                <td>{formatDate(row.published_at)}</td>
                <td><div className="actions">
                  <button className="button button-accent" onClick={() => router.push(`/content/${endpoint}/${row.id}${mode === 'shorts' ? '?mode=short' : ''}`)}>{mode === 'shorts' ? 'Add short' : 'Open'}</button>
                  {mode !== 'shorts' ? <button className="button button-danger" onClick={() => window.confirm(`Archive ${row.title}?`) && archive.mutate(row.id)}>Archive</button> : null}
                </div></td>
              </tr>)}</tbody>
            </table>
          </div>
        </QueryState>
      </section>
    </div>
  );
}
