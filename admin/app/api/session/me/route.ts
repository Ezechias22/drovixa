import { NextRequest } from 'next/server';

import { forwardWithAdminSession } from '@/lib/server-proxy';

export async function GET(request: NextRequest) {
  return forwardWithAdminSession(request, '/users/me');
}
