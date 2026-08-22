import { NextRequest, NextResponse } from 'next/server';

import { attachSessionCookies, backendBaseUrl } from '@/lib/server-proxy';

const STAFF_ROLES = new Set([
  'moderator',
  'content_manager',
  'support_agent',
  'finance_admin',
  'admin',
  'super_admin',
]);

type LoginResponse = {
  success: boolean;
  data?: {
    access_token: string;
    refresh_token: string;
    expires_in: number;
    user: { id: string; email: string; name: string; roles: string[] };
  };
  error?: { code: string; message: string };
};

export async function POST(request: NextRequest) {
  try {
    const credentials = (await request.json()) as { email?: string; password?: string };
    const upstream = await fetch(`${backendBaseUrl()}/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        email: credentials.email,
        password: credentials.password,
        device: {
          device_id: `admin-web-${crypto.randomUUID()}`,
          name: 'Drovixa Admin Web',
          platform: 'web',
        },
      }),
      cache: 'no-store',
    });
    const payload = (await upstream.json()) as LoginResponse;
    if (!upstream.ok || !payload.data) {
      return NextResponse.json(payload, { status: upstream.status });
    }
    if (!payload.data.user.roles.some((role) => STAFF_ROLES.has(role))) {
      return NextResponse.json(
        {
          success: false,
          error: { code: 'FORBIDDEN', message: 'This account has no admin permissions.' },
        },
        { status: 403 },
      );
    }
    const response = NextResponse.json({ success: true, data: { user: payload.data.user } });
    attachSessionCookies(response, payload.data);
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
