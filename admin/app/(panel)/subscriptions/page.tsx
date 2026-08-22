'use client';

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';

import { Badge, PageHeading, QueryState } from '@/components/ui';
import { apiRequest, formatDate, formatMoney } from '@/lib/api';

type Plan = { id: string; name: string; slug: string; interval: string; price: string; currency: string; active: boolean; featured: boolean; trial_days: number; benefits: Record<string, unknown> };
type Subscription = { id: string; user_id: string; plan: Plan; provider: string; status: string; current_period_end: string; cancel_at_period_end: boolean };

export default function SubscriptionsPage() {
  const client = useQueryClient();
  const [name, setName] = useState(''); const [price, setPrice] = useState(''); const [interval, setInterval] = useState('monthly');
  const plans = useQuery({ queryKey: ['subscription-plans'], queryFn: async () => (await apiRequest<Plan[]>('/subscription-plans?page=1&limit=100')).data });
  const subscriptions = useQuery({ queryKey: ['subscriptions'], queryFn: async () => (await apiRequest<Subscription[]>('/subscriptions?page=1&limit=100')).data });
  const create = useMutation({ mutationFn: () => apiRequest('/subscription-plans', { method: 'POST', body: JSON.stringify({ name, slug: name.trim().toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, ''), interval, price: Number(price), currency: 'USD', benefits: { no_ads: true, premium_content: true, offline_download: true, hd: true } }) }), onSuccess: () => { setName(''); setPrice(''); client.invalidateQueries({ queryKey: ['subscription-plans'] }); } });
  const toggle = useMutation({ mutationFn: ({ id, active }: { id: string; active: boolean }) => apiRequest(`/subscription-plans/${id}`, { method: 'PATCH', body: JSON.stringify({ active }) }), onSuccess: () => client.invalidateQueries({ queryKey: ['subscription-plans'] }) });
  return <div className="page">
    <PageHeading eyebrow="Premium business" title="Subscriptions" description="Manage premium plans and monitor the lifecycle of every viewer subscription." />
    <section className="content-grid" style={{ alignItems: 'start' }}>
      <article className="panel"><div className="panel-header"><div><h3>Plans</h3><p>Products shown in the Premium experience</p></div></div>
        <div className="toolbar"><input className="field" placeholder="Plan name" value={name} onChange={(e) => setName(e.target.value)} /><input className="field" style={{ width: 110 }} placeholder="Price" inputMode="decimal" value={price} onChange={(e) => setPrice(e.target.value)} /><select className="select" value={interval} onChange={(e) => setInterval(e.target.value)}><option value="monthly">Monthly</option><option value="quarterly">Quarterly</option><option value="annual">Annual</option></select><button className="button button-primary" disabled={!name || !Number(price) || create.isPending} onClick={() => create.mutate()}>Create</button></div>
        {create.error || toggle.error ? <div className="notice">{(create.error ?? toggle.error)?.message}</div> : null}
        <QueryState loading={plans.isLoading} error={plans.error} empty={plans.data?.length === 0}><div className="table-wrap"><table className="data-table"><thead><tr><th>Plan</th><th>Price</th><th>State</th><th>Control</th></tr></thead><tbody>{plans.data?.map((plan) => <tr key={plan.id}><td className="primary-cell"><strong>{plan.name}</strong><small>{plan.interval} · {plan.trial_days} trial days</small></td><td>{formatMoney(plan.price, plan.currency)}</td><td><Badge tone={plan.active ? 'success' : 'danger'}>{plan.active ? 'active' : 'hidden'}</Badge></td><td><button className={`toggle ${plan.active ? 'on' : ''}`} onClick={() => toggle.mutate({ id: plan.id, active: !plan.active })} /></td></tr>)}</tbody></table></div></QueryState>
      </article>
      <article className="panel"><div className="panel-header"><div><h3>Active records</h3><p>Latest viewer subscriptions</p></div></div><QueryState loading={subscriptions.isLoading} error={subscriptions.error} empty={subscriptions.data?.length === 0}><div className="table-wrap"><table className="data-table"><thead><tr><th>User</th><th>Plan</th><th>Status</th><th>Renews/ends</th></tr></thead><tbody>{subscriptions.data?.map((sub) => <tr key={sub.id}><td>{sub.user_id.slice(0, 8)}</td><td>{sub.plan?.name ?? 'Plan'}</td><td><Badge tone={sub.status === 'active' ? 'success' : 'warning'}>{sub.status}</Badge></td><td>{formatDate(sub.current_period_end)}</td></tr>)}</tbody></table></div></QueryState></article>
    </section>
  </div>;
}
