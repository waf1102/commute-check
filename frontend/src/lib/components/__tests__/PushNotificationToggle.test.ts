import { render, screen, fireEvent, waitFor } from '@testing-library/svelte';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import PushNotificationToggle from '../PushNotificationToggle.svelte';
import * as api from '$lib/api';

vi.mock('$lib/api', async (importOriginal) => {
  const actual: any = await importOriginal();
  return {
    ...actual,
    getVapidPublicKey: vi.fn(),
    subscribePush: vi.fn(),
    unsubscribePush: vi.fn(),
    sendTestPush: vi.fn()
  };
});

describe('PushNotificationToggle', () => {
  let mockGetSubscription: any;
  let mockSubscribe: any;
  let mockUnsubscribe: any;
  let mockRequestPermission: any;

  beforeEach(() => {
    vi.clearAllMocks();

    mockUnsubscribe = vi.fn().mockResolvedValue(true);
    mockGetSubscription = vi.fn().mockResolvedValue(null);
    mockSubscribe = vi.fn().mockResolvedValue({
      endpoint: 'https://push.example.com/sub/123',
      toJSON: () => ({
        endpoint: 'https://push.example.com/sub/123',
        keys: { p256dh: 'mock-p256dh', auth: 'mock-auth' }
      }),
      unsubscribe: mockUnsubscribe
    });

    mockRequestPermission = vi.fn().mockResolvedValue('granted');

    (window as any).Notification = {
      permission: 'default',
      requestPermission: mockRequestPermission
    };

    Object.defineProperty(navigator, 'serviceWorker', {
      value: {
        ready: Promise.resolve({
          pushManager: {
            getSubscription: mockGetSubscription,
            subscribe: mockSubscribe
          }
        })
      },
      configurable: true,
      writable: true
    });
  });

  it('renders push notification component with Enable Push button initially', async () => {
    render(PushNotificationToggle);

    expect(screen.getByRole('heading', { name: /Push Notifications/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Enable Push/i })).toBeInTheDocument();
  });

  it('subscribes to push notifications when Enable Push button is clicked', async () => {
    (api.getVapidPublicKey as any).mockResolvedValue({
      public_key: 'BEl62iUYgUivxIkv69yViEuiM23V9A'
    });
    (api.subscribePush as any).mockResolvedValue({ status: 'subscribed' });

    render(PushNotificationToggle);

    const toggleBtn = screen.getByRole('button', { name: /Enable Push/i });
    await fireEvent.click(toggleBtn);

    await waitFor(() => {
      expect(mockRequestPermission).toHaveBeenCalled();
      expect(api.getVapidPublicKey).toHaveBeenCalled();
      expect(mockSubscribe).toHaveBeenCalled();
      expect(api.subscribePush).toHaveBeenCalledWith({
        endpoint: 'https://push.example.com/sub/123',
        keys: { p256dh: 'mock-p256dh', auth: 'mock-auth' }
      });
      expect(screen.getByRole('button', { name: /Disable Push/i })).toBeInTheDocument();
    });
  });

  it('unsubscribes from push notifications when Disable Push button is clicked', async () => {
    const mockSub = {
      endpoint: 'https://push.example.com/sub/123',
      toJSON: () => ({ endpoint: 'https://push.example.com/sub/123' }),
      unsubscribe: mockUnsubscribe
    };
    mockGetSubscription.mockResolvedValue(mockSub);
    (api.unsubscribePush as any).mockResolvedValue({ status: 'unsubscribed' });

    render(PushNotificationToggle);

    const disableBtn = await screen.findByRole('button', { name: /Disable Push/i });
    await fireEvent.click(disableBtn);

    await waitFor(() => {
      expect(api.unsubscribePush).toHaveBeenCalledWith('https://push.example.com/sub/123');
      expect(mockUnsubscribe).toHaveBeenCalled();
      expect(screen.getByRole('button', { name: /Enable Push/i })).toBeInTheDocument();
    });
  });

  it('triggers sendTestPush when Test button is clicked', async () => {
    const mockSub = {
      endpoint: 'https://push.example.com/sub/123',
      toJSON: () => ({ endpoint: 'https://push.example.com/sub/123' }),
      unsubscribe: mockUnsubscribe
    };
    mockGetSubscription.mockResolvedValue(mockSub);
    (api.sendTestPush as any).mockResolvedValue({ status: 'sent', delivered: 1, failed: 0 });

    render(PushNotificationToggle);

    const testBtn = await screen.findByRole('button', { name: /Send Test Notification/i });
    await fireEvent.click(testBtn);

    await waitFor(() => {
      expect(api.sendTestPush).toHaveBeenCalledTimes(1);
    });
  });
});
