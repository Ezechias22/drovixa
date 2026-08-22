'use client';

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';

import { apiClient } from '@/lib/api';

type Profile = { id: string; name: string; is_kids: boolean; age_limit: number; pin_protected: boolean; is_default: boolean };
type Envelope<T> = { success: true; data: T };

export default function ProfilesPage() {
  const client = useQueryClient();
  const [name, setName] = useState('');
  const profiles = useQuery({
    queryKey: ['profiles'],
    queryFn: async () => (await apiClient.get<Envelope<Profile[]>>('/profiles')).data.data,
  });
  const create = useMutation({
    mutationFn: async () => (await apiClient.post('/profiles', { name, is_kids: false, age_limit: 18, language_code: 'en' })).data,
    onSuccess: () => { setName(''); void client.invalidateQueries({ queryKey: ['profiles'] }); },
  });
  const active = typeof window === 'undefined' ? null : sessionStorage.getItem('drovixa.web.profile');
  const select = (id: string) => { sessionStorage.setItem('drovixa.web.profile', id); window.location.reload(); };
  return (
    <div className="mx-auto max-w-4xl px-5 py-14">
      <p className="text-xs font-black tracking-[.2em] text-[var(--accent)]">WHO IS WATCHING?</p>
      <h1 className="mt-2 text-4xl font-black">Profiles</h1>
      <div className="mt-8 grid grid-cols-2 gap-4 md:grid-cols-4">
        {profiles.data?.map((profile) => (
          <button key={profile.id} onClick={() => select(profile.id)} className={`rounded-3xl bg-[var(--card)] p-6 text-center ${active === profile.id ? 'ring-2 ring-[var(--accent)]' : ''}`}>
            <span className="mx-auto grid h-20 w-20 place-items-center rounded-2xl bg-violet-700 text-3xl font-black">{profile.name[0]}</span>
            <strong className="mt-4 block">{profile.name}</strong>
            <small className="text-[var(--muted)]">{profile.is_kids ? `Kids · ${profile.age_limit}+` : 'Standard'}</small>
          </button>
        ))}
      </div>
      <div className="mt-10 rounded-3xl bg-[var(--card)] p-6">
        <h2 className="text-xl font-black">Add profile</h2>
        <div className="mt-4 flex flex-col gap-3 sm:flex-row">
          <input value={name} onChange={(event) => setName(event.target.value)} placeholder="Profile name" className="min-h-12 flex-1 rounded-2xl bg-white/5 px-4 outline-none" />
          <button disabled={!name.trim() || create.isPending} onClick={() => create.mutate()} className="primary-button">{create.isPending ? 'Creating…' : 'Create profile'}</button>
        </div>
      </div>
    </div>
  );
}
