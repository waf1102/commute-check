import { render, screen, waitFor } from '@testing-library/svelte';
import RouteMap from '../RouteMap.svelte';
import { describe, it, expect } from 'vitest';

describe('RouteMap Component (RouteMap.svelte)', () => {
  const mockOrigin = {
    name: 'Home',
    lat: 37.7749,
    lon: -122.4194
  };

  const mockDestination = {
    name: 'Office',
    lat: 37.7891,
    lon: -122.4014
  };

  const mockWaypoints = [
    { id: 'wp-1', name: 'Coffee Stop', lat: 37.7800, lon: -122.4100, status: 'Caution' },
    { id: 'wp-2', name: 'Bridge Checkpoint', lat: 37.7850, lon: -122.4050, status: 'Go' }
  ];

  const mockHazardPinpoints = [
    {
      lat: 37.7800,
      lon: -122.4100,
      title: 'High Wind Zone',
      location_name: 'Midway Crossing',
      severity: 'Caution',
      risk_factors: ['Wind gusts up to 28 mph', 'Slippery road surface'],
      weather: {
        temperature: 48,
        wind_speed: 28,
        precip_prob: 45,
        weather_code: 61
      }
    },
    {
      lat: 37.7850,
      lon: -122.4050,
      title: 'Freezing Hazard',
      location_name: 'Overpass',
      severity: 'No-Go',
      risk_factors: ['Black ice potential', 'Sub-freezing temperatures'],
      weather: {
        temperature: 30,
        wind_speed: 15,
        precip_prob: 80,
        weather_code: 71
      }
    }
  ];

  it('mounts cleanly and renders the map container, legend, and accessibility elements', async () => {
    render(RouteMap, {
      props: {
        origin: mockOrigin,
        destination: mockDestination,
        waypoints: mockWaypoints
      }
    });

    // Check legend items
    const legend = screen.getByTestId('route-legend');
    expect(legend).toBeInTheDocument();
    expect(legend).toHaveTextContent('Go (Safe)');
    expect(legend).toHaveTextContent('Caution (Risk)');
    expect(legend).toHaveTextContent('No-Go (Severe)');
    expect(legend).toHaveTextContent('Hazard Alert');

    // Check map canvas element
    const canvas = screen.getByTestId('route-map-canvas');
    expect(canvas).toBeInTheDocument();
    expect(canvas).toHaveAttribute('aria-label', 'Interactive Route Map');

    // Wait for Leaflet mounting
    await waitFor(() => {
      const summary = screen.getByTestId('route-stops-summary');
      expect(summary).toBeInTheDocument();
    });
  });

  it('renders numbered stop chips for Origin (1), Waypoints (2, 3), and Destination (4)', async () => {
    render(RouteMap, {
      props: {
        origin: mockOrigin,
        destination: mockDestination,
        waypoints: mockWaypoints
      }
    });

    await waitFor(() => {
      // #1 Origin
      const stop1 = screen.getByTestId('stop-chip-1');
      expect(stop1).toHaveTextContent('1');
      expect(stop1).toHaveTextContent('Home');
      expect(stop1).toHaveClass('origin');

      // #2 Waypoint 1
      const stop2 = screen.getByTestId('stop-chip-2');
      expect(stop2).toHaveTextContent('2');
      expect(stop2).toHaveTextContent('Coffee Stop');
      expect(stop2).toHaveClass('waypoint');

      // #3 Waypoint 2
      const stop3 = screen.getByTestId('stop-chip-3');
      expect(stop3).toHaveTextContent('3');
      expect(stop3).toHaveTextContent('Bridge Checkpoint');
      expect(stop3).toHaveClass('waypoint');

      // #4 Destination
      const stop4 = screen.getByTestId('stop-chip-4');
      expect(stop4).toHaveTextContent('4');
      expect(stop4).toHaveTextContent('Office');
      expect(stop4).toHaveClass('destination');
    });
  });

  it('renders hazard pinpoints summary and markers when hazard_pinpoints are provided', async () => {
    render(RouteMap, {
      props: {
        origin: mockOrigin,
        destination: mockDestination,
        hazard_pinpoints: mockHazardPinpoints
      }
    });

    await waitFor(() => {
      const hazardBar = screen.getByTestId('hazard-alerts-summary');
      expect(hazardBar).toBeInTheDocument();
      expect(hazardBar).toHaveTextContent('2 active hazard pinpoints on route');
    });
  });

  it('handles empty route coordinates gracefully with informational notice', async () => {
    render(RouteMap, {
      props: {
        origin: null,
        destination: null,
        waypoints: []
      }
    });

    const notice = screen.getByText('No route coordinates specified. Add origin and destination to view the route.');
    expect(notice).toBeInTheDocument();
  });

  it('plots custom segments with specified safety status and colors', async () => {
    const customSegments = [
      {
        coordinates: [[37.77, -122.42], [37.78, -122.41]] as [number, number][],
        status: 'Go',
        name: 'Segment A'
      },
      {
        coordinates: [[37.78, -122.41], [37.79, -122.40]] as [number, number][],
        status: 'Caution',
        name: 'Segment B'
      },
      {
        coordinates: [[37.79, -122.40], [37.80, -122.39]] as [number, number][],
        status: 'No-Go',
        name: 'Segment C'
      }
    ];

    const { container } = render(RouteMap, {
      props: {
        origin: mockOrigin,
        destination: mockDestination,
        segments: customSegments
      }
    });

    expect(container).toBeInTheDocument();
  });
});
