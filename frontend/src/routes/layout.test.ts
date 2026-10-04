import { render, screen, fireEvent, cleanup } from '@testing-library/svelte';
import { afterEach, expect, it, vi } from 'vitest';
import { createRawSnippet } from 'svelte';
import Layout from './+layout.svelte';
import { jwt_token } from '$lib/auth';
import { goto } from '$app/navigation';
vi.mock('$app/environment', () => ({ browser: true }));
vi.mock('$app/navigation', () => ({ goto: vi.fn() }));
vi.mock('$app/state', () => ({ page: { url: new URL('http://localhost/') } }));
const children = createRawSnippet(() => ({ render: () => '<div>Page</div>' }));
afterEach(() => {
  cleanup();
  jwt_token.set(null);
  localStorage.clear();
});
it('shows a clear sign-in entry point before signing in', () => {
  render(Layout, { children });
  expect(screen.getByRole('link', { name: 'Sign in' })).toHaveAttribute('href', '/login');
  expect(screen.queryByRole('link', { name: 'History' })).not.toBeInTheDocument();
});
it('identifies the signed-in account and exposes navigation and sign out directly', async () => {
  jwt_token.set(`header.${btoa(JSON.stringify({ sub: 'rider@example.com' }))}.signature`);
  render(Layout, { children });
  expect(screen.getByText('Signed in as rider@example.com')).toBeInTheDocument();
  expect(screen.getByRole('link', { name: 'Your commute' })).toHaveAttribute('href', '/settings');
  await fireEvent.click(screen.getByRole('button', { name: 'Sign out' }));
  expect(goto).toHaveBeenCalledWith('/login');
});
