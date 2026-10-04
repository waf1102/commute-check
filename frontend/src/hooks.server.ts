import type { Handle } from '@sveltejs/kit';

export const handle: Handle = async ({ event, resolve }) => {
  // Proxy /api/* requests to the FastAPI backend
  if (event.url.pathname === '/api' || event.url.pathname.startsWith('/api/')) {
    const backendBase = (
      process.env.BACKEND_URL ||
      process.env.VITE_BACKEND_URL ||
      'http://127.0.0.1:8000'
    ).replace(/\/+$/, '');

    const targetUrl = `${backendBase}${event.url.pathname}${event.url.search}`;

    const headers = new Headers(event.request.headers);
    headers.delete('host');
    headers.delete('connection');
    headers.delete('content-length');

    if (!headers.has('x-forwarded-host')) {
      headers.set('x-forwarded-host', event.url.host);
    }
    if (!headers.has('x-forwarded-proto')) {
      headers.set('x-forwarded-proto', event.url.protocol.replace(':', ''));
    }
    try {
      const clientAddress = event.getClientAddress?.();
      if (clientAddress && !headers.has('x-forwarded-for')) {
        headers.set('x-forwarded-for', clientAddress);
      }
    } catch {
      // getClientAddress may throw in certain test or deployment environments
    }

    const method = event.request.method;
    const body =
      method === 'GET' || method === 'HEAD' ? undefined : await event.request.arrayBuffer();

    try {
      const response = await fetch(targetUrl, {
        method,
        headers,
        redirect: 'manual',
        signal: AbortSignal.timeout(60000),
        body: body && body.byteLength > 0 ? body : undefined
      });

      const responseHeaders = new Headers(response.headers);
      responseHeaders.delete('content-encoding');
      responseHeaders.delete('content-length');
      responseHeaders.delete('transfer-encoding');
      responseHeaders.delete('connection');
      responseHeaders.set('cache-control', 'no-store');

      const responseBody =
        response.status === 204 ||
        response.status === 205 ||
        response.status === 304 ||
        method === 'HEAD'
          ? null
          : response.body;

      return new Response(responseBody, {
        status: response.status,
        statusText: response.statusText,
        headers: responseHeaders
      });
    } catch (err) {
      console.error(`[hooks.server] Failed to proxy request to ${targetUrl}:`, err);
      return new Response(JSON.stringify({ detail: 'Backend service unavailable' }), {
        status: 502,
        headers: { 'content-type': 'application/json' }
      });
    }
  }

  return resolve(event);
};
