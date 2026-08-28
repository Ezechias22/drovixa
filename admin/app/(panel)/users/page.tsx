'use client';

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';

import { Badge, PageHeading, QueryState } from '@/components/ui';
import { apiRequest, formatDate } from '@/lib/api';
import type { AdminUser, PageMeta } from '@/lib/types';

type Role = { id: string; name: string; description: string; permissions: string[] };
type Plan = { id: string; name: string; active: boolean; interval: string };
type Monetization = {
  wallet: { coin_balance: number; bonus_coin_balance: number; total_balance: number };
  subscription: null | {
    id: string; provider: string; status: string; current_period_end: string;
    plan: { id: string; name: string };
  };
};

function tone(status: string) {
  if (status === 'active') return 'success';
  if (status === 'suspended' || status === 'banned') return 'danger';
  return 'warning';
}

export default function UsersPage() {
  const client = useQueryClient();
  const [q, setQ] = useState('');
  const [status, setStatus] = useState('');
  const [page, setPage] = useState(1);
  const [managing, setManaging] = useState<AdminUser | null>(null);
  const [coinAmount, setCoinAmount] = useState('100');
  const [reason, setReason] = useState('Admin adjustment');
  const [planId, setPlanId] = useState('');
  const [premiumDays, setPremiumDays] = useState('30');
  const [moneyNotice, setMoneyNotice] = useState('');
  const params = new URLSearchParams({ page: String(page), limit: '20' });
  if (q) params.set('q', q);
  if (status) params.set('status', status);
  const users = useQuery({
    queryKey: ['users', q, status, page],
    queryFn: () => apiRequest<AdminUser[]>(`/users?${params}`),
  });
  const roles = useQuery({
    queryKey: ['roles'],
    queryFn: async () => (await apiRequest<Role[]>('/roles')).data,
  });
  const plans = useQuery({
    queryKey: ['subscription-plans', 'user-manager'],
    queryFn: async () => (await apiRequest<Plan[]>('/subscription-plans?page=1&limit=100')).data,
  });
  const monetization = useQuery({
    queryKey: ['user-monetization', managing?.id],
    queryFn: async () => (await apiRequest<Monetization>(`/users/${managing?.id}/monetization`)).data,
    enabled: Boolean(managing),
  });
  const invalidate = () => client.invalidateQueries({ queryKey: ['users'] });
  const updateStatus = useMutation({
    mutationFn: ({ id, next }: { id: string; next: string }) =>
      apiRequest(`/users/${id}/status`, {
        method: 'PATCH',
        body: JSON.stringify({ status: next, reason: `Changed from Drovixa Admin to ${next}` }),
      }),
    onSuccess: invalidate,
  });
  const updateRole = useMutation({
    mutationFn: ({ id, role }: { id: string; role: string }) =>
      apiRequest(`/users/${id}/roles`, {
        method: 'PATCH',
        body: JSON.stringify({ roles: [role] }),
      }),
    onSuccess: invalidate,
  });
  const refreshMoney = () => client.invalidateQueries({ queryKey: ['user-monetization', managing?.id] });
  const adjustCoins = useMutation({
    mutationFn: (direction: 1 | -1) => {
      if (!managing) throw new Error('Choose a user.');
      const amount = Number(coinAmount);
      if (!Number.isInteger(amount) || amount < 1) throw new Error('Enter a whole number of coins.');
      return apiRequest(`/wallets/${managing.id}/adjust`, {
        method: 'POST',
        headers: { 'Idempotency-Key': crypto.randomUUID() },
        body: JSON.stringify({ amount: direction * amount, bonus_amount: 0, reason }),
      });
    },
    onSuccess: async () => { setMoneyNotice('Coin balance updated.'); await refreshMoney(); },
  });
  const grantPremium = useMutation({
    mutationFn: () => {
      if (!managing) throw new Error('Choose a user.');
      const selectedPlan = planId || plans.data?.find((plan) => plan.active)?.id;
      if (!selectedPlan) throw new Error('Activate or create a Premium plan first.');
      return apiRequest(`/users/${managing.id}/premium`, {
        method: 'POST',
        body: JSON.stringify({ plan_id: selectedPlan, days: Number(premiumDays), reason }),
      });
    },
    onSuccess: async () => { setMoneyNotice('Premium access assigned.'); await refreshMoney(); },
  });
  const revokePremium = useMutation({
    mutationFn: () => {
      if (!managing) throw new Error('Choose a user.');
      return apiRequest(`/users/${managing.id}/premium/revoke`, {
        method: 'POST', body: JSON.stringify({ reason }),
      });
    },
    onSuccess: async () => { setMoneyNotice('Admin Premium access removed.'); await refreshMoney(); },
  });
  const meta = users.data?.meta as PageMeta | undefined;

  return (
    <div className="page">
      <PageHeading
        eyebrow="Audience control"
        title="Users"
        description="Search accounts, review access and apply audited status or role changes."
      />
      <section className="panel">
        <div className="toolbar">
          <input
            className="field"
            placeholder="Search name or email…"
            value={q}
            onChange={(event) => { setQ(event.target.value); setPage(1); }}
          />
          <select className="select" value={status} onChange={(event) => setStatus(event.target.value)}>
            <option value="">All statuses</option>
            <option value="active">Active</option>
            <option value="suspended">Suspended</option>
            <option value="banned">Banned</option>
          </select>
          {updateStatus.error || updateRole.error ? (
            <span className="form-error">{(updateStatus.error ?? updateRole.error)?.message}</span>
          ) : null}
        </div>
        <QueryState
          loading={users.isLoading}
          error={users.error}
          empty={users.data?.data.length === 0}
        >
          <div className="table-wrap">
            <table className="data-table">
              <thead>
                <tr><th>User</th><th>Role</th><th>Status</th><th>Devices</th><th>Joined</th><th>Actions</th></tr>
              </thead>
              <tbody>
                {users.data?.data.map((user) => {
                  const protectedAccount = user.roles.includes('super_admin');
                  return (
                    <tr key={user.id}>
                      <td className="primary-cell">
                        <strong>{user.name}</strong><small>{user.email}</small>
                      </td>
                      <td>
                        {protectedAccount ? (
                          <Badge tone="accent">super_admin</Badge>
                        ) : (
                          <select
                            className="select"
                            style={{ minHeight: 34, minWidth: 145 }}
                            value={user.roles[0] ?? 'user'}
                            onChange={(event) =>
                              updateRole.mutate({ id: user.id, role: event.target.value })
                            }
                          >
                            {roles.data?.map((role) => <option key={role.id}>{role.name}</option>)}
                          </select>
                        )}
                      </td>
                      <td><Badge tone={tone(user.status)}>{user.status}</Badge></td>
                      <td>{user.devices ?? 0}</td>
                      <td>{formatDate(user.created_at)}</td>
                      <td>
                        <div className="actions">
                          {!protectedAccount && user.status === 'active' ? (
                            <button
                              className="button button-danger"
                              onClick={() =>
                                window.confirm(`Suspend ${user.email}?`) &&
                                updateStatus.mutate({ id: user.id, next: 'suspended' })
                              }
                            >Suspend</button>
                          ) : null}
                          {!protectedAccount && user.status !== 'active' ? (
                            <button
                              className="button button-quiet"
                              onClick={() => updateStatus.mutate({ id: user.id, next: 'active' })}
                            >Restore</button>
                          ) : null}
                          <button className="button button-accent" onClick={() => { setManaging(user); setMoneyNotice(''); }}>Coins &amp; Premium</button>
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </QueryState>
        {managing ? (
          <div className="account-money-panel">
            <div className="panel-header"><div><h3>Coins &amp; Premium</h3><p>{managing.name} · {managing.email}</p></div><button className="button button-quiet" onClick={() => setManaging(null)}>Close</button></div>
            <QueryState loading={monetization.isLoading} error={monetization.error}>
              {monetization.data ? (
                <div className="account-money-grid">
                  <div className="money-card">
                    <span>Coin balance</span><strong>{monetization.data.wallet.total_balance.toLocaleString()}</strong>
                    <div className="form-field"><label>Amount</label><input className="field" type="number" min="1" step="1" value={coinAmount} onChange={(event) => setCoinAmount(event.target.value)} /></div>
                    <div className="actions"><button className="button button-primary" disabled={adjustCoins.isPending} onClick={() => adjustCoins.mutate(1)}>+ Add coins</button><button className="button button-danger" disabled={adjustCoins.isPending} onClick={() => adjustCoins.mutate(-1)}>− Remove coins</button></div>
                  </div>
                  <div className="money-card">
                    <span>Premium access</span><strong>{monetization.data.subscription ? monetization.data.subscription.plan.name : 'Not active'}</strong>
                    {monetization.data.subscription ? <small>{monetization.data.subscription.provider} · ends {formatDate(monetization.data.subscription.current_period_end)}</small> : null}
                    <div className="form-field"><label>Plan</label><select className="select" value={planId || plans.data?.find((plan) => plan.active)?.id || ''} onChange={(event) => setPlanId(event.target.value)}>{plans.data?.filter((plan) => plan.active).map((plan) => <option key={plan.id} value={plan.id}>{plan.name} · {plan.interval}</option>)}</select></div>
                    <div className="form-field"><label>Days</label><input className="field" type="number" min="1" max="3650" value={premiumDays} onChange={(event) => setPremiumDays(event.target.value)} /></div>
                    <div className="actions"><button className="button button-primary" disabled={grantPremium.isPending} onClick={() => grantPremium.mutate()}>Give Premium</button>{monetization.data.subscription?.provider === 'admin_grant' ? <button className="button button-danger" disabled={revokePremium.isPending} onClick={() => window.confirm(`Remove Premium from ${managing.email}?`) && revokePremium.mutate()}>Remove Premium</button> : null}</div>
                  </div>
                </div>
              ) : null}
            </QueryState>
            <div className="form-field"><label>Audit reason</label><input className="field" value={reason} onChange={(event) => setReason(event.target.value)} /></div>
            {moneyNotice ? <div className="notice success">{moneyNotice}</div> : null}
            {adjustCoins.error || grantPremium.error || revokePremium.error ? <div className="notice">{(adjustCoins.error ?? grantPremium.error ?? revokePremium.error)?.message}</div> : null}
          </div>
        ) : null}
        {meta && meta.pages > 1 ? (
          <div className="toolbar" style={{ margin: '18px 0 0', justifyContent: 'flex-end' }}>
            <button className="button button-quiet" disabled={page <= 1} onClick={() => setPage((p) => p - 1)}>Previous</button>
            <span style={{ color: 'var(--muted)', fontSize: 12 }}>Page {page} of {meta.pages}</span>
            <button className="button button-quiet" disabled={page >= meta.pages} onClick={() => setPage((p) => p + 1)}>Next</button>
          </div>
        ) : null}
      </section>
    </div>
  );
}
