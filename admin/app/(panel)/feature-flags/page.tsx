'use client';

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { Badge, PageHeading, QueryState } from '@/components/ui';
import { apiRequest, formatDate } from '@/lib/api';
import type { FeatureFlag } from '@/lib/types';

export default function FeatureFlagsPage() {
  const client = useQueryClient();
  const query = useQuery({
    queryKey: ['feature-flags'],
    queryFn: async () => (await apiRequest<FeatureFlag[]>('/feature-flags')).data,
  });
  const update = useMutation({
    mutationFn: ({ key, enabled }: { key: string; enabled: boolean }) =>
      apiRequest(`/feature-flags/${key}`, {
        method: 'PATCH',
        body: JSON.stringify({ enabled, rollout_percentage: 100 }),
      }),
    onSuccess: () => client.invalidateQueries({ queryKey: ['feature-flags'] }),
  });
  const toggle = (flag: FeatureFlag) => {
    if (
      flag.key === 'maintenance_mode' &&
      !flag.enabled &&
      !window.confirm('Maintenance mode can block viewers. Activate it now?')
    ) return;
    update.mutate({ key: flag.key, enabled: !flag.enabled });
  };

  return (
    <div className="page">
      <PageHeading eyebrow="Runtime control" title="Feature flags" description="Release or stop platform capabilities instantly, with audited changes and cache invalidation." />
      <section className="panel">
        {update.error ? <div className="notice" style={{ marginBottom: 14 }}>{update.error.message}</div> : null}
        <QueryState loading={query.isLoading} error={query.error} empty={query.data?.length === 0}>
          <div className="table-wrap"><table className="data-table">
            <thead><tr><th>Feature</th><th>State</th><th>Rollout</th><th>Updated</th><th>Control</th></tr></thead>
            <tbody>{query.data?.map((flag) => <tr key={flag.key}>
              <td className="primary-cell"><strong>{flag.key.replaceAll('_', ' ')}</strong><small>{flag.description}</small></td>
              <td><Badge tone={flag.enabled ? 'success' : 'danger'}>{flag.enabled ? 'enabled' : 'disabled'}</Badge></td>
              <td>{flag.rollout_percentage}%</td>
              <td>{formatDate(flag.updated_at)}</td>
              <td><button className={`toggle ${flag.enabled ? 'on' : ''}`} aria-label={`Toggle ${flag.key}`} disabled={update.isPending} onClick={() => toggle(flag)} /></td>
            </tr>)}</tbody>
          </table></div>
        </QueryState>
      </section>
    </div>
  );
}
