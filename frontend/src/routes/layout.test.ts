import { render, screen, fireEvent, waitFor } from '@testing-library/svelte';
import { tick } from 'svelte';
import Layout from './+layout.svelte';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { jwt_token, logout } from '$lib/auth';

// Mock navigation
vi.mock('$app/navigation', () => ({
  goto: vi.fn(),
}));

// Mock environment
vi.mock('$app/environment', () => ({
  browser: true,
}));

// Helper to create valid JWT tokens with custom payload
function createMockJwt(payload: Record<string, any>): string {
  const header = { alg: 'HS256', typ: 'JWT' };
  const toBase64Url = (obj: any) =>
    btoa(JSON.stringify(obj))
      .replace(/\+/g, '-')
      .replace(/\//g, '_')
      .replace(/=+$/, '');
  return `${toBase64Url(header)}.${toBase64Url(payload)}.signature`;
}

describe('Layout Component (+layout.svelte)', () => {
  beforeEach(() => {
    localStorage.clear();
    jwt_token.set(null);
    vi.restoreAllMocks();
  });

  afterEach(() => {
    localStorage.clear();
    jwt_token.set(null);
  });

  it('renders default nav links and login/register when unauthenticated', () => {
    render(Layout);

    expect(screen.getByRole('link', { name: 'Dashboard' })).toHaveAttribute('href', '/');
    expect(screen.getByRole('link', { name: 'History' })).toHaveAttribute('href', '/history');
    expect(screen.getByRole('link', { name: 'Settings' })).toHaveAttribute('href', '/settings');
    expect(screen.getByRole('link', { name: 'Login' })).toHaveAttribute('href', '/login');
    expect(screen.getByRole('link', { name: 'Register' })).toHaveAttribute('href', '/register');

    // Should not render user dropdown
    expect(screen.queryByTestId('user-dropdown-trigger')).toBeNull();
    expect(screen.queryByTestId('user-dropdown-menu')).toBeNull();
  });

  it('dynamically decodes JWT to show authenticated user email in top navigation', () => {
    const token = createMockJwt({ sub: 'rider@example.com' });
    jwt_token.set(token);

    render(Layout);

    const trigger = screen.getByTestId('user-dropdown-trigger');
    expect(trigger).toBeInTheDocument();
    expect(trigger).toHaveTextContent('rider@example.com');
    expect(trigger).toHaveTextContent('Hello, rider@example.com');
    expect(screen.queryByRole('link', { name: 'Login' })).toBeNull();
    expect(screen.queryByRole('link', { name: 'Register' })).toBeNull();
  });

  it('dynamically decodes JWT with email claim taking precedence if present', () => {
    const token = createMockJwt({ email: 'priority@example.com', sub: 'user-sub-id' });
    jwt_token.set(token);

    render(Layout);

    const trigger = screen.getByTestId('user-dropdown-trigger');
    expect(trigger).toHaveTextContent('priority@example.com');
  });

  it('opens and closes user dropdown menu when trigger is clicked', async () => {
    const token = createMockJwt({ sub: 'rider@example.com' });
    jwt_token.set(token);

    render(Layout);

    const trigger = screen.getByTestId('user-dropdown-trigger');
    expect(trigger).toHaveAttribute('aria-expanded', 'false');
    expect(screen.queryByTestId('user-dropdown-menu')).toBeNull();

    // Click to open dropdown
    await fireEvent.click(trigger);

    expect(trigger).toHaveAttribute('aria-expanded', 'true');
    const menu = screen.getByTestId('user-dropdown-menu');
    expect(menu).toBeInTheDocument();
    expect(menu).toHaveTextContent('rider@example.com');

    // Click to close dropdown
    await fireEvent.click(trigger);
    expect(trigger).toHaveAttribute('aria-expanded', 'false');
    expect(screen.queryByTestId('user-dropdown-menu')).toBeNull();
  });

  it('includes functional profile link and logout button in dropdown menu', async () => {
    const token = createMockJwt({ sub: 'commuter@example.com' });
    jwt_token.set(token);

    render(Layout);

    const trigger = screen.getByTestId('user-dropdown-trigger');
    await fireEvent.click(trigger);

    const profileLink = screen.getByTestId('dropdown-profile-link');
    expect(profileLink).toHaveAttribute('href', '/settings');
    expect(profileLink).toHaveTextContent('Profile');

    const logoutBtn = screen.getByTestId('dropdown-logout-button');
    expect(logoutBtn).toBeInTheDocument();
    expect(logoutBtn).toHaveTextContent('Logout');

    // Clicking profile link closes the menu
    await fireEvent.click(profileLink);
    expect(screen.queryByTestId('user-dropdown-menu')).toBeNull();
  });

  it('clicking logout inside dropdown executes logout and closes menu', async () => {
    const token = createMockJwt({ sub: 'commuter@example.com' });
    jwt_token.set(token);
    localStorage.setItem('jwt_token', token);

    render(Layout);

    const trigger = screen.getByTestId('user-dropdown-trigger');
    await fireEvent.click(trigger);

    const logoutBtn = screen.getByTestId('dropdown-logout-button');
    await fireEvent.click(logoutBtn);

    // Dropdown menu should be closed
    expect(screen.queryByTestId('user-dropdown-menu')).toBeNull();
    // Token should be removed
    expect(localStorage.getItem('jwt_token')).toBeNull();
  });

  it('closes dropdown when clicking outside', async () => {
    const token = createMockJwt({ sub: 'rider@example.com' });
    jwt_token.set(token);

    render(Layout);

    const trigger = screen.getByTestId('user-dropdown-trigger');
    await fireEvent.click(trigger);
    expect(screen.getByTestId('user-dropdown-menu')).toBeInTheDocument();

    // Click outside on window / document body
    await fireEvent.click(document.body);
    expect(screen.queryByTestId('user-dropdown-menu')).toBeNull();
  });

  it('closes dropdown when pressing Escape key', async () => {
    const token = createMockJwt({ sub: 'rider@example.com' });
    jwt_token.set(token);

    render(Layout);

    const trigger = screen.getByTestId('user-dropdown-trigger');
    await fireEvent.click(trigger);
    expect(screen.getByTestId('user-dropdown-menu')).toBeInTheDocument();

    // Press Escape
    await fireEvent.keyDown(window, { key: 'Escape' });
    expect(screen.queryByTestId('user-dropdown-menu')).toBeNull();
  });

  it('reactively updates user email when jwt_token store changes', async () => {
    const token1 = createMockJwt({ sub: 'first@example.com' });
    jwt_token.set(token1);

    render(Layout);

    expect(screen.getByTestId('user-dropdown-trigger')).toHaveTextContent('first@example.com');

    // Switch user token
    const token2 = createMockJwt({ sub: 'second@example.com' });
    jwt_token.set(token2);
    await tick();

    await waitFor(() => {
      expect(screen.getByTestId('user-dropdown-trigger')).toHaveTextContent('second@example.com');
    });

    // Clear token
    jwt_token.set(null);
    await tick();

    await waitFor(() => {
      expect(screen.queryByTestId('user-dropdown-trigger')).toBeNull();
      expect(screen.getByRole('link', { name: 'Login' })).toBeInTheDocument();
    });
  });

  it('handles invalid token gracefully with fallback', () => {
    jwt_token.set('invalid.token');

    render(Layout);

    const trigger = screen.getByTestId('user-dropdown-trigger');
    expect(trigger).toHaveTextContent('User');
  });
});
