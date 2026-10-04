import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { get } from 'svelte/store';
import {
  login,
  register,
  logout,
  fetchCurrentUser,
  jwt_token,
  user,
  decodeJwt,
  getUserEmailFromToken
} from '../auth';

// Mock navigation
vi.mock('$app/navigation', () => ({
  goto: vi.fn()
}));

// Mock environment
vi.mock('$app/environment', () => ({
  browser: true
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
        user: mockUser
      })
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
          token_type: 'bearer'
        })
      } as Response)
      .mockResolvedValueOnce({
        ok: true,
        json: async () => mockUser
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
      json: async () => ({ detail: 'Incorrect username or password' })
    } as Response);

    await expect(login('bad@example.com', 'wrongpass')).rejects.toThrow(
      'Incorrect username or password'
    );
    expect(get(jwt_token)).toBeNull();
    expect(get(user)).toBeNull();
  });

  it('fetchCurrentUser populates user store when token is valid', async () => {
    jwt_token.set('valid-token-abc');
    const mockUser = { id: 5, email: 'commuter@example.com' };
    vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: async () => mockUser
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
      json: async () => ({ detail: 'Could not validate credentials' })
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
      json: async () => ({ detail: 'User with this email already exists' })
    } as Response);

    await expect(register('dup@example.com', 'password123')).rejects.toThrow(
      'User with this email already exists'
    );
  });

  it('register reports a missing session without persisting an undefined token', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: async () => ({
        message: 'User registered successfully',
        user: { id: 10, email: 'new@example.com' }
      })
    } as Response);

    await expect(register('new@example.com', 'password123')).rejects.toThrow('Sign in failed');
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

  describe('JWT decoding helpers', () => {
    // Helper to generate a fake JWT token from a payload object
    function makeJwt(payload: any): string {
      const header = { alg: 'HS256', typ: 'JWT' };
      const toBase64Url = (obj: any) =>
        btoa(JSON.stringify(obj)).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
      return `${toBase64Url(header)}.${toBase64Url(payload)}.fake_signature`;
    }

    it('decodeJwt correctly extracts sub claim from JWT token', () => {
      const token = makeJwt({ sub: 'rider@example.com', exp: 1700000000 });
      const payload = decodeJwt(token);
      expect(payload).not.toBeNull();
      expect(payload?.sub).toBe('rider@example.com');
      expect(payload?.exp).toBe(1700000000);
    });

    it('decodeJwt correctly extracts email and custom fields from JWT token', () => {
      const token = makeJwt({
        email: 'commuter@example.com',
        name: 'Commuter Jane',
        custom_role: 'admin'
      });
      const payload = decodeJwt(token);
      expect(payload).not.toBeNull();
      expect(payload?.email).toBe('commuter@example.com');
      expect(payload?.name).toBe('Commuter Jane');
      expect(payload?.custom_role).toBe('admin');
    });

    it('decodeJwt handles url-safe base64 characters (- and _)', () => {
      // payload with bytes that produce - and _ in base64url
      const token = makeJwt({ special: 'chars>>>???&&&', email: 'test+special@example.com' });
      const payload = decodeJwt(token);
      expect(payload?.email).toBe('test+special@example.com');
    });

    it('decodeJwt handles UTF-8 characters properly', () => {
      const token = makeJwt({ sub: 'user_café_öäü@example.com', name: 'René' });
      const payload = decodeJwt(token);
      expect(payload?.sub).toBe('user_café_öäü@example.com');
      expect(payload?.name).toBe('René');
    });

    it('decodeJwt returns null for invalid or corrupted tokens', () => {
      expect(decodeJwt('')).toBeNull();
      expect(decodeJwt(null)).toBeNull();
      expect(decodeJwt(undefined)).toBeNull();
      expect(decodeJwt('not.a.valid.jwt.with.too.many.dots')).toBeNull();
      expect(decodeJwt('invalid-single-part-token')).toBeNull();
      expect(decodeJwt('header.invalid-base64-json%%%.sig')).toBeNull();
      expect(decodeJwt('header.' + btoa('not-json') + '.sig')).toBeNull();
    });

    it('getUserEmailFromToken extracts email from sub or email or name', () => {
      const tokenSub = makeJwt({ sub: 'user_sub@example.com' });
      expect(getUserEmailFromToken(tokenSub)).toBe('user_sub@example.com');

      const tokenEmail = makeJwt({ email: 'user_email@example.com', sub: 'different_sub' });
      expect(getUserEmailFromToken(tokenEmail)).toBe('user_email@example.com');

      const tokenNameOnly = makeJwt({ name: 'SoloName' });
      expect(getUserEmailFromToken(tokenNameOnly)).toBe('SoloName');

      expect(getUserEmailFromToken(null)).toBe('');
      expect(getUserEmailFromToken(undefined)).toBe('');
      expect(getUserEmailFromToken('malformed-token')).toBe('');
    });
  });
});
