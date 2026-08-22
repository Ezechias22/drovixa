export type ApiErrorPayload = { code?: string; message?: string; details?: unknown };
export type ApiEnvelope<T> = { success: true; data: T; meta?: Record<string, unknown> };

export class AdminApiError extends Error {
  code: string;
  details?: unknown;

  constructor(status: number, payload?: ApiErrorPayload) {
    super(payload?.message ?? `Request failed (${status})`);
    this.name = 'AdminApiError';
    this.code = payload?.code ?? 'REQUEST_FAILED';
    this.details = payload?.details;
  }
}

export async function apiRequest<T>(path: string, init?: RequestInit): Promise<ApiEnvelope<T>> {
  const response = await fetch(`/api/admin${path}`, {
    ...init,
    headers: {
      ...(init?.body ? { 'Content-Type': 'application/json' } : {}),
      ...(init?.headers ?? {}),
    },
    cache: 'no-store',
  });
  const payload = (await response.json().catch(() => ({}))) as {
    success?: boolean;
    data?: T;
    meta?: Record<string, unknown>;
    error?: ApiErrorPayload;
  };
  if (!response.ok || !payload.success) throw new AdminApiError(response.status, payload.error);
  return payload as ApiEnvelope<T>;
}

export async function sessionRequest<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`/api/session${path}`, {
    ...init,
    headers: {
      ...(init?.body ? { 'Content-Type': 'application/json' } : {}),
      ...(init?.headers ?? {}),
    },
    cache: 'no-store',
  });
  const payload = (await response.json().catch(() => ({}))) as {
    success?: boolean;
    data?: T;
    error?: ApiErrorPayload;
  };
  if (!response.ok || !payload.success || payload.data === undefined) {
    throw new AdminApiError(response.status, payload.error);
  }
  return payload.data;
}

export function formatMoney(value: string | number, currency = 'USD') {
  return new Intl.NumberFormat('en-US', { style: 'currency', currency }).format(Number(value));
}

export function formatDate(value?: string | null) {
  if (!value) return '—';
  return new Intl.DateTimeFormat('en', { dateStyle: 'medium', timeStyle: 'short' }).format(
    new Date(value),
  );
}
