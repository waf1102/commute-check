import { writable } from 'svelte/store';
import { browser } from '$app/environment';
import { goto } from '$app/navigation';

export const jwt_token = writable<string | null>(null);

if (browser) {
  const storedToken = localStorage.getItem('jwt_token');
  if (storedToken) {
    jwt_token.set(storedToken);
  }
}

async function handleAuthResponse(response: Response) {
  if (!response.ok) {
    const errorData = await response.json();
    throw new Error(errorData.detail || 'Authentication failed');
  }
  const data = await response.json();
  const token = data.access_token; // Assuming backend returns access_token
  if (browser) {
    localStorage.setItem('jwt_token', token);
  }
  jwt_token.set(token);
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

export async function register(email: string, password: string): Promise<string> {
  const response = await fetch('/api/register', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ email, password }),
  });
  return handleAuthResponse(response);
}

export function logout() {
  if (browser) {
    localStorage.removeItem('jwt_token');
  }
  jwt_token.set(null);
  goto('/login');
}