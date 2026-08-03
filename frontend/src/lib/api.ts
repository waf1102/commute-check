import { get } from 'svelte/store';
import { jwt_token } from './auth'; // Assuming auth.ts is in the same directory

const API_BASE_URL = '/api'; // Adjust if your API is hosted elsewhere

export interface Thresholds {
  min_temp_caution: number;
  min_temp_no_go: number;
  max_wind_caution: number;
  max_wind_no_go: number;
  rain_threshold: number;
}

export interface HourlyForecastItem {
  time: string;
  temperature: number;
  apparent_temp: number;
  wind_speed: number;
  precip_prob: number;
  weather_code: number;
}

export interface LegAssessment {
  leg_type: string;
  location_name: string;
  schedule_time: string;
  status: string;
  score: number;
  reasons: string[];
  weather?: HourlyForecastItem;
}

export interface RouteAssessmentResult {
  overall_status: string;
  overall_score: number;
  outbound_leg: LegAssessment;
  return_leg?: LegAssessment;
  recommendation: string;
}

export interface ForecastResponse {
  unit_system: string;
  thresholds: Thresholds;
  hourly: HourlyForecastItem[];
  destination_hourly?: HourlyForecastItem[];
}

async function authenticatedFetch(input: RequestInfo, init?: RequestInit): Promise<Response> {
  const token = get(jwt_token);
  const headers = new Headers(init?.headers);

  if (token) {
    headers.set('Authorization', `Bearer ${token}`);
  }

  const response = await fetch(input, {
    ...init,
    headers,
  });

  // Handle unauthorized responses globally if needed
  if (response.status === 401) {
    // Optionally trigger logout or redirect to login
    // For now, let's just let the component handle it or throw
  }

  return response;
}

export async function getCommuteData(): Promise<any> { // Replace 'any' with actual type later
  const response = await authenticatedFetch(`${API_BASE_URL}/commute`);
  if (!response.ok) {
    throw new Error('Failed to fetch commute data');
  }
  return response.json();
}

// Add other API functions here as needed.
export async function getCommuteConfig(): Promise<any> {
  const response = await authenticatedFetch(`${API_BASE_URL}/config`);
  if (!response.ok) {
    throw new Error('Failed to fetch commute config');
  }
  return response.json();
}

export async function getCommuteAssessment(queryParams: URLSearchParams): Promise<any> {
  const response = await authenticatedFetch(`${API_BASE_URL}/assess?${queryParams.toString()}`);
  if (!response.ok) {
    throw new Error('Failed to fetch commute assessment');
  }
  return response.json();
}

export async function getCommuteStats(userId: string, startDate: string, endDate: string): Promise<any> {
  const queryParams = new URLSearchParams({
    user_id: userId,
    start_date: startDate,
    end_date: endDate,
  });
  const response = await authenticatedFetch(`${API_BASE_URL}/analytics/commute-stats/daily?${queryParams.toString()}`);
  if (!response.ok) {
    throw new Error('Failed to fetch commute stats');
  }
  return response.json();
}

export async function getWeatherForecast(commuteId?: number, unitSystem: string = 'imperial'): Promise<ForecastResponse> {
  const queryParams = new URLSearchParams();
  if (commuteId !== undefined) {
    queryParams.append('commute_id', commuteId.toString());
  }
  if (unitSystem) {
    queryParams.append('unit_system', unitSystem);
  }
  const url = `${API_BASE_URL}/weather/forecast${queryParams.toString() ? '?' + queryParams.toString() : ''}`;
  const response = await authenticatedFetch(url);
  if (!response.ok) {
    throw new Error('Failed to fetch weather forecast');
  }
  return response.json();
}

export function urlBase64ToUint8Array(base64String: string): Uint8Array<ArrayBuffer> {
  const padding = '='.repeat((4 - (base64String.length % 4)) % 4);
  const base64 = (base64String + padding).replace(/-/g, '+').replace(/_/g, '/');
  const rawData = window.atob(base64);
  const outputArray = new Uint8Array(rawData.length);
  for (let i = 0; i < rawData.length; ++i) {
    outputArray[i] = rawData.charCodeAt(i);
  }
  return outputArray;
}

export async function getVapidPublicKey(): Promise<{ public_key: string }> {
  const response = await authenticatedFetch(`${API_BASE_URL}/push/vapid-public-key`);
  if (!response.ok) {
    throw new Error('Failed to fetch VAPID public key');
  }
  return response.json();
}

export async function subscribePush(subscriptionData: {
  endpoint: string;
  keys: { p256dh: string; auth: string };
  user_agent?: string;
}): Promise<any> {
  const response = await authenticatedFetch(`${API_BASE_URL}/push/subscribe`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(subscriptionData),
  });
  if (!response.ok) {
    throw new Error('Failed to subscribe to push notifications');
  }
  return response.json();
}

export async function unsubscribePush(endpoint: string): Promise<any> {
  const response = await authenticatedFetch(`${API_BASE_URL}/push/unsubscribe`, {
    method: 'DELETE',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ endpoint }),
  });
  if (!response.ok) {
    throw new Error('Failed to unsubscribe from push notifications');
  }
  return response.json();
}

export async function sendTestPush(): Promise<any> {
  const response = await authenticatedFetch(`${API_BASE_URL}/push/test`, {
    method: 'POST',
  });
  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new Error(errorData.detail || 'Failed to send test push notification');
  }
  return response.json();
}
