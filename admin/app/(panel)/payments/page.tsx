'use client';

import { useQuery } from '@tanstack/react-query';

import { Badge, PageHeading, QueryState } from '@/components/ui';
import { apiRequest, formatDate, formatMoney } from '@/lib/api';

type Payment = { id: string; user_id: string; provider: string; provider_transaction_id?: string | null; product_type: string; product_id: string; currency: string; amount: string; status: string; platform: string; country?: string | null; created_at: string };
function tone(status: string) { if (status === 'paid') return 'success'; if (['failed', 'cancelled'].includes(status)) return 'danger'; if (status.includes('refund')) return 'warning'; return 'accent'; }

export default function PaymentsPage() {
  const query = useQuery({ queryKey: ['payments'], queryFn: () => apiRequest<Payment[]>('/payments?page=1&limit=100') });
  return <div className="page">
    <PageHeading eyebrow="Financial ledger" title="Payments" description="Backend-authoritative payment records. Provider events and idempotency protect every financial transition." />
    <section className="panel">
      <QueryState loading={query.isLoading} error={query.error} empty={query.data?.data.length === 0}>
        <div className="table-wrap"><table className="data-table"><thead><tr><th>Payment</th><th>User</th><th>Product</th><th>Provider</th><th>Status</th><th>Amount</th><th>Date</th></tr></thead><tbody>{query.data?.data.map((payment) => <tr key={payment.id}><td className="primary-cell"><strong>{payment.id.slice(0, 12)}</strong><small>{payment.provider_transaction_id ?? 'Awaiting provider reference'}</small></td><td>{payment.user_id.slice(0, 8)}</td><td><Badge>{payment.product_type}</Badge></td><td>{payment.provider} · {payment.platform}</td><td><Badge tone={tone(payment.status)}>{payment.status}</Badge></td><td>{formatMoney(payment.amount, payment.currency)}</td><td>{formatDate(payment.created_at)}</td></tr>)}</tbody></table></div>
      </QueryState>
    </section>
  </div>;
}
