import { render, screen, fireEvent, cleanup, waitFor } from '@testing-library/svelte';
import { afterEach, expect, it, vi } from 'vitest';
import PlacePicker from '../PlacePicker.svelte';
import { searchPlaces } from '$lib/api';

vi.mock('$lib/api', () => ({ searchPlaces: vi.fn() }));

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
  vi.useRealTimers();
});

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

it('automatically fetches suggestions as user types', async () => {
  vi.useFakeTimers({ toFake: ['setTimeout', 'clearTimeout'] });
  const place = {
    name: 'Somerville, Massachusetts, US',
    lat: 42.38,
    lon: -71.1,
    timezone: 'America/New_York'
  };
  vi.mocked(searchPlaces).mockResolvedValue([place]);
  render(PlacePicker, { id: 'origin', label: 'Leaving from' });

  await fireEvent.input(screen.getByLabelText('Leaving from town or postal code'), {
    target: { value: 'Somerville' }
  });

  await vi.advanceTimersByTimeAsync(350);
  expect(searchPlaces).toHaveBeenCalledWith('Somerville');
  expect(await screen.findByRole('button', { name: place.name })).toBeInTheDocument();
});

it('does not have manual coordinate input fields', () => {
  render(PlacePicker, { id: 'origin', label: 'Leaving from' });
  expect(screen.queryByLabelText(/latitude/i)).not.toBeInTheDocument();
  expect(screen.queryByLabelText(/longitude/i)).not.toBeInTheDocument();
  expect(screen.queryByText(/Enter exact coordinates/i)).not.toBeInTheDocument();
});

it('renders interactive map and sets location on map click', async () => {
  const onselect = vi.fn();
  render(PlacePicker, { id: 'origin', label: 'Leaving from', onselect });

  const mapContainer = screen.getByLabelText('Leaving from map');
  expect(mapContainer).toBeInTheDocument();

  await waitFor(() => {
    expect((mapContainer as any)._leaflet_map).toBeDefined();
  });

  const map = (mapContainer as any)._leaflet_map;
  map.fire('click', { latlng: { lat: 42.3601, lng: -71.0589 } });

  await waitFor(() => {
    expect(onselect).toHaveBeenCalledWith(
      expect.objectContaining({
        lat: 42.3601,
        lon: -71.0589
      })
    );
  });
});
