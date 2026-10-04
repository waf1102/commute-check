import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { get } from 'svelte/store';
import { login, register, logout, fetchCurrentUser, jwt_token, user } from '../auth';

// Mock navigation
vi.mock('$app/navigation', () => ({
  goto: vi.fn(),
}));

// Mock environment
vi.mock('$app/environment', () => ({
  browser: true,
}));

describe('Frontend auth module', () => {
  beforeEach(() => {
    localStorage.clear();
    jwt_token.set(null);
    user.set(null);
    vi.restoreAllMocks();
  });

  afterEach(() => {
    localStorage.clear();
  });

  it('login saves token and populates user store when user is in response', async () => {
    const mockUser = { id: 1, email: 'rider@example.com' };
    vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        access_token: 'fake-jwt-token-123',
        token_type: 'bearer',
        user: mockUser,
      }),
    } as Response);

    const token = await login('rider@example.com', 'password123');
    expect(token).toBe('fake-jwt-token-123');
    expect(get(jwt_token)).toBe('fake-jwt-token-123');
    expect(localStorage.getItem('jwt_token')).toBe('fake-jwt-token-123');
    expect(get(user)).toEqual(mockUser);
  });

  it('login falls back to /api/auth/me if user is not in login response', async () => {
    const mockUser = { id: 2, email: 'driver@example.com' };
    vi.spyOn(globalThis, 'fetch')
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          access_token: 'token-without-user',
          token_type: 'bearer',
        }),
      } as Response)
      .mockResolvedValueOnce({
        ok: true,
        json: async () => mockUser,
      } as Response);

    const token = await login('driver@example.com', 'password123');
    expect(token).toBe('token-without-user');
    expect(get(jwt_token)).toBe('token-without-user');
    expect(get(user)).toEqual(mockUser);
  });

  it('login throws an error on invalid credentials (401)', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce({
      ok: false,
      status: 401,
      json: async () => ({ detail: 'Incorrect username or password' }),
    } as Response);

    await expect(login('bad@example.com', 'wrongpass')).rejects.toThrow(
      'Incorrect username or password'
    );
    expect(get(jwt_token)).toBeNull();
    expect(get(user)).toBeNull();
  });

  it('fetchCurrentUser populates user store when token is valid', async () => {
    const mockUser = { id: 5, email: 'commuter@example.com' };
    vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: async () => mockUser,
    } as Response);

    const res = await fetchCurrentUser('valid-token-abc');
    expect(res).toEqual(mockUser);
    expect(get(user)).toEqual(mockUser);
  });

  it('fetchCurrentUser logs out on 401 unauthorized', async () => {
    localStorage.setItem('jwt_token', 'expired-token');
    jwt_token.set('expired-token');
    user.set({ id: 9, email: 'old@example.com' });

    vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce({
      ok: false,
      status: 401,
      json: async () => ({ detail: 'Could not validate credentials' }),
    } as Response);

    const res = await fetchCurrentUser('expired-token');
    expect(res).toBeNull();
    expect(get(jwt_token)).toBeNull();
    expect(get(user)).toBeNull();
    expect(localStorage.getItem('jwt_token')).toBeNull();
  });

  it('register throws clean error on duplicate registration (400)', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce({
      ok: false,
      status: 400,
      json: async () => ({ detail: 'User with this email already exists' }),
    } as Response);

    await expect(register('dup@example.com', 'password123')).rejects.toThrow(
      'User with this email already exists'
    );
  });

  it('register succeeds and returns user info without polluting token if not included', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: async () => ({
        message: 'User registered successfully',
        user: { id: 10, email: 'new@example.com' },
      }),
    } as Response);

    const res = await register('new@example.com', 'password123');
    expect(res.message).toBe('User registered successfully');
    expect(get(jwt_token)).toBeNull();
    expect(localStorage.getItem('jwt_token')).toBeNull();
  });

  it('logout purges token from localStorage and resets stores', () => {
    localStorage.setItem('jwt_token', 'active-token');
    jwt_token.set('active-token');
    user.set({ id: 1, email: 'user@example.com' });

    logout();

    expect(localStorage.getItem('jwt_token')).toBeNull();
    expect(get(jwt_token)).toBeNull();
    expect(get(user)).toBeNull();
  });
});
