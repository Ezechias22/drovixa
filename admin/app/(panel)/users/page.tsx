'use client';

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';

import { Badge, PageHeading, QueryState } from '@/components/ui';
import { apiRequest, formatDate } from '@/lib/api';
import type { AdminUser, PageMeta } from '@/lib/types';

type Role = { id: string; name: string; description: string; permissions: string[] };

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
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </QueryState>
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
