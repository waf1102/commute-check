import { afterEach, expect, it, vi } from 'vitest';
import { getCommuteStats, recordDecision, authenticatedFetch } from './api';
import { jwt_token, user } from './auth';
import { get } from 'svelte/store';
vi.mock('$app/environment', () => ({ browser: true }));
vi.mock('$app/navigation', () => ({ goto: vi.fn() }));
afterEach(() => {
  vi.unstubAllGlobals();
  jwt_token.set(null);
  user.set(null);
});
it('loads history for the signed-in user without a client-supplied user ID', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(Response.json([])));
  await getCommuteStats('2026-10-01', '2026-10-03');
  const url = String(vi.mocked(fetch).mock.calls[0][0]);
  expect(url).toContain('start_date=2026-10-01');
  expect(url).toContain('end_date=2026-10-03');
  expect(url).not.toContain('user_id');
});
it('records the chosen mode and local date', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(Response.json({ id: 1 })));
  await recordDecision({ decision: 'riding', date: '2026-10-03' });
  const [url, options] = vi.mocked(fetch).mock.calls[0];
  expect(url).toContain('/api/analytics/record-decision');
  expect(options?.method).toBe('POST');
  expect(JSON.parse(String(options?.body))).toEqual({ decision: 'riding', date: '2026-10-03' });
});
it('clears stale identity when the session expires', async () => {
  jwt_token.set('expired');
  user.set({ id: 1, email: 'rider@example.com' });
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(null, { status: 401 })));
  await expect(authenticatedFetch('/api/config')).rejects.toThrow('Please sign in again');
  expect(get(jwt_token)).toBeNull();
  expect(get(user)).toBeNull();
});
