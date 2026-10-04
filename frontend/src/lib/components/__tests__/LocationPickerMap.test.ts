import { render, screen, fireEvent, waitFor } from '@testing-library/svelte';
import LocationPickerMap from '../LocationPickerMap.svelte';
import { describe, it, expect, vi, beforeEach } from 'vitest';

describe('LocationPickerMap Component (LocationPickerMap.svelte)', () => {
  const mockOrigin = { lat: 37.7749, lon: -122.4194, name: 'Home' };
  const mockDestination = { lat: 37.7891, lon: -122.4014, name: 'Office' };
  const mockWaypoints = [
    { id: 'wp-1', name: 'Coffee Stop', lat: 37.7800, lon: -122.4100 },
    { id: 'wp-2', name: 'Charging Station', lat: 37.7850, lon: -122.4050 }
  ];

  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it('mounts cleanly and renders canvas, target pills, and coordinates summary', async () => {
    render(LocationPickerMap, {
      props: {
        origin: mockOrigin,
        destination: mockDestination,
        waypoints: mockWaypoints,
        onupdateOrigin: vi.fn(),
        onupdateDestination: vi.fn(),
        onupdateWaypoint: vi.fn()
      }
    });

    // Check canvas element
    const canvas = screen.getByTestId('location-picker-canvas');
    expect(canvas).toBeInTheDocument();
    expect(canvas).toHaveAttribute('aria-label', 'Interactive Location Picker Map');

    // Check target selection pills
    expect(screen.getByTestId('target-select-origin')).toBeInTheDocument();
    expect(screen.getByTestId('target-select-destination')).toBeInTheDocument();
    expect(screen.getByTestId('target-select-waypoint-0')).toBeInTheDocument();
    expect(screen.getByTestId('target-select-waypoint-1')).toBeInTheDocument();

    // Check coordinates summary chips
    const originChip = screen.getByTestId('origin-coords-chip');
    expect(originChip).toHaveTextContent('37.7749, -122.4194');

    const destChip = screen.getByTestId('destination-coords-chip');
    expect(destChip).toHaveTextContent('37.7891, -122.4014');

    const wp0Chip = screen.getByTestId('waypoint-coords-chip-0');
    expect(wp0Chip).toHaveTextContent('37.78, -122.41');
  });

  it('switches active target when pill is clicked', async () => {
    render(LocationPickerMap, {
      props: {
        origin: mockOrigin,
        destination: mockDestination,
        waypoints: mockWaypoints,
        onupdateOrigin: vi.fn(),
        onupdateDestination: vi.fn(),
        onupdateWaypoint: vi.fn()
      }
    });

    const hint = screen.getByTestId('map-picker-hint');
    expect(hint).toHaveTextContent('Active: Origin (Home)');

    // Click Destination pill
    const destPill = screen.getByTestId('target-select-destination');
    await fireEvent.click(destPill);

    expect(destPill).toHaveAttribute('aria-checked', 'true');
    expect(hint).toHaveTextContent('Active: Destination (Office)');

    // Click Waypoint 1 pill
    const wp1Pill = screen.getByTestId('target-select-waypoint-0');
    await fireEvent.click(wp1Pill);

    expect(wp1Pill).toHaveAttribute('aria-checked', 'true');
    expect(hint).toHaveTextContent('Active: Waypoint 1: Coffee Stop');
  });

  it('updates Origin coordinates when map coordinate select occurs while Origin is active', async () => {
    const onupdateOrigin = vi.fn();
    const onupdateDestination = vi.fn();

    render(LocationPickerMap, {
      props: {
        origin: mockOrigin,
        destination: mockDestination,
        waypoints: mockWaypoints,
        onupdateOrigin,
        onupdateDestination,
        onupdateWaypoint: vi.fn()
      }
    });

    const canvas = screen.getByTestId('location-picker-canvas') as any;

    await waitFor(() => {
      expect(canvas.__handleMapCoordinateSelect).toBeDefined();
    });

    // Simulate clicking map at new coordinates (e.g. 37.7755, -122.4180)
    canvas.__handleMapCoordinateSelect(37.7755, -122.4180);

    expect(onupdateOrigin).toHaveBeenCalledWith({
      lat: 37.7755,
      lon: -122.418
    });
    expect(onupdateDestination).not.toHaveBeenCalled();

    const statusNotice = await screen.findByTestId('map-status-notice');
    expect(statusNotice).toHaveTextContent('Origin set to 37.7755, -122.418');
  });

  it('updates Destination coordinates when map coordinate select occurs while Destination is active', async () => {
    const onupdateDestination = vi.fn();

    render(LocationPickerMap, {
      props: {
        origin: mockOrigin,
        destination: mockDestination,
        waypoints: mockWaypoints,
        onupdateOrigin: vi.fn(),
        onupdateDestination,
        onupdateWaypoint: vi.fn()
      }
    });

    const destPill = screen.getByTestId('target-select-destination');
    await fireEvent.click(destPill);

    const canvas = screen.getByTestId('location-picker-canvas') as any;
    await waitFor(() => {
      expect(canvas.__handleMapCoordinateSelect).toBeDefined();
    });

    canvas.__handleMapCoordinateSelect(37.7900, -122.4000);

    expect(onupdateDestination).toHaveBeenCalledWith({
      lat: 37.79,
      lon: -122.4
    });
  });

  it('updates Waypoint coordinates when map coordinate select occurs while Waypoint is active', async () => {
    const onupdateWaypoint = vi.fn();

    render(LocationPickerMap, {
      props: {
        origin: mockOrigin,
        destination: mockDestination,
        waypoints: mockWaypoints,
        onupdateOrigin: vi.fn(),
        onupdateDestination: vi.fn(),
        onupdateWaypoint
      }
    });

    const wp2Pill = screen.getByTestId('target-select-waypoint-1');
    await fireEvent.click(wp2Pill);

    const canvas = screen.getByTestId('location-picker-canvas') as any;
    await waitFor(() => {
      expect(canvas.__handleMapCoordinateSelect).toBeDefined();
    });

    canvas.__handleMapCoordinateSelect(37.7865, -122.4045);

    expect(onupdateWaypoint).toHaveBeenCalledWith(1, {
      lat: 37.7865,
      lon: -122.4045
    });
  });

  it('adds a new waypoint when Add Waypoint Pin target is active and map is clicked', async () => {
    const onaddWaypoint = vi.fn();

    render(LocationPickerMap, {
      props: {
        origin: mockOrigin,
        destination: mockDestination,
        waypoints: mockWaypoints,
        onupdateOrigin: vi.fn(),
        onupdateDestination: vi.fn(),
        onupdateWaypoint: vi.fn(),
        onaddWaypoint
      }
    });

    const addWpPill = screen.getByTestId('target-select-new-waypoint');
    await fireEvent.click(addWpPill);

    const canvas = screen.getByTestId('location-picker-canvas') as any;
    await waitFor(() => {
      expect(canvas.__handleMapCoordinateSelect).toBeDefined();
    });

    canvas.__handleMapCoordinateSelect(37.7820, -122.4080);

    expect(onaddWaypoint).toHaveBeenCalledWith({
      lat: 37.782,
      lon: -122.408
    });
  });

  it('updates active target coordinates via browser Geolocation API button', async () => {
    const mockGeolocation = {
      getCurrentPosition: vi.fn().mockImplementation((success) => {
        success({
          coords: {
            latitude: 37.7760,
            longitude: -122.4170
          }
        });
      })
    };
    (globalThis.navigator as any).geolocation = mockGeolocation;

    const onupdateOrigin = vi.fn();

    render(LocationPickerMap, {
      props: {
        origin: mockOrigin,
        destination: mockDestination,
        waypoints: mockWaypoints,
        onupdateOrigin,
        onupdateDestination: vi.fn(),
        onupdateWaypoint: vi.fn()
      }
    });

    const locBtn = screen.getByTestId('use-current-location-btn');
    await fireEvent.click(locBtn);

    expect(mockGeolocation.getCurrentPosition).toHaveBeenCalled();
    expect(onupdateOrigin).toHaveBeenCalledWith({
      lat: 37.776,
      lon: -122.417
    });

    const statusNotice = await screen.findByTestId('map-status-notice');
    expect(statusNotice).toHaveTextContent('Updated Origin (Home) to current location');
  });

  it('updates coordinates when an address is searched in the integrated AddressSearch', async () => {
    const mockNominatimResponse = [
      {
        place_id: 201,
        name: 'Transamerica Pyramid',
        display_name: 'Transamerica Pyramid, Montgomery St, San Francisco, CA',
        lat: '37.7952',
        lon: '-122.4028'
      }
    ];

    vi.spyOn(globalThis, 'fetch').mockResolvedValue({
      ok: true,
      json: async () => mockNominatimResponse
    } as Response);

    const onupdateOrigin = vi.fn();

    render(LocationPickerMap, {
      props: {
        origin: mockOrigin,
        destination: mockDestination,
        waypoints: mockWaypoints,
        onupdateOrigin,
        onupdateDestination: vi.fn(),
        onupdateWaypoint: vi.fn()
      }
    });

    const searchInput = screen.getByTestId('map-address-search-input');
    await fireEvent.input(searchInput, { target: { value: 'Transamerica' } });

    const searchBtn = screen.getByTestId('map-address-search-btn');
    await fireEvent.click(searchBtn);

    const result0 = await screen.findByTestId('map-address-search-result-0');
    expect(result0).toHaveTextContent('Transamerica Pyramid');

    await fireEvent.click(result0);

    expect(onupdateOrigin).toHaveBeenCalledWith({
      lat: 37.7952,
      lon: -122.4028
    });
  });
});
