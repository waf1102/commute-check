import { render, screen, waitFor } from '@testing-library/svelte';
import { describe, it, expect, beforeEach } from 'vitest';
import OfflineBanner from '../OfflineBanner.svelte';

describe('OfflineBanner', () => {
  beforeEach(() => {
    Object.defineProperty(navigator, 'onLine', {
      value: true,
      configurable: true,
      writable: true,
    });
  });

  it('is hidden when online', () => {
    render(OfflineBanner);
    expect(screen.queryByTestId('offline-banner')).not.toBeInTheDocument();
  });

  it('renders offline warning when window fires offline event', async () => {
    render(OfflineBanner);
    
    window.dispatchEvent(new Event('offline'));
    
    expect(await screen.findByTestId('offline-banner')).toBeInTheDocument();
    expect(screen.getByText(/You are offline/i)).toBeInTheDocument();
  });

  it('hides offline warning when window fires online event', async () => {
    render(OfflineBanner);

    window.dispatchEvent(new Event('offline'));
    expect(await screen.findByTestId('offline-banner')).toBeInTheDocument();

    window.dispatchEvent(new Event('online'));
    await waitFor(() => {
      expect(screen.queryByTestId('offline-banner')).not.toBeInTheDocument();
    });
  });
});
