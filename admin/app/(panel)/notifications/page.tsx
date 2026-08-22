'use client';

import { zodResolver } from '@hookform/resolvers/zod';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useForm } from 'react-hook-form';
import { z } from 'zod';

import { Badge, PageHeading, QueryState, StatCard } from '@/components/ui';
import { apiRequest, formatDate } from '@/lib/api';

type Campaign = {
  id: string;
  name: string;
  type: string;
  title: string;
  status: string;
  channels: string[];
  recipient_count: number;
  failure_count: number;
  scheduled_at?: string | null;
  sent_at?: string | null;
  created_at: string;
};

type ProviderStatus = {
  provider: string;
  configured: boolean;
  project_id?: string | null;
  dry_run: boolean;
  batch_size: number;
};

const optionalUrl = z.union([z.literal(''), z.string().url()]);
const schema = z.object({
  name: z.string().min(2),
  type: z.enum([
    'new_episode',
    'new_series',
    'promotion',
    'system',
    'recommendation',
    'wallet',
    'subscription',
    'account_security',
  ]),
  title: z.string().min(2),
  body: z.string().min(2),
  segment: z.enum(['all', 'premium', 'non_premium', 'inactive']),
  push: z.boolean(),
  imageUrl: optionalUrl,
  actionUrl: z.string(),
  scheduledAt: z.string(),
});
type FormValues = z.infer<typeof schema>;

function statusTone(status: string) {
  if (status === 'sent') return 'success';
  if (status === 'cancelled' || status === 'failed') return 'danger';
  if (status === 'scheduled') return 'accent';
  return 'warning';
}

function resetValues(): FormValues {
  return {
    type: 'promotion', segment: 'all', name: '', title: '', body: '', push: true,
    imageUrl: '', actionUrl: 'drovixa://notifications', scheduledAt: '',
  };
}

export default function NotificationsPage() {
  const client = useQueryClient();
  const query = useQuery({
    queryKey: ['campaigns'],
    queryFn: async () =>
      (await apiRequest<Campaign[]>('/notification-campaigns?page=1&limit=50')).data,
    refetchInterval: (state) =>
      state.state.data?.some((item) => ['queued', 'processing'].includes(item.status))
        ? 4_000
        : false,
  });
  const provider = useQuery({
    queryKey: ['notification-provider'],
    queryFn: async () =>
      (await apiRequest<ProviderStatus>('/notifications/provider-status')).data,
  });
  const form = useForm<FormValues>({ resolver: zodResolver(schema), defaultValues: resetValues() });
  const refresh = () => client.invalidateQueries({ queryKey: ['campaigns'] });
  const create = useMutation({
    mutationFn: (values: FormValues) => apiRequest('/notification-campaigns', {
      method: 'POST',
      body: JSON.stringify({
        name: values.name, type: values.type, title: values.title, body: values.body,
        image_url: values.imageUrl || null,
        action_url: values.actionUrl || null,
        scheduled_at: values.scheduledAt ? new Date(values.scheduledAt).toISOString() : null,
        audience: { segment: values.segment, inactive_days: 30 },
        channels: values.push ? ['in_app', 'push'] : ['in_app'],
        metadata: {},
      }),
    }),
    onSuccess: () => { form.reset(resetValues()); refresh(); },
  });
  const send = useMutation({
    mutationFn: (id: string) => apiRequest(`/notification-campaigns/${id}/send`, {
      method: 'POST', body: JSON.stringify({ send_now: true }),
    }),
    onSuccess: refresh,
  });
  const cancel = useMutation({
    mutationFn: (id: string) => apiRequest(`/notification-campaigns/${id}/cancel`, { method: 'POST' }),
    onSuccess: refresh,
  });
  const error = create.error ?? send.error ?? cancel.error;

  return (
    <div className="page">
      <PageHeading
        eyebrow="Audience engagement"
        title="Notification campaigns"
        description="Send reliable in-app notifications and Firebase Cloud Messaging campaigns from one audited workspace."
      />
      <div className="grid-stats">
        <StatCard color={provider.data?.configured ? '#22c55e' : '#f59e0b'}
          detail={provider.data?.configured ? `Project ${provider.data.project_id}` : 'In-app delivery remains available'}
          label="Firebase Cloud Messaging" value={provider.data?.configured ? 'Ready' : 'Setup needed'} />
        <StatCard color="#8b5cf6" detail="Firebase Admin multicast safety limit"
          label="Push batch size" value={provider.data?.batch_size ?? 500} />
        <StatCard color="#ff3d71" detail="Queued and processing campaigns" label="Active deliveries"
          value={query.data?.filter((item) => ['queued', 'processing'].includes(item.status)).length ?? 0} />
        <StatCard color="#38bdf8" detail="Completed without delivery failures" label="Sent campaigns"
          value={query.data?.filter((item) => item.status === 'sent').length ?? 0} />
      </div>
      <section className="content-grid" style={{ alignItems: 'start' }}>
        <article className="panel">
          <div className="panel-header"><div><h3>Campaign history</h3><p>Draft, scheduled, queued, partial and sent campaigns</p></div></div>
          {error ? <div className="notice" style={{ marginBottom: 12 }}>{error.message}</div> : null}
          <QueryState loading={query.isLoading} error={query.error} empty={query.data?.length === 0}>
            <div className="table-wrap"><table className="data-table">
              <thead><tr><th>Campaign</th><th>Status</th><th>Channels</th><th>Audience</th><th>Created</th><th>Actions</th></tr></thead>
              <tbody>{query.data?.map((campaign) => <tr key={campaign.id}>
                <td className="primary-cell"><strong>{campaign.name}</strong><small>{campaign.title} · {campaign.type}</small></td>
                <td><Badge tone={statusTone(campaign.status)}>{campaign.status}</Badge></td>
                <td>{campaign.channels.join(' + ')}</td>
                <td>{campaign.recipient_count.toLocaleString()} recipients{campaign.failure_count ? ` · ${campaign.failure_count} failed` : ''}</td>
                <td>{formatDate(campaign.created_at)}</td>
                <td><div className="actions">
                  {['draft', 'scheduled'].includes(campaign.status) ? <button className="button button-primary"
                    onClick={() => window.confirm('Send this campaign now?') && send.mutate(campaign.id)}>Send now</button> : null}
                  {['draft', 'scheduled'].includes(campaign.status) ? <button className="button button-danger"
                    onClick={() => cancel.mutate(campaign.id)}>Cancel</button> : null}
                </div></td>
              </tr>)}</tbody>
            </table></div>
          </QueryState>
        </article>
        <article className="panel">
          <div className="panel-header"><div><h3>Compose campaign</h3><p>Push needs Firebase plus an EAS development or production build.</p></div></div>
          <form className="form-grid" onSubmit={form.handleSubmit((values) => create.mutate(values))}>
            <div className="form-field full"><label>Internal name</label><input className="field" {...form.register('name')} /></div>
            <div className="form-field"><label>Type</label><select className="select" {...form.register('type')}><option value="promotion">Promotion</option><option value="new_episode">New episode</option><option value="new_series">New series</option><option value="recommendation">Recommendation</option><option value="system">System</option><option value="wallet">Wallet</option><option value="subscription">Subscription</option><option value="account_security">Security</option></select></div>
            <div className="form-field"><label>Audience</label><select className="select" {...form.register('segment')}><option value="all">All users</option><option value="premium">Premium users</option><option value="non_premium">Non-premium</option><option value="inactive">Inactive 30 days</option></select></div>
            <div className="form-field full"><label>Notification title</label><input className="field" {...form.register('title')} /></div>
            <div className="form-field full"><label>Message</label><textarea className="textarea" {...form.register('body')} /></div>
            <div className="form-field full"><label>Action URL</label><input className="field" placeholder="drovixa://notifications" {...form.register('actionUrl')} /></div>
            <div className="form-field full"><label>Image URL (optional)</label><input className="field" placeholder="https://..." {...form.register('imageUrl')} /></div>
            <div className="form-field full"><label>Schedule (optional, your local time)</label><input className="field" type="datetime-local" {...form.register('scheduledAt')} /></div>
            <label className="section-card full" style={{ gridTemplateColumns: 'auto 1fr' }}>
              <input type="checkbox" {...form.register('push')} />
              <span><strong>Also send Firebase push</strong><small style={{ display: 'block', color: 'var(--muted)', marginTop: 4 }}>Every campaign still creates an in-app notification.</small></span>
            </label>
            {Object.keys(form.formState.errors).length ? <div className="form-error full">Check the required fields and URL formats.</div> : null}
            <button className="button button-accent" disabled={create.isPending}>{create.isPending ? 'Saving…' : 'Save campaign'}</button>
          </form>
        </article>
      </section>
    </div>
  );
}
