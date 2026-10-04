import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { handle } from './hooks.server';
import type { RequestEvent } from '@sveltejs/kit';

describe('hooks.server.ts handle proxy', () => {
  const originalEnv = process.env;

  beforeEach(() => {
    process.env = { ...originalEnv };
    vi.restoreAllMocks();
  });

  afterEach(() => {
    process.env = originalEnv;
  });

  function createMockEvent(url: string, init?: RequestInit): RequestEvent {
    const parsedUrl = new URL(url);
    const request = new Request(url, init);
    return {
      url: parsedUrl,
      request,
      getClientAddress: () => '127.0.0.1',
      cookies: {} as any,
      fetch: vi.fn(),
      locals: {},
      params: {},
      platform: {},
      route: { id: null },
      setHeaders: vi.fn(),
      isDataRequest: false,
      isSubRequest: false
    } as unknown as RequestEvent;
  }

  it('passes through non-API requests via resolve', async () => {
    const event = createMockEvent('http://localhost:3000/dashboard');
    const mockResponse = new Response('<html>ok</html>', { status: 200 });
    const resolve = vi.fn().mockResolvedValue(mockResponse);

    const result = await handle({ event, resolve });

    expect(resolve).toHaveBeenCalledWith(event);
    expect(result).toBe(mockResponse);
  });

  it('proxies GET /api/commutes to backend and returns response', async () => {
    process.env.BACKEND_URL = 'http://backend:8000';
    const event = createMockEvent('http://localhost:3000/api/commutes?active=true', {
      headers: {
        Authorization: 'Bearer test-token',
        'User-Agent': 'Vitest'
      }
    });
    const resolve = vi.fn();

    const mockBackendResponse = new Response(JSON.stringify([{ id: 1, name: 'Work' }]), {
      status: 200,
      headers: {
        'content-type': 'application/json',
        'transfer-encoding': 'chunked',
        'x-custom-backend': 'true'
      }
    });

    const fetchSpy = vi.spyOn(globalThis, 'fetch').mockResolvedValue(mockBackendResponse);

    const response = await handle({ event, resolve });

    expect(resolve).not.toHaveBeenCalled();
    expect(fetchSpy).toHaveBeenCalledTimes(1);

    const [targetUrl, options] = fetchSpy.mock.calls[0];
    expect(targetUrl).toBe('http://backend:8000/api/commutes?active=true');
    expect(options?.method).toBe('GET');

    const headers = new Headers(options?.headers);
    expect(headers.get('authorization')).toBe('Bearer test-token');
    expect(headers.has('host')).toBe(false);
    expect(headers.get('x-forwarded-host')).toBe('localhost:3000');

    expect(response.status).toBe(200);
    expect(response.headers.get('x-custom-backend')).toBe('true');
    expect(response.headers.has('transfer-encoding')).toBe(false);

    const body = await response.json();
    expect(body).toEqual([{ id: 1, name: 'Work' }]);
  });

  it('proxies POST /api/login with request body to backend', async () => {
    process.env.VITE_BACKEND_URL = 'http://custom-backend:9000';
    delete process.env.BACKEND_URL;

    const payload = { email: 'test@example.com', password: 'password123' };
    const event = createMockEvent('http://localhost:3000/api/login', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify(payload)
    });
    const resolve = vi.fn();

    const mockBackendResponse = new Response(
      JSON.stringify({ access_token: 'xyz', user: { id: 1 } }),
      { status: 200, headers: { 'content-type': 'application/json' } }
    );

    const fetchSpy = vi.spyOn(globalThis, 'fetch').mockResolvedValue(mockBackendResponse);

    const response = await handle({ event, resolve });

    expect(fetchSpy).toHaveBeenCalledTimes(1);
    const [targetUrl, options] = fetchSpy.mock.calls[0];
    expect(targetUrl).toBe('http://custom-backend:9000/api/login');
    expect(options?.method).toBe('POST');
    expect(options?.body).toBeDefined();

    const sentBodyText = new TextDecoder().decode(options?.body as ArrayBuffer);
    expect(JSON.parse(sentBodyText)).toEqual(payload);

    expect(response.status).toBe(200);
    const data = await response.json();
    expect(data.access_token).toBe('xyz');
  });

  it('returns 502 JSON error when backend is unavailable', async () => {
    process.env.BACKEND_URL = 'http://backend:8000';
    const event = createMockEvent('http://localhost:3000/api/check', {
      method: 'POST',
      body: JSON.stringify({ route: 'home' })
    });
    const resolve = vi.fn();

    vi.spyOn(globalThis, 'fetch').mockRejectedValue(new Error('fetch failed: ECONNREFUSED'));
    const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {});

    const response = await handle({ event, resolve });

    expect(response.status).toBe(502);
    expect(response.headers.get('content-type')).toBe('application/json');
    const body = await response.json();
    expect(body).toEqual({ detail: 'Backend service unavailable' });

    consoleSpy.mockRestore();
  });

  it('handles 204 No Content response from backend without body errors', async () => {
    process.env.BACKEND_URL = 'http://backend:8000';
    const event = createMockEvent('http://localhost:3000/api/commutes/1', {
      method: 'DELETE'
    });
    const resolve = vi.fn();

    const mockBackendResponse = new Response(null, { status: 204 });
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(mockBackendResponse);

    const response = await handle({ event, resolve });

    expect(response.status).toBe(204);
    expect(response.body).toBeNull();
  });
});
