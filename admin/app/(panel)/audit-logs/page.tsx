'use client';

import { useQuery } from '@tanstack/react-query';
import { useState } from 'react';

import { Badge, PageHeading, QueryState } from '@/components/ui';
import { apiRequest, formatDate } from '@/lib/api';
import type { PageMeta } from '@/lib/types';

type AuditLog = {
  id: string;
  admin_id: string | null;
  action: string;
  entity_type: string;
  entity_id: string;
  old_value: Record<string, unknown> | null;
  new_value: Record<string, unknown> | null;
  ip: string | null;
  user_agent: string | null;
  created_at: string;
};

export default function AuditLogsPage() {
  const [action, setAction] = useState('');
  const [entityType, setEntityType] = useState('');
  const [page, setPage] = useState(1);
  const query = useQuery({
    queryKey: ['audit-logs', action, entityType, page],
    queryFn: async () => {
      const parameters = new URLSearchParams({ page: String(page), limit: '25' });
      if (action.trim()) parameters.set('action', action.trim());
      if (entityType) parameters.set('entity_type', entityType);
      return apiRequest<AuditLog[]>(`/audit-logs?${parameters.toString()}`);
    },
  });

  const meta = query.data?.meta as PageMeta | undefined;

  return (
    <div className="page">
      <PageHeading
        eyebrow="Security and accountability"
        title="Audit logs"
        description="Review immutable administrative activity, before-and-after values, IP addresses and request clients."
      />
      <section className="panel">
        <div className="toolbar">
          <input
            className="field"
            value={action}
            placeholder="Filter actions…"
            onChange={(event) => {
              setAction(event.target.value);
              setPage(1);
            }}
          />
          <select
            className="select"
            value={entityType}
            onChange={(event) => {
              setEntityType(event.target.value);
              setPage(1);
            }}
          >
            <option value="">All entities</option>
            <option value="user">Users</option>
            <option value="content">Content</option>
            <option value="homepage_section">Homepage</option>
            <option value="notification_campaign">Campaigns</option>
            <option value="feature_flag">Feature flags</option>
            <option value="remote_config">Remote config</option>
            <option value="comment">Comments</option>
            <option value="report">Reports</option>
            <option value="wallet">Wallet</option>
          </select>
        </div>
        <QueryState
          loading={query.isLoading}
          error={query.error}
          empty={query.data?.data.length === 0}
        >
          <div className="table-wrap">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Action</th>
                  <th>Entity</th>
                  <th>Administrator</th>
                  <th>Origin</th>
                  <th>Changes</th>
                  <th>Date</th>
                </tr>
              </thead>
              <tbody>
                {query.data?.data.map((item) => (
                  <tr key={item.id}>
                    <td className="primary-cell">
                      <strong>{item.action}</strong>
                      <small>{item.id.slice(0, 12)}</small>
                    </td>
                    <td>
                      <Badge>{item.entity_type.replaceAll('_', ' ')}</Badge>
                      <div style={{ marginTop: 6, color: 'var(--muted)' }}>
                        {item.entity_id.slice(0, 18)}
                      </div>
                    </td>
                    <td>{item.admin_id?.slice(0, 12) ?? 'System'}</td>
                    <td className="primary-cell">
                      <strong>{item.ip ?? 'Unknown IP'}</strong>
                      <small>{item.user_agent?.slice(0, 42) ?? 'No user agent'}</small>
                    </td>
                    <td>
                      <details className="audit-details">
                        <summary>Inspect snapshot</summary>
                        <pre>
                          {JSON.stringify(
                            { before: item.old_value, after: item.new_value },
                            null,
                            2,
                          )}
                        </pre>
                      </details>
                    </td>
                    <td>{formatDate(item.created_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </QueryState>
        {meta && meta.pages > 1 ? (
          <div className="toolbar" style={{ marginTop: 18, marginBottom: 0 }}>
            <button
              className="button button-quiet"
              disabled={page <= 1}
              onClick={() => setPage((value) => value - 1)}
            >
              Previous
            </button>
            <Badge>
              Page {meta.page} of {meta.pages}
            </Badge>
            <button
              className="button button-quiet"
              disabled={page >= meta.pages}
              onClick={() => setPage((value) => value + 1)}
            >
              Next
            </button>
          </div>
        ) : null}
      </section>
    </div>
  );
}
