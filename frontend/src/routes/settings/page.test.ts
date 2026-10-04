import { render, screen, fireEvent, cleanup, waitFor } from '@testing-library/svelte';
import { beforeEach, afterEach, expect, it, vi } from 'vitest';
import { writable } from 'svelte/store';
import { newCommute } from '$lib/commute';
import * as api from '$lib/api';
import { goto } from '$app/navigation';
import Page from './+page.svelte';
vi.mock('$lib/auth', () => ({ jwt_token: writable('token') }));
vi.mock('$app/navigation', () => ({ goto: vi.fn(), beforeNavigate: vi.fn() }));
vi.mock('$lib/api', async (importOriginal) => ({
  ...(await importOriginal<typeof import('$lib/api')>()),
  getCommuteConfig: vi.fn(),
  saveCommuteConfig: vi.fn(),
  searchPlaces: vi.fn()
}));
beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(api.getCommuteConfig).mockResolvedValue([]);
});
afterEach(cleanup);
it('does not silently save an invented default location', async () => {
  render(Page);
  await fireEvent.click(await screen.findByRole('button', { name: 'Save and check weather' }));
  expect(await screen.findByRole('alert')).toHaveTextContent('Choose where you leave from');
  expect(api.saveCommuteConfig).not.toHaveBeenCalled();
});
it('saves a new commute once and continues straight to its forecast', async () => {
  const commute = {
    ...newCommute(),
    id: 3,
    origin_name: 'Boston',
    lat: 42,
    lon: -71,
    dest_name: 'Cambridge',
    dest_lat: 42.1,
    dest_lon: -71.1
  };
  vi.mocked(api.getCommuteConfig).mockResolvedValue([commute]);
  vi.mocked(api.saveCommuteConfig).mockResolvedValue(commute);
  render(Page);
  await fireEvent.click(await screen.findByRole('button', { name: 'Save and check weather' }));
  await waitFor(() => expect(goto).toHaveBeenCalledWith('/?commute=3'));
  expect(api.saveCommuteConfig).toHaveBeenCalledTimes(1);
  expect(vi.mocked(api.saveCommuteConfig).mock.calls[0][0]).toMatchObject({
    id: 3,
    lat: 42,
    dest_lat: 42.1
  });
});
it('converts weather limits when changing units', async () => {
  vi.mocked(api.getCommuteConfig).mockResolvedValue([
    { ...newCommute(), id: 3, lat: 42, lon: -71, dest_lat: 42.1, dest_lon: -71.1 }
  ]);
  render(Page);
  await fireEvent.change(await screen.findByLabelText('Weather units'), {
    target: { value: 'metric' }
  });
  const temp = screen.getByLabelText(/Cold: take care below/);
  expect(temp).toHaveValue(7.2);
  expect(screen.getByLabelText(/Wind: take care above/)).toHaveValue(24.1);
});
it('keeps entered changes and shows the server error when saving fails', async () => {
  vi.mocked(api.getCommuteConfig).mockResolvedValue([
    { ...newCommute(), id: 3, lat: 42, lon: -71, dest_lat: 42.1, dest_lon: -71.1 }
  ]);
  vi.mocked(api.saveCommuteConfig).mockRejectedValue(new Error('Please try again'));
  render(Page);
  await fireEvent.input(await screen.findByLabelText('Commute name'), {
    target: { value: 'My office' }
  });
  await fireEvent.click(screen.getByRole('button', { name: 'Save and check weather' }));
  expect(await screen.findByRole('alert')).toHaveTextContent('Please try again');
  expect(screen.getByLabelText('Commute name')).toHaveValue('My office');
  expect(goto).not.toHaveBeenCalled();
});
it('populates notification times from saved commute and saves updated notification times independent of departure times', async () => {
  const commute = {
    ...newCommute(),
    id: 5,
    origin_name: 'Boston',
    lat: 42,
    lon: -71,
    dest_name: 'Cambridge',
    dest_lat: 42.1,
    dest_lon: -71.1,
    schedule_time: '08:00',
    return_schedule_time: '17:00',
    notification_time: '07:15',
    return_notification_time: '16:30'
  };
  vi.mocked(api.getCommuteConfig).mockResolvedValue([commute]);
  vi.mocked(api.saveCommuteConfig).mockResolvedValue(commute);

  render(Page);

  const outboundNotify = await screen.findByLabelText('Notify at');
  const returnNotify = await screen.findByLabelText('Notify at (return)');
  expect(outboundNotify).toHaveValue('07:15');
  expect(returnNotify).toHaveValue('16:30');

  // Change notification times independently of departure times
  await fireEvent.input(outboundNotify, { target: { value: '07:00' } });
  await fireEvent.input(returnNotify, { target: { value: '16:15' } });

  await fireEvent.click(screen.getByRole('button', { name: 'Save and check weather' }));
  await waitFor(() => expect(api.saveCommuteConfig).toHaveBeenCalledTimes(1));

  expect(vi.mocked(api.saveCommuteConfig).mock.calls[0][0]).toMatchObject({
    id: 5,
    schedule_time: '08:00',
    return_schedule_time: '17:00',
    notification_time: '07:00',
    return_notification_time: '16:15'
  });
});
it('disables return notification time and sets it to null when return trip is unchecked', async () => {
  const commute = {
    ...newCommute(),
    id: 6,
    origin_name: 'Boston',
    lat: 42,
    lon: -71,
    dest_name: 'Cambridge',
    dest_lat: 42.1,
    dest_lon: -71.1,
    schedule_time: '08:00',
    return_schedule_time: '17:00',
    notification_time: '07:30',
    return_notification_time: '16:30'
  };
  vi.mocked(api.getCommuteConfig).mockResolvedValue([commute]);
  vi.mocked(api.saveCommuteConfig).mockResolvedValue(commute);

  render(Page);

  const returnNotify = (await screen.findByLabelText('Notify at (return)')) as HTMLInputElement;
  expect(returnNotify.disabled).toBe(false);

  const returnTripCheckbox = screen.getByLabelText('Check my return trip too');
  await fireEvent.click(returnTripCheckbox);

  expect(returnNotify.disabled).toBe(true);

  await fireEvent.click(screen.getByRole('button', { name: 'Save and check weather' }));
  await waitFor(() => expect(api.saveCommuteConfig).toHaveBeenCalledTimes(1));

  expect(vi.mocked(api.saveCommuteConfig).mock.calls[0][0]).toMatchObject({
    id: 6,
    schedule_time: '08:00',
    return_schedule_time: null,
    notification_time: '07:30',
    return_notification_time: null
  });
});

