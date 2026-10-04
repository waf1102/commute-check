import type { Thresholds, Waypoint } from './api';

export interface Commute extends Thresholds {
  id?: number;
  name: string;
  origin_name: string;
  lat: number | null;
  lon: number | null;
  dest_name: string;
  dest_lat: number | null;
  dest_lon: number | null;
  schedule_time: string;
  return_schedule_time: string | null;
  days_of_week: string;
  timezone: string;
  unit_system: 'imperial' | 'metric';
  webhook_url: string | null;
  waypoints: Waypoint[];
}
export function newCommute(): Commute {
  return {
    name: 'My commute',
    origin_name: '',
    lat: null,
    lon: null,
    dest_name: '',
    dest_lat: null,
    dest_lon: null,
    schedule_time: '08:00',
    return_schedule_time: '17:00',
    days_of_week: 'mon-fri',
    timezone: Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC',
    unit_system: 'imperial',
    min_temp_caution: 45,
    min_temp_no_go: 38,
    max_wind_caution: 15,
    max_wind_no_go: 25,
    rain_threshold: 30,
    webhook_url: null,
    waypoints: []
  };
}
export function convertUnits(commute: Commute, unit: 'imperial' | 'metric'): Commute {
  if (unit === commute.unit_system) return commute;
  const metric = unit === 'metric';
  const round = (n: number) => Math.round(n * 10) / 10;
  const temp = (n: number) => round(metric ? ((n - 32) * 5) / 9 : (n * 9) / 5 + 32);
  const wind = (n: number) => round(metric ? n * 1.609344 : n / 1.609344);
  return {
    ...commute,
    unit_system: unit,
    min_temp_caution: temp(commute.min_temp_caution),
    min_temp_no_go: temp(commute.min_temp_no_go),
    max_wind_caution: wind(commute.max_wind_caution),
    max_wind_no_go: wind(commute.max_wind_no_go)
  };
}
export const verdict = (status: string) =>
  ({ Go: 'Good to ride', Caution: 'Take extra care', 'No-Go': 'Consider another way' })[status] ||
  'Forecast unavailable';
export const statusClass = (status: string) =>
  ({ Go: 'go', Caution: 'caution', 'No-Go': 'nogo' })[status] || '';
export function departureLabel(time: string, timezone = 'UTC'): string {
  if (!time.includes('T')) return time;
  return new Intl.DateTimeFormat(undefined, {
    weekday: 'short',
    hour: 'numeric',
    minute: '2-digit',
    timeZone: timezone
  }).format(new Date(time));
}
