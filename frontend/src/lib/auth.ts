import { get, writable } from 'svelte/store';
import { browser } from '$app/environment';
import { goto } from '$app/navigation';

export const jwt_token = writable<string | null>(null);
export interface UserProfile {
  id: string | number;
  email?: string;
}
export interface JwtPayload {
  sub?: string;
  email?: string;
  name?: string;
  exp?: number;
  [key: string]: unknown;
}
export const user = writable<UserProfile | null>(null);

// Decoding is for display only; the server verifies identity and permissions.
export function decodeJwt(token: string | null | undefined): JwtPayload | null {
  if (!token || token.split('.').length !== 3) return null;
  try {
    const encoded = token.split('.')[1].replace(/-/g, '+').replace(/_/g, '/');
    const binary = atob(encoded.padEnd(Math.ceil(encoded.length / 4) * 4, '='));
    let decoded = binary;
    try {
      decoded = decodeURIComponent(
        Array.from(binary, (c) => '%' + c.charCodeAt(0).toString(16).padStart(2, '0')).join('')
      );
    } catch {
      /* Legacy Latin-1 tokens. */
    }
    const payload = JSON.parse(decoded);
    return payload && typeof payload === 'object' && !Array.isArray(payload) ? payload : null;
  } catch {
    return null;
  }
}
export function getUserEmailFromToken(token: string | null | undefined): string {
  const payload = decodeJwt(token);
  const email = payload?.email || payload?.sub || payload?.name;
  return typeof email === 'string' ? email : '';
}

export async function fetchCurrentUser(token?: string): Promise<UserProfile | null> {
  const activeToken = token || get(jwt_token);
  if (!activeToken) return null;
  try {
    const response = await fetch('/api/auth/me', {
      headers: { Authorization: `Bearer ${activeToken}` },
      signal: AbortSignal.timeout(10000)
    });
    if (response.ok) {
      const profile = await response.json();
      if (get(jwt_token) === activeToken) user.set(profile);
      return profile;
    }
    if (response.status === 401 && get(jwt_token) === activeToken) logout();
  } catch {
    /* Identity can be loaded again when the connection returns. */
  }
  return null;
}

if (browser) {
  const storedToken = localStorage.getItem('jwt_token');
  if (storedToken && storedToken !== 'undefined' && storedToken !== 'null') {
    jwt_token.set(storedToken);
  } else if (storedToken) {
    localStorage.removeItem('jwt_token');
  }
}

async function handleAuthResponse(response: Response) {
  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new Error(
      typeof errorData.detail === 'string'
        ? errorData.detail
        : errorData.detail?.[0]?.msg || 'Could not sign in. Please try again.'
    );
  }
  const data = await response.json();
  const token = data.access_token;
  if (!token) throw new Error('Sign in failed. Please try again.');
  if (browser) {
    localStorage.setItem('jwt_token', token);
  }
  jwt_token.set(token);
  if (data.user) user.set(data.user);
  else await fetchCurrentUser(token);
  return token;
}

export async function login(email: string, password: string): Promise<string> {
  const response = await fetch('/api/login', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/x-www-form-urlencoded'
    },
    body: new URLSearchParams({ username: email.trim(), password })
  });
  return handleAuthResponse(response);
}

export async function register(email: string, password: string): Promise<string> {
  const response = await fetch('/api/register', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({ email, password })
  });
  return handleAuthResponse(response);
}

export function logout() {
  if (browser) {
    localStorage.removeItem('jwt_token');
  }
  jwt_token.set(null);
  user.set(null);
  goto('/login');
}
