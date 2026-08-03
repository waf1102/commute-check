import { render, screen, fireEvent, waitFor } from '@testing-library/svelte';
import { describe, it, expect, vi } from 'vitest';
import PwaInstallPrompt from '../PwaInstallPrompt.svelte';

describe('PwaInstallPrompt', () => {
  it('is hidden initially until beforeinstallprompt event fires', () => {
    render(PwaInstallPrompt);
    expect(screen.queryByTestId('pwa-install-prompt')).not.toBeInTheDocument();
  });

  it('renders install prompt when beforeinstallprompt event is dispatched', async () => {
    render(PwaInstallPrompt);

    const event = new Event('beforeinstallprompt');
    (event as any).prompt = vi.fn();
    (event as any).userChoice = Promise.resolve({ outcome: 'accepted' });

    window.dispatchEvent(event);

    expect(await screen.findByTestId('pwa-install-prompt')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Install App/i })).toBeInTheDocument();
  });

  it('prompts user and hides banner upon clicking install', async () => {
    render(PwaInstallPrompt);

    const event = new Event('beforeinstallprompt');
    const promptMock = vi.fn();
    (event as any).prompt = promptMock;
    (event as any).userChoice = Promise.resolve({ outcome: 'accepted' });

    window.dispatchEvent(event);

    const installBtn = await screen.findByRole('button', { name: /Install App/i });
    await fireEvent.click(installBtn);

    expect(promptMock).toHaveBeenCalledTimes(1);
    await waitFor(() => {
      expect(screen.queryByTestId('pwa-install-prompt')).not.toBeInTheDocument();
    });
  });
});
