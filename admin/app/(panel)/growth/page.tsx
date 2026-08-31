'use client';

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useEffect, useState } from 'react';

import { PageHeading, QueryState, StatCard } from '@/components/ui';
import { apiRequest } from '@/lib/api';

type Summary = {
  daily_claims: number;
  qualified_referrals: number;
  active_watch_parties: number;
  ad_completions: number;
  ad_impressions: number;
};

type Ad = { id: string; name: string; placement: string; format: string; daily_cap: number; active: boolean };
type Automation = { id: string; name: string; trigger_event: string; cooldown_hours: number; active: boolean };
type EngagementConfig = {
  rewarded_ads_enabled: boolean;
  premium_offers_enabled: boolean;
  content_notifications_enabled: boolean;
  continue_watching_reminders_enabled: boolean;
  coins_per_ad: number;
  daily_limit: number;
  max_per_session: number;
  max_per_day: number;
  first_delay_seconds: number;
  repeat_delay_seconds: number;
  premium_notification_cooldown_hours: number;
  continue_after_hours: number;
  continue_cooldown_hours: number;
};

export default function GrowthPage() {
  const client = useQueryClient();
  const [settings, setSettings] = useState<EngagementConfig | null>(null);
  const summary = useQuery({
    queryKey: ['growth-summary'],
    queryFn: async () => (await apiRequest<Summary>('/growth/summary')).data,
  });
  const ads = useQuery({
    queryKey: ['growth-ads'],
    queryFn: async () => (await apiRequest<Ad[]>('/growth/ads')).data,
  });
  const automations = useQuery({
    queryKey: ['growth-automations'],
    queryFn: async () => (await apiRequest<Automation[]>('/growth/automations')).data,
  });
  const engagement = useQuery({
    queryKey: ['growth-engagement-config'],
    queryFn: async () => (await apiRequest<EngagementConfig>('/growth/config')).data,
  });
  useEffect(() => {
    if (engagement.data) setSettings(engagement.data);
  }, [engagement.data]);
  const saveSettings = useMutation({
    mutationFn: (value: EngagementConfig) => apiRequest<EngagementConfig>('/growth/config', {
      method: 'PATCH',
      body: JSON.stringify(value),
    }),
    onSuccess: (result) => {
      setSettings(result.data);
      client.setQueryData(['growth-engagement-config'], result.data);
    },
  });
  const toggle = useMutation({
    mutationFn: ({ id, active }: { id: string; active: boolean }) => apiRequest(`/growth/automations/${id}`, {
      method: 'PATCH',
      body: JSON.stringify({ active }),
    }),
    onSuccess: () => client.invalidateQueries({ queryKey: ['growth-automations'] }),
  });

  return (
    <div className="page">
      <PageHeading
        eyebrow="Audience growth"
        title="Growth & Watch Party"
        description="Ads, rewards, referrals, social acquisition and watch-together activity in one operational view."
      />
      <QueryState loading={summary.isLoading} error={summary.error}>
        {summary.data ? (
          <>
            <section className="grid-stats">
              <StatCard label="Daily claims" value={summary.data.daily_claims} detail="Coin streak rewards" color="#f59e0b" />
              <StatCard label="Qualified referrals" value={summary.data.qualified_referrals} detail="Rewarded invites" color="#22c55e" />
              <StatCard label="Watch Parties" value={summary.data.active_watch_parties} detail="Active rooms" color="#8b5cf6" />
              <StatCard label="Ad completions" value={summary.data.ad_completions} detail={`${summary.data.ad_impressions} impressions`} color="#ff3d71" />
            </section>
            <section className="content-grid">
              <article className="panel" style={{ gridColumn: '1 / -1' }}>
                <div className="panel-header"><div><h3>Ads, coins & reminders</h3><p>Keep offers useful, limited and controlled from one place.</p></div></div>
                {settings ? <form onSubmit={(event) => { event.preventDefault(); saveSettings.mutate(settings); }}>
                  <div className="form-grid">
                    <label className="check-row"><input type="checkbox" checked={settings.rewarded_ads_enabled} onChange={(event) => setSettings({ ...settings, rewarded_ads_enabled: event.target.checked })} /> Rewarded AdMob ads</label>
                    <label className="check-row"><input type="checkbox" checked={settings.premium_offers_enabled} onChange={(event) => setSettings({ ...settings, premium_offers_enabled: event.target.checked })} /> Premium offers</label>
                    <label className="check-row"><input type="checkbox" checked={settings.content_notifications_enabled} onChange={(event) => setSettings({ ...settings, content_notifications_enabled: event.target.checked })} /> New-content notifications</label>
                    <label className="check-row"><input type="checkbox" checked={settings.continue_watching_reminders_enabled} onChange={(event) => setSettings({ ...settings, continue_watching_reminders_enabled: event.target.checked })} /> Continue-watching reminders</label>
                    <label className="form-field">Coins per completed ad<input className="field" type="number" min={1} max={100} value={settings.coins_per_ad} onChange={(event) => setSettings({ ...settings, coins_per_ad: Number(event.target.value) })} /></label>
                    <label className="form-field">Ads per user / day<input className="field" type="number" min={1} max={25} value={settings.daily_limit} onChange={(event) => setSettings({ ...settings, daily_limit: Number(event.target.value) })} /></label>
                    <label className="form-field">Offers per app session<input className="field" type="number" min={0} max={3} value={settings.max_per_session} onChange={(event) => setSettings({ ...settings, max_per_session: Number(event.target.value) })} /></label>
                    <label className="form-field">Offers per user / day<input className="field" type="number" min={0} max={5} value={settings.max_per_day} onChange={(event) => setSettings({ ...settings, max_per_day: Number(event.target.value) })} /></label>
                    <label className="form-field">First offer after (seconds)<input className="field" type="number" min={30} max={3600} value={settings.first_delay_seconds} onChange={(event) => setSettings({ ...settings, first_delay_seconds: Number(event.target.value) })} /></label>
                    <label className="form-field">Repeat offer after (seconds)<input className="field" type="number" min={180} max={7200} value={settings.repeat_delay_seconds} onChange={(event) => setSettings({ ...settings, repeat_delay_seconds: Number(event.target.value) })} /></label>
                    <label className="form-field">Premium push cooldown (hours)<input className="field" type="number" min={24} max={168} value={settings.premium_notification_cooldown_hours} onChange={(event) => setSettings({ ...settings, premium_notification_cooldown_hours: Number(event.target.value) })} /></label>
                    <label className="form-field">Remind after inactivity (hours)<input className="field" type="number" min={6} max={168} value={settings.continue_after_hours} onChange={(event) => setSettings({ ...settings, continue_after_hours: Number(event.target.value) })} /></label>
                    <label className="form-field">Viewing reminder cooldown (hours)<input className="field" type="number" min={12} max={336} value={settings.continue_cooldown_hours} onChange={(event) => setSettings({ ...settings, continue_cooldown_hours: Number(event.target.value) })} /></label>
                  </div>
                  <button className="button button-accent" disabled={saveSettings.isPending} style={{ marginTop: 18 }} type="submit">{saveSettings.isPending ? 'Saving…' : 'Save engagement settings'}</button>
                  {saveSettings.isError ? <div className="notice" style={{ marginTop: 12 }}>{saveSettings.error.message}</div> : null}
                </form> : <p>Loading engagement settings…</p>}
              </article>
              <article className="panel">
                <div className="panel-header"><div><h3>Ad inventory</h3><p>Server-issued, capped delivery campaigns</p></div></div>
                <div className="warning-list">
                  {ads.data?.map((ad) => <div className="warning-row" key={ad.id}><span><strong>{ad.name}</strong><small style={{ display: 'block', opacity: 0.6 }}>{ad.placement} · {ad.format} · cap {ad.daily_cap}</small></span><span className="badge">{ad.active ? 'active' : 'paused'}</span></div>)}
                </div>
              </article>
              <article className="panel">
                <div className="panel-header"><div><h3>Growth automations</h3><p>Event-triggered in-app notifications</p></div></div>
                <div className="warning-list">
                  {automations.data?.map((row) => <div className="warning-row" key={row.id}><span><strong>{row.name}</strong><small style={{ display: 'block', opacity: 0.6 }}>{row.trigger_event} · {row.cooldown_hours}h cooldown</small></span><button className="secondary-button" onClick={() => toggle.mutate({ id: row.id, active: !row.active })}>{row.active ? 'Disable' : 'Enable'}</button></div>)}
                </div>
              </article>
            </section>
          </>
        ) : null}
      </QueryState>
    </div>
  );
}
