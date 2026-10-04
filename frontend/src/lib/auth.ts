import { writable } from 'svelte/store';
import { browser } from '$app/environment';
import { goto } from '$app/navigation';

export interface UserProfile {
  id: string | number;
  email?: string;
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
