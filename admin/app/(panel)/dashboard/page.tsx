'use client';

import { useQuery } from '@tanstack/react-query';

import { PageHeading, QueryState, StatCard } from '@/components/ui';
import { apiRequest, formatDate, formatMoney } from '@/lib/api';

type DashboardData = {
  cards: {
    users_total: number;
    users_new_30d: number;
    active_subscriptions: number;
    published_content: number;
    gross_revenue: string;
    net_revenue: string;
    open_reports: number;
    comments_under_review: number;
  };
  warnings: Record<string, number>;
  user_growth: { date: string; users: number }[];
  recent_payments: {
    id: string;
    amount: string;
    currency: string;
    status: string;
    provider: string;
    created_at: string;
  }[];
};

export default function DashboardPage() {
  const query = useQuery({
    queryKey: ['dashboard'],
    queryFn: async () => (await apiRequest<DashboardData>('/dashboard')).data,
  });
  const data = query.data;
  const maxUsers = Math.max(1, ...(data?.user_growth.map((point) => point.users) ?? [1]));

  return (
    <div className="page">
      <PageHeading
        eyebrow="Live operations"
        title="Platform overview"
        description="The health, audience and revenue signals that need your attention right now."
      />
      <QueryState loading={query.isLoading} error={query.error}>
        {data ? (
          <>
            <section className="grid-stats">
              <StatCard
                label="Total users"
                value={data.cards.users_total.toLocaleString()}
                detail={`+${data.cards.users_new_30d} in the last 30 days`}
                color="#8b5cf6"
              />
              <StatCard
                label="Active premium"
                value={data.cards.active_subscriptions.toLocaleString()}
                detail="Trialing and active subscriptions"
                color="#ff3d71"
              />
              <StatCard
                label="Published titles"
                value={data.cards.published_content.toLocaleString()}
                detail="Public catalog inventory"
                color="#22c55e"
              />
              <StatCard
                label="Net revenue"
                value={formatMoney(data.cards.net_revenue)}
                detail={`Gross ${formatMoney(data.cards.gross_revenue)}`}
                color="#f59e0b"
              />
            </section>
            <section className="content-grid">
              <article className="panel">
                <div className="panel-header">
                  <div>
                    <h3>New user momentum</h3>
                    <p>Registrations across the last 14 days</p>
                  </div>
                </div>
                <div
                  style={{ height: 220, display: 'flex', alignItems: 'end', gap: 7, paddingTop: 18 }}
                  aria-label="New users chart"
                >
                  {data.user_growth.map((point) => (
                    <div
                      key={point.date}
                      title={`${point.date}: ${point.users}`}
                      style={{ flex: 1, display: 'grid', alignItems: 'end', height: '100%' }}
                    >
                      <div
                        style={{
                          minHeight: 4,
                          height: `${Math.max(3, (point.users / maxUsers) * 100)}%`,
                          borderRadius: 8,
                          background: 'linear-gradient(180deg,#ff3d8d,#7c3aed)',
                          opacity: point.users ? 1 : 0.22,
                        }}
                      />
                    </div>
                  ))}
                </div>
              </article>
              <article className="panel">
                <div className="panel-header">
                  <div>
                    <h3>Needs attention</h3>
                    <p>Operational warnings from live data</p>
                  </div>
                </div>
                <div className="warning-list">
                  {Object.entries(data.warnings).map(([key, value]) => (
                    <div className="warning-row" key={key}>
                      <span>{key.replaceAll('_', ' ')}</span>
                      <strong>{value}</strong>
                    </div>
                  ))}
                </div>
              </article>
            </section>
            <section className="panel" style={{ marginTop: 16 }}>
              <div className="panel-header">
                <div>
                  <h3>Recent payments</h3>
                  <p>Latest checkout and purchase records</p>
                </div>
              </div>
              <div className="table-wrap">
                <table className="data-table">
                  <thead>
                    <tr><th>Reference</th><th>Provider</th><th>Status</th><th>Amount</th><th>Date</th></tr>
                  </thead>
                  <tbody>
                    {data.recent_payments.map((payment) => (
                      <tr key={payment.id}>
                        <td>{payment.id.slice(0, 8)}</td>
                        <td>{payment.provider}</td>
                        <td><span className="badge">{payment.status}</span></td>
                        <td>{formatMoney(payment.amount, payment.currency)}</td>
                        <td>{formatDate(payment.created_at)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </section>
          </>
        ) : null}
      </QueryState>
    </div>
  );
}
