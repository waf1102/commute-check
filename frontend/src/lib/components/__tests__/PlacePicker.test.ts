import { render, screen, fireEvent, cleanup } from '@testing-library/svelte';
import { afterEach, expect, it, vi } from 'vitest';
import PlacePicker from '../PlacePicker.svelte';
import { searchPlaces } from '$lib/api';
vi.mock('$lib/api', () => ({ searchPlaces: vi.fn() }));
afterEach(cleanup);
it('lets people select an unambiguous search result', async () => {
  const place = {
    name: 'Cambridge, Massachusetts, US',
    lat: 42.3,
    lon: -71.1,
    timezone: 'America/New_York'
  };
  vi.mocked(searchPlaces).mockResolvedValue([place]);
  const onselect = vi.fn();
  render(PlacePicker, { id: 'origin', label: 'Leaving from', onselect });
  await fireEvent.input(screen.getByLabelText('Leaving from town or postal code'), {
    target: { value: 'Cambridge' }
  });
  await fireEvent.click(screen.getByRole('button', { name: 'Find' }));
  await fireEvent.click(await screen.findByRole('button', { name: place.name }));
  expect(onselect).toHaveBeenCalledWith(place);
  expect(screen.getByText(place.name)).toBeInTheDocument();
});

it('explains a location permission failure and leaves search available', async () => {
  Object.defineProperty(navigator, 'geolocation', {
    configurable: true,
    value: {
      getCurrentPosition: (_success: unknown, failure: (error: unknown) => void) =>
        failure({ code: 1 })
    }
  });
  render(PlacePicker, { id: 'origin', label: 'Leaving from' });
  await fireEvent.click(screen.getByRole('button', { name: /Use my current location/ }));
  expect(await screen.findByRole('status')).toHaveTextContent('Search for a town');
  expect(screen.getByLabelText('Leaving from town or postal code')).toBeEnabled();
});
