'use client';

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';

import { Badge, PageHeading, QueryState } from '@/components/ui';
import { apiRequest, formatMoney } from '@/lib/api';

type Package = { id: string; name: string; coins: number; bonus_coins: number; price: string; currency: string; platform: string; active: boolean; featured: boolean };
export default function CoinsPage() {
  const client = useQueryClient(); const [name, setName] = useState(''); const [coins, setCoins] = useState(''); const [price, setPrice] = useState('');
  const query = useQuery({ queryKey: ['coin-packages'], queryFn: async () => (await apiRequest<Package[]>('/coin-packages?page=1&limit=100')).data });
  const refresh = () => client.invalidateQueries({ queryKey: ['coin-packages'] });
  const create = useMutation({ mutationFn: () => apiRequest('/coin-packages', { method: 'POST', body: JSON.stringify({ name, coins: Number(coins), price: Number(price), bonus_coins: 0, currency: 'USD', platform: 'web' }) }), onSuccess: () => { setName(''); setCoins(''); setPrice(''); refresh(); } });
  const toggle = useMutation({ mutationFn: ({ id, active }: { id: string; active: boolean }) => apiRequest(`/coin-packages/${id}`, { method: 'PATCH', body: JSON.stringify({ active }) }), onSuccess: refresh });
  return <div className="page"><PageHeading eyebrow="Virtual economy" title="Coin packages" description="Create coin offers here. To add or remove coins from one person, open Users and choose Coins & Premium." /><section className="panel"><div className="toolbar"><input className="field" placeholder="Package name" value={name} onChange={(e) => setName(e.target.value)} /><input className="field" style={{ width: 120 }} placeholder="Coins" inputMode="numeric" value={coins} onChange={(e) => setCoins(e.target.value)} /><input className="field" style={{ width: 120 }} placeholder="USD price" inputMode="decimal" value={price} onChange={(e) => setPrice(e.target.value)} /><button className="button button-primary" disabled={!name || !Number(coins) || !Number(price) || create.isPending} onClick={() => create.mutate()}>Create package</button></div>{create.error || toggle.error ? <div className="notice">{(create.error ?? toggle.error)?.message}</div> : null}<QueryState loading={query.isLoading} error={query.error} empty={query.data?.length === 0}><div className="table-wrap"><table className="data-table"><thead><tr><th>Package</th><th>Coins</th><th>Price</th><th>Platform</th><th>Status</th><th>Action</th></tr></thead><tbody>{query.data?.map((item) => <tr key={item.id}><td className="primary-cell"><strong>{item.name}</strong><small>{item.featured ? 'Featured package' : 'Standard package'}</small></td><td>{item.coins.toLocaleString()} + {item.bonus_coins.toLocaleString()} bonus</td><td>{formatMoney(item.price, item.currency)}</td><td><Badge>{item.platform}</Badge></td><td><Badge tone={item.active ? 'success' : 'danger'}>{item.active ? 'active' : 'hidden'}</Badge></td><td><button className={`button ${item.active ? 'button-danger' : 'button-primary'}`} disabled={toggle.isPending} onClick={() => toggle.mutate({ id: item.id, active: !item.active })}>{item.active ? 'Hide package' : 'Activate package'}</button></td></tr>)}</tbody></table></div></QueryState></section></div>;
}
