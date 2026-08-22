import { NextRequest } from 'next/server';

import { forwardWithAdminSession } from '@/lib/server-proxy';

type RouteContext = { params: Promise<{ path: string[] }> };

async function forward(request: NextRequest, context: RouteContext) {
  const { path } = await context.params;
  return forwardWithAdminSession(request, `/admin/${path.join('/')}`);
}

export const GET = forward;
export const POST = forward;
export const PATCH = forward;
export const PUT = forward;
export const DELETE = forward;
