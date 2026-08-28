import { cookies } from 'next/headers';
import { NextRequest, NextResponse } from 'next/server';

const ACCESS_COOKIE = 'drovixa_admin_access';
const REFRESH_COOKIE = 'drovixa_admin_refresh';

type TokenPayload = {
  access_token: string;
  refresh_token: string;
  expires_in: number;
};

export function backendBaseUrl(): string {
  if (process.env.BACKEND_HOSTPORT) {
    return `http://${process.env.BACKEND_HOSTPORT}/api/v1`;
  }
  return (
    process.env.INTERNAL_API_URL ??
    process.env.NEXT_PUBLIC_API_URL ??
    'http://localhost:8000/api/v1'
  ).replace(/\/$/, '');
}

function setSessionCookies(response: NextResponse, tokens: TokenPayload) {
  const secure = process.env.ADMIN_COOKIE_SECURE === 'true';
  response.cookies.set(ACCESS_COOKIE, tokens.access_token, {
    httpOnly: true,
    sameSite: 'lax',
    secure,
    path: '/',
    maxAge: tokens.expires_in,
  });
  response.cookies.set(REFRESH_COOKIE, tokens.refresh_token, {
    httpOnly: true,
    sameSite: 'lax',
    secure,
    path: '/',
    maxAge: 60 * 24 * 60 * 60,
  });
}

export function clearSessionCookies(response: NextResponse) {
  response.cookies.delete(ACCESS_COOKIE);
  response.cookies.delete(REFRESH_COOKIE);
}

export function attachSessionCookies(response: NextResponse, tokens: TokenPayload) {
  setSessionCookies(response, tokens);
}

async function refreshSession(refreshToken: string): Promise<TokenPayload | null> {
  const response = await fetch(`${backendBaseUrl()}/auth/refresh`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ refresh_token: refreshToken }),
    cache: 'no-store',
  });
  if (!response.ok) return null;
  const payload = (await response.json()) as { data?: TokenPayload };
  return payload.data ?? null;
}

function unauthorizedResponse() {
  return NextResponse.json(
    { success: false, error: { code: 'UNAUTHORIZED', message: 'Admin session required.' } },
    { status: 401 },
  );
}

export async function forwardWithAdminSession(
  request: NextRequest,
  backendPath: string,
): Promise<NextResponse> {
  const cookieStore = await cookies();
  let accessToken = cookieStore.get(ACCESS_COOKIE)?.value;
  const refreshToken = cookieStore.get(REFRESH_COOKIE)?.value;
  if (!accessToken && !refreshToken) return unauthorizedResponse();

  const requestBody = ['GET', 'HEAD'].includes(request.method)
    ? undefined
    : new Uint8Array(await request.arrayBuffer());
  const query = new URL(request.url).search;
  const publicApiOrigin = (process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000/api/v1')
    .replace(/\/api\/v1\/?$/, '')
    .replace(/\/$/, '');
  const callBackend = (token: string) =>
    fetch(`${backendBaseUrl()}${backendPath}${query}`, {
      method: request.method,
      headers: {
        Authorization: `Bearer ${token}`,
        'X-Public-API-Origin': publicApiOrigin,
        ...(request.headers.get('content-type')
          ? { 'Content-Type': request.headers.get('content-type') as string }
          : {}),
        ...(request.headers.get('idempotency-key')
          ? { 'Idempotency-Key': request.headers.get('idempotency-key') as string }
          : {}),
      },
      body: requestBody,
      cache: 'no-store',
    });

  try {
    let refreshed: TokenPayload | null = null;
    let upstream = accessToken ? await callBackend(accessToken) : null;
    if ((!upstream || upstream.status === 401) && refreshToken) {
      refreshed = await refreshSession(refreshToken);
      if (refreshed) {
        accessToken = refreshed.access_token;
        upstream = await callBackend(accessToken);
      }
    }
    if (!upstream) return unauthorizedResponse();
    const response = new NextResponse(await upstream.arrayBuffer(), {
      status: upstream.status,
      headers: {
        'Content-Type': upstream.headers.get('content-type') ?? 'application/json',
        'Cache-Control': 'no-store',
      },
    });
    if (refreshed) setSessionCookies(response, refreshed);
    if (upstream.status === 401) clearSessionCookies(response);
    return response;
  } catch {
    return NextResponse.json(
      {
        success: false,
        error: { code: 'API_UNAVAILABLE', message: 'Cannot reach the Drovixa API.' },
      },
      { status: 503 },
    );
  }
}
