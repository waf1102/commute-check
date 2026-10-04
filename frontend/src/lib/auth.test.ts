import { beforeEach, expect, it, vi } from 'vitest';
import { login, register, jwt_token } from './auth';
import { get } from 'svelte/store';
vi.mock('$app/environment', () => ({ browser: true }));
vi.mock('$app/navigation', () => ({ goto: vi.fn() }));
beforeEach(() => {
  localStorage.clear();
  jwt_token.set(null);
  vi.stubGlobal('fetch', vi.fn());
});
it('sends the form contract the login endpoint actually accepts', async () => {
  vi.mocked(fetch).mockResolvedValue(Response.json({ access_token: 'token' }));
  await login(' rider@example.com ', 'password');
  const request = vi.mocked(fetch).mock.calls[0][1];
  expect(request?.body?.toString()).toBe('username=rider%40example.com&password=password');
  expect(get(jwt_token)).toBe('token');
});
it('does not persist an undefined token after registration', async () => {
  vi.mocked(fetch).mockResolvedValue(Response.json({ message: 'Created' }));
  await expect(register('rider@example.com', 'password')).rejects.toThrow('Sign in failed');
  expect(localStorage.getItem('jwt_token')).toBeNull();
});
