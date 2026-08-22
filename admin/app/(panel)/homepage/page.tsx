'use client';

import { zodResolver } from '@hookform/resolvers/zod';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useForm } from 'react-hook-form';
import { z } from 'zod';

import { Badge, PageHeading, QueryState } from '@/components/ui';
import { apiRequest } from '@/lib/api';

type Section = {
  id: string;
  key: string;
  title: string;
  algorithm: string;
  presentation: string;
  active: boolean;
  sort_order: number;
  max_items: number;
  items: { id: string; content_id: string; content: { title: string } }[];
};

const schema = z.object({
  title: z.string().min(2),
  key: z.string().min(2).regex(/^[a-z0-9_]+$/),
  algorithm: z.enum(['manual', 'trending', 'latest', 'most_watched', 'recommended', 'top_10', 'recently_added']),
  presentation: z.enum(['poster', 'wide', 'ranked', 'progress']),
});
type FormValues = z.infer<typeof schema>;

export default function HomepagePage() {
  const client = useQueryClient();
  const query = useQuery({
    queryKey: ['homepage-sections'],
    queryFn: async () => (await apiRequest<Section[]>('/homepage/sections')).data,
  });
  const form = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: { algorithm: 'manual', presentation: 'poster' },
  });
  const refresh = () => client.invalidateQueries({ queryKey: ['homepage-sections'] });
  const create = useMutation({
    mutationFn: (values: FormValues) => apiRequest('/homepage/sections', { method: 'POST', body: JSON.stringify(values) }),
    onSuccess: () => { form.reset({ algorithm: 'manual', presentation: 'poster', title: '', key: '' }); refresh(); },
  });
  const patch = useMutation({
    mutationFn: ({ id, body }: { id: string; body: Record<string, unknown> }) => apiRequest(`/homepage/sections/${id}`, { method: 'PATCH', body: JSON.stringify(body) }),
    onSuccess: refresh,
  });
  const addItem = useMutation({
    mutationFn: ({ id, contentId }: { id: string; contentId: string }) => apiRequest(`/homepage/sections/${id}/items`, { method: 'POST', body: JSON.stringify({ content_id: contentId, sort_order: 0 }) }),
    onSuccess: refresh,
  });
  const removeItem = useMutation({
    mutationFn: ({ sectionId, itemId }: { sectionId: string; itemId: string }) => apiRequest(`/homepage/sections/${sectionId}/items/${itemId}`, { method: 'DELETE' }),
    onSuccess: refresh,
  });
  const reorder = useMutation({
    mutationFn: (ids: string[]) => apiRequest('/homepage/sections/reorder', { method: 'POST', body: JSON.stringify({ section_ids: ids }) }),
    onSuccess: refresh,
  });
  const move = (id: string, delta: number) => {
    const ids = query.data?.map((section) => section.id) ?? [];
    const index = ids.indexOf(id);
    const target = index + delta;
    if (index < 0 || target < 0 || target >= ids.length) return;
    [ids[index], ids[target]] = [ids[target], ids[index]];
    reorder.mutate(ids);
  };
  const error = create.error ?? patch.error ?? addItem.error ?? removeItem.error ?? reorder.error;

  return (
    <div className="page">
      <PageHeading eyebrow="Experience control" title="Homepage builder" description="Create, hide, reorder and target dynamic home sections without releasing a new app version." />
      <section className="content-grid" style={{ alignItems: 'start' }}>
        <article className="panel">
          <div className="panel-header"><div><h3>Live section order</h3><p>Changes affect mobile and web through the shared API.</p></div></div>
          {error ? <div className="notice" style={{ marginBottom: 12 }}>{error.message}</div> : null}
          <QueryState loading={query.isLoading} error={query.error} empty={query.data?.length === 0}>
            <div style={{ display: 'grid', gap: 10 }}>
              {query.data?.map((section, index) => (
                <div className="section-card" key={section.id}>
                  <div className="drag-index">{index + 1}</div>
                  <div className="primary-cell">
                    <strong>{section.title}</strong>
                    <small>{section.key} · {section.algorithm} · {section.presentation}</small>
                    {section.items.length ? <small>{section.items.map((item) => item.content.title).join(' · ')}</small> : null}
                  </div>
                  <div className="actions">
                    <Badge tone={section.active ? 'success' : 'danger'}>{section.active ? 'live' : 'hidden'}</Badge>
                    <button className={`toggle ${section.active ? 'on' : ''}`} aria-label={`Toggle ${section.title}`} onClick={() => patch.mutate({ id: section.id, body: { active: !section.active } })} />
                    <button className="button button-quiet" onClick={() => move(section.id, -1)}>↑</button>
                    <button className="button button-quiet" onClick={() => move(section.id, 1)}>↓</button>
                    {section.algorithm === 'manual' ? <button className="button button-quiet" onClick={() => { const contentId = window.prompt('Paste a content ID from the Content page'); if (contentId) addItem.mutate({ id: section.id, contentId }); }}>Add title</button> : null}
                  </div>
                  {section.items.length ? <div style={{ gridColumn: '2 / -1' }} className="actions">{section.items.map((item) => <button key={item.id} className="button button-danger" onClick={() => removeItem.mutate({ sectionId: section.id, itemId: item.id })}>Remove {item.content.title}</button>)}</div> : null}
                </div>
              ))}
            </div>
          </QueryState>
        </article>
        <article className="panel">
          <div className="panel-header"><div><h3>New section</h3><p>Add a reusable algorithmic or manual rail.</p></div></div>
          <form className="form-grid" onSubmit={form.handleSubmit((values) => create.mutate(values))}>
            <div className="form-field full"><label>Display title</label><input className="field" {...form.register('title')} /></div>
            <div className="form-field full"><label>Stable key</label><input className="field" placeholder="editors_picks" {...form.register('key')} /></div>
            <div className="form-field full"><label>Algorithm</label><select className="select" {...form.register('algorithm')}><option value="manual">Manual</option><option value="trending">Trending</option><option value="latest">Latest</option><option value="most_watched">Most watched</option><option value="recommended">Recommended</option><option value="top_10">Top 10</option><option value="recently_added">Recently added</option></select></div>
            <div className="form-field full"><label>Presentation</label><select className="select" {...form.register('presentation')}><option value="poster">Poster</option><option value="wide">Wide</option><option value="ranked">Ranked</option><option value="progress">Progress</option></select></div>
            {Object.keys(form.formState.errors).length ? <div className="form-error full">Check the section name and key format.</div> : null}
            <button className="button button-accent" disabled={create.isPending}>{create.isPending ? 'Creating…' : 'Create section'}</button>
          </form>
        </article>
      </section>
    </div>
  );
}
