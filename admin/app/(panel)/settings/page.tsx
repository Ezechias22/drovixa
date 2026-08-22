'use client';

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useEffect, useState } from 'react';

import { Badge, PageHeading, QueryState } from '@/components/ui';
import { apiRequest, formatDate } from '@/lib/api';
import type { RemoteConfig } from '@/lib/types';

function ConfigRow({ item }: { item: RemoteConfig }) {
  const client = useQueryClient();
  const [value, setValue] = useState(JSON.stringify(item.value));
  useEffect(() => setValue(JSON.stringify(item.value)), [item.value]);
  const save = useMutation({
    mutationFn: async () => {
      let parsed: unknown;
      try { parsed = JSON.parse(value); } catch { throw new Error('Value must be valid JSON. Strings need double quotes.'); }
      return apiRequest(`/remote-config/${item.key}`, { method: 'PATCH', body: JSON.stringify({ value: parsed, is_public: item.is_public }) });
    },
    onSuccess: () => client.invalidateQueries({ queryKey: ['remote-config'] }),
  });
  return <tr>
    <td className="primary-cell"><strong>{item.key.replaceAll('_', ' ')}</strong><small>{item.description}</small></td>
    <td style={{ minWidth: 300 }}><input className="field" value={value} onChange={(event) => setValue(event.target.value)} /></td>
    <td><Badge tone={item.is_public ? 'success' : 'warning'}>{item.is_public ? 'public' : 'private'}</Badge></td>
    <td>{formatDate(item.updated_at)}</td>
    <td><button className="button button-primary" disabled={save.isPending || value === JSON.stringify(item.value)} onClick={() => save.mutate()}>{save.isPending ? 'Saving…' : 'Save'}</button>{save.error ? <small className="form-error" style={{ display: 'block', marginTop: 5 }}>{save.error.message}</small> : null}</td>
  </tr>;
}

export default function SettingsPage() {
  const query = useQuery({
    queryKey: ['remote-config'],
    queryFn: async () => (await apiRequest<RemoteConfig[]>('/remote-config')).data,
  });
  return <div className="page">
    <PageHeading eyebrow="Remote configuration" title="Platform settings" description="Change public runtime values such as accent color, versions, policies and playback defaults without an app update." />
    <section className="panel">
      <div className="notice" style={{ marginBottom: 16 }}>Enter valid JSON values. For example, text must look like <code>"#FF3D71"</code>, while numbers and booleans do not use quotes.</div>
      <QueryState loading={query.isLoading} error={query.error} empty={query.data?.length === 0}>
        <div className="table-wrap"><table className="data-table"><thead><tr><th>Setting</th><th>JSON value</th><th>Visibility</th><th>Updated</th><th>Action</th></tr></thead><tbody>{query.data?.map((item) => <ConfigRow key={item.key} item={item} />)}</tbody></table></div>
      </QueryState>
    </section>
  </div>;
}
