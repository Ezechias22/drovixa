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

export default function ContentPage() {
  const router = useRouter();
  const client = useQueryClient();
  const [type, setType] = useState<'series' | 'movies'>('series');
  const [title, setTitle] = useState('');
  const query = useQuery({
    queryKey: ['admin-content', type],
    queryFn: async () => (await apiRequest<ContentRow[]>(`/${type}?page=1&limit=100`)).data,
  });
  const refresh = () => client.invalidateQueries({ queryKey: ['admin-content'] });
  const create = useMutation({
    mutationFn: () =>
      apiRequest<ContentRow>(`/${type}`, { method: 'POST', body: JSON.stringify({ title }) }),
    onSuccess: (response) => {
      setTitle('');
      refresh();
      router.push(`/content/${type}/${response.data.id}`);
    },
  });
  const archive = useMutation({
    mutationFn: (id: string) => apiRequest(`/${type}/${id}`, { method: 'DELETE' }),
    onSuccess: refresh,
  });

  return (
    <div className="page">
      <PageHeading
        eyebrow="Catalog studio"
        title="Content"
        description="Create a draft, then open Content Studio to add artwork, videos, seasons and episodes before publishing."
      />
      <section className="panel">
        <div className="toolbar">
          <button className={`button ${type === 'series' ? 'button-accent' : 'button-quiet'}`} onClick={() => setType('series')}>Series</button>
          <button className={`button ${type === 'movies' ? 'button-accent' : 'button-quiet'}`} onClick={() => setType('movies')}>Movies</button>
          <span style={{ flex: 1 }} />
          <input className="field" placeholder={`New ${type === 'series' ? 'series' : 'movie'} title`} value={title} onChange={(event) => setTitle(event.target.value)} />
          <button className="button button-primary" disabled={title.trim().length < 1 || create.isPending} onClick={() => create.mutate()}>Create draft</button>
        </div>
        {create.error || archive.error ? <div className="notice">{(create.error ?? archive.error)?.message}</div> : null}
        <QueryState loading={query.isLoading} error={query.error} empty={query.data?.length === 0}>
          <div className="table-wrap">
            <table className="data-table">
              <thead><tr><th>Title</th><th>ID</th><th>Status</th><th>Access</th><th>Published</th><th>Actions</th></tr></thead>
              <tbody>
                {query.data?.map((row) => (
                  <tr key={row.id}>
                    <td className="primary-cell"><strong>{row.title}</strong><small>/{row.slug}{row.total_episodes !== undefined ? ` · ${row.total_episodes} episodes` : ''}</small></td>
                    <td><button className="button button-quiet" onClick={() => navigator.clipboard.writeText(row.id)} title={row.id}>Copy ID</button></td>
                    <td><Badge tone={row.status === 'published' ? 'success' : 'warning'}>{row.status}</Badge></td>
                    <td><Badge tone={row.premium ? 'accent' : ''}>{row.premium ? 'premium' : row.visibility}</Badge></td>
                    <td>{formatDate(row.published_at)}</td>
                    <td><div className="actions">
                      <button className="button button-accent" onClick={() => router.push(`/content/${type}/${row.id}`)}>Edit &amp; upload</button>
                      <button className="button button-danger" onClick={() => window.confirm(`Archive ${row.title}?`) && archive.mutate(row.id)}>Archive</button>
                    </div></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </QueryState>
      </section>
    </div>
  );
}
