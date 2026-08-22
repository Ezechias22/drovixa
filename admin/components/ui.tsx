import type { ReactNode } from 'react';

export function PageHeading({
  eyebrow,
  title,
  description,
  action,
}: {
  eyebrow: string;
  title: string;
  description: string;
  action?: ReactNode;
}) {
  return (
    <div className="page-heading">
      <div>
        <div className="eyebrow">{eyebrow}</div>
        <h2>{title}</h2>
        <p>{description}</p>
      </div>
      {action}
    </div>
  );
}

export function StatCard({
  label,
  value,
  detail,
  color,
}: {
  label: string;
  value: ReactNode;
  detail?: string;
  color?: string;
}) {
  return (
    <article className="stat-card" style={{ '--stat-color': color } as React.CSSProperties}>
      <span>{label}</span>
      <strong>{value}</strong>
      {detail ? <small>{detail}</small> : null}
    </article>
  );
}

export function Badge({ children, tone = '' }: { children: ReactNode; tone?: string }) {
  return <span className={`badge ${tone}`}>{children}</span>;
}

export function QueryState({
  loading,
  error,
  empty,
  children,
}: {
  loading: boolean;
  error?: Error | null;
  empty?: boolean;
  children: ReactNode;
}) {
  if (loading)
    return (
      <div style={{ display: 'grid', gap: 10 }}>
        {[1, 2, 3, 4].map((item) => (
          <div key={item} className="skeleton" style={{ height: 58 }} />
        ))}
      </div>
    );
  if (error)
    return (
      <div className="empty-state">
        <div>
          <strong>Could not load this area</strong>
          <span>{error.message}</span>
        </div>
      </div>
    );
  if (empty)
    return (
      <div className="empty-state">
        <div>
          <strong>Nothing here yet</strong>
          <span>New records will appear here automatically.</span>
        </div>
      </div>
    );
  return children;
}
