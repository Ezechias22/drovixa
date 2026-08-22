import { NextRequest, NextResponse } from 'next/server';

type RouteContext = { params: Promise<{ path: string[] }> };

function backendBaseUrl() {
  if (process.env.BACKEND_HOSTPORT) {
    return `http://${process.env.BACKEND_HOSTPORT}/api/v1`;
  }
  return (process.env.INTERNAL_API_URL ?? 'http://localhost:8000/api/v1').replace(/\/$/, '');
}

async function forward(request: NextRequest, context: RouteContext) {
  const { path } = await context.params;
  const query = new URL(request.url).search;
  const body = ['GET', 'HEAD'].includes(request.method)
    ? undefined
    : new Uint8Array(await request.arrayBuffer());
  try {
    const upstream = await fetch(`${backendBaseUrl()}/${path.join('/')}${query}`, {
      method: request.method,
      headers: {
        ...(request.headers.get('authorization')
          ? { Authorization: request.headers.get('authorization') as string }
          : {}),
        ...(request.headers.get('content-type')
          ? { 'Content-Type': request.headers.get('content-type') as string }
          : {}),
        ...(request.headers.get('idempotency-key')
          ? { 'Idempotency-Key': request.headers.get('idempotency-key') as string }
          : {}),
      },
      body,
      cache: 'no-store',
    });
    return new NextResponse(await upstream.arrayBuffer(), {
      status: upstream.status,
      headers: {
        'Content-Type': upstream.headers.get('content-type') ?? 'application/json',
        'Cache-Control': 'no-store',
      },
    });
  } catch {
    return NextResponse.json(
      { success: false, error: { code: 'API_UNAVAILABLE', message: 'Cannot reach Drovixa.' } },
      { status: 503 },
    );
  }
}

export const GET = forward;
export const POST = forward;
export const PATCH = forward;
export const PUT = forward;
export const DELETE = forward;
