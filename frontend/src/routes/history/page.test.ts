import { render, screen, fireEvent, cleanup, waitFor } from '@testing-library/svelte';
import { beforeEach, afterEach, expect, it, vi } from 'vitest';
import { writable } from 'svelte/store';
import * as api from '$lib/api';
import Page from './+page.svelte';
vi.mock('$lib/auth', () => ({ jwt_token: writable('token') }));
vi.mock('$lib/api', () => ({ getCommuteStats: vi.fn(), recordDecision: vi.fn() }));
beforeEach(() => {
  vi.resetAllMocks();
  vi.mocked(api.getCommuteStats).mockResolvedValue([]);
});
afterEach(cleanup);
it('explains empty history and records today without a fabricated user ID', async () => {
  vi.mocked(api.recordDecision).mockResolvedValue({});
  render(Page);
  expect(await screen.findByText('No rides logged in this period')).toBeInTheDocument();
  await fireEvent.click(screen.getByRole('button', { name: 'I rode' }));
  await waitFor(() =>
    expect(api.recordDecision).toHaveBeenCalledWith({
      decision: 'riding',
      date: expect.stringMatching(/^\d{4}-\d{2}-\d{2}$/)
    })
  );
  expect(await screen.findByRole('status')).toHaveTextContent('Saved: you rode today');
});
