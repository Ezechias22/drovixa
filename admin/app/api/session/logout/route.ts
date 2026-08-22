import { NextRequest, NextResponse } from 'next/server';

import { clearSessionCookies, forwardWithAdminSession } from '@/lib/server-proxy';

export async function POST(request: NextRequest) {
  await forwardWithAdminSession(request, '/auth/logout');
  const response = NextResponse.json({ success: true, data: { logged_out: true } });
  clearSessionCookies(response);
  return response;
}
