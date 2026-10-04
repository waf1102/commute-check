import { writable } from 'svelte/store';
import { browser } from '$app/environment';
import { goto } from '$app/navigation';

export interface UserProfile {
  id: string | number;
  email?: string;
}

export interface JwtPayload {
  sub?: string;
  email?: string;
  name?: string;
  exp?: number;
  [key: string]: any;
}

export function decodeJwt<T = JwtPayload>(token: string | null | undefined): T | null {
  if (!token || typeof token !== 'string') return null;
  const parts = token.split('.');
  if (parts.length < 2) return null;

  try {
    const base64Url = parts[1];
    let base64 = base64Url.replace(/-/g, '+').replace(/_/g, '/');
    while (base64.length % 4 !== 0) {
      base64 += '=';
    }

    let decodedStr: string;
    if (typeof atob === 'function') {
      const binary = atob(base64);
      try {
        decodedStr = decodeURIComponent(
          binary
            .split('')
            .map((c) => '%' + ('00' + c.charCodeAt(0).toString(16)).slice(-2))
            .join('')
        );
      } catch {
        decodedStr = binary;
      }
    } else if (typeof Buffer !== 'undefined') {
      decodedStr = Buffer.from(base64, 'base64').toString('utf-8');
    } else {
      return null;
    }

    return JSON.parse(decodedStr);
  } catch {
    return null;
  }
}

export function getUserEmailFromToken(token: string | null | undefined): string {
  if (!token) return '';
  const payload = decodeJwt(token);
  return payload?.email || payload?.sub || payload?.name || '';
}

export const jwt_token = writable<string | null>(null);
export const user = writable<UserProfile | null>(null);

export async function fetchCurrentUser(token?: string): Promise<UserProfile | null> {
  const activeToken = token || (browser ? localStorage.getItem('jwt_token') : null);
  if (!activeToken || activeToken === 'undefined' || activeToken === 'null') {
    user.set(null);
    return null;
  }

  try {
    const response = await fetch('/api/auth/me', {
      headers: {
        'Authorization': `Bearer ${activeToken}`,
      },
    });

    if (response.ok) {
      const userData: UserProfile = await response.json();
      user.set(userData);
      return userData;
    } else if (response.status === 401) {
      logout();
      return null;
    }
  } catch (err) {
    console.error('Failed to fetch user:', err);
  }
  return null;
}

if (browser) {
  const storedToken = localStorage.getItem('jwt_token');
  if (storedToken && storedToken !== 'undefined' && storedToken !== 'null') {
    jwt_token.set(storedToken);
    fetchCurrentUser(storedToken).catch(() => {});
  } else if (storedToken) {
    localStorage.removeItem('jwt_token');
  }
}

async function handleAuthResponse(response: Response): Promise<string> {
  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new Error(errorData.detail || 'Authentication failed');
  }
  const data = await response.json();
  const token = data.access_token;
  if (!token) {
    throw new Error('Authentication response did not contain access_token');
  }
  if (browser) {
    localStorage.setItem('jwt_token', token);
  }
  jwt_token.set(token);

  if (data.user) {
    user.set(data.user);
  } else {
    await fetchCurrentUser(token);
  }

  return token;
}

export async function login(email: string, password: string): Promise<string> {
  const response = await fetch('/api/login', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ email, password }),
  });
  return handleAuthResponse(response);
}

export async function register(email: string, password: string): Promise<any> {
  const response = await fetch('/api/register', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ email, password }),
  });
  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new Error(errorData.detail || 'Registration failed');
  }
  const data = await response.json();
  if (data.access_token) {
    if (browser) {
      localStorage.setItem('jwt_token', data.access_token);
    }
    jwt_token.set(data.access_token);
    if (data.user) {
      user.set(data.user);
    }
  }
  return data;
}

export function logout() {
  if (browser) {
    localStorage.removeItem('jwt_token');
  }
  jwt_token.set(null);
  user.set(null);
  if (browser) {
    goto('/login');
  }
}
