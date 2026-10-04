import { get } from 'svelte/store';
import { jwt_token, user } from './auth';
import type { Commute } from './commute';

export interface Thresholds {
  min_temp_caution: number;
  min_temp_no_go: number;
  max_wind_caution: number;
  max_wind_no_go: number;
  rain_threshold: number;
}
export interface Weather {
  temperature: number;
  apparent_temp: number;
  wind_speed: number;
  wind_gusts?: number;
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
  weather?: Weather;
  waypoint_evaluations?: {
    name: string;
    estimated_arrival_time: string;
    status: string;
    reasons: string[];
  }[];
}
export interface Waypoint {
  name: string;
  lat: number | null;
  lon: number | null;
  order?: number;
}
export interface RouteAssessmentResult {
  assessment_date?: string;
  checked_at?: string;
  timezone?: string;
  routing_estimated?: boolean;
  overall_status: string;
  overall_score: number;
  outbound_leg: LegAssessment;
  return_leg?: LegAssessment | null;
  recommendation: string;
}
export interface DailyStats {
  date: string;
  days_ridden: number;
  days_driven: number;
  days_total: number;
}
export interface Place {
  name: string;
  lat: number;
  lon: number;
  timezone: string;
}

export async function authenticatedFetch(
  input: RequestInfo,
  init?: RequestInit
): Promise<Response> {
  const token = get(jwt_token);
  const headers = new Headers(init?.headers);
  if (token) headers.set('Authorization', `Bearer ${token}`);
  let response: Response;
  try {
    response = await fetch(input, {
      ...init,
      headers,
      signal: init?.signal || AbortSignal.timeout(60000)
    });
  } catch {
    throw new Error('Cannot reach the server. Check your connection and try again.');
  }
  if (response.status === 401) {
    jwt_token.set(null);
    user.set(null);
    localStorage.removeItem('jwt_token');
    throw new Error('Your session has ended. Please sign in again.');
  }
  if (!response.ok) {
    const data = await response.json().catch(() => ({}));
    const detail = data.detail;
    throw new Error(
      typeof detail === 'string'
        ? detail
        : detail?.[0]?.msg || 'Something went wrong. Please try again.'
    );
  }
  return response;
}
async function request<T>(path: string, method = 'GET', body?: unknown): Promise<T> {
  const response = await authenticatedFetch(`/api${path}`, {
    method,
    ...(body === undefined
      ? {}
      : { headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) })
  });
  return response.json();
}
export const getCommuteConfig = () => request<Commute[]>('/config');
export const saveCommuteConfig = (config: Commute) => request<Commute>('/config', 'POST', config);
export const deleteCommuteConfig = (id: number) =>
  request<{ status: string }>(`/config/${id}`, 'DELETE');
export const testWebhook = (config: Commute) => request('/test-webhook', 'POST', config);
export const checkRoute = ({ commute_id }: { commute_id: number }) =>
  request<RouteAssessmentResult>(`/check?commute_id=${commute_id}&save_history=true`, 'POST');
export const getCommuteStats = (startDate: string, endDate: string) =>
  request<DailyStats[]>(
    `/analytics/commute-stats/daily?${new URLSearchParams({ start_date: startDate, end_date: endDate })}`
  );
export const recordDecision = (params: { decision: 'riding' | 'driving'; date: string }) =>
  request('/analytics/record-decision', 'POST', params);
export const searchPlaces = (query: string) =>
  request<Place[]>(`/places?q=${encodeURIComponent(query)}`);
export const getVapidPublicKey = () => request<{ public_key: string }>('/push/vapid-public-key');
export const subscribePush = (data: {
  endpoint: string;
  keys: { p256dh: string; auth: string };
  user_agent?: string;
}) => request('/push/subscribe', 'POST', data);
export const unsubscribePush = (endpoint: string) =>
  request('/push/unsubscribe', 'DELETE', { endpoint });
export const sendTestPush = () =>
  request<{ delivered: number; failed: number }>('/push/test', 'POST');

export function urlBase64ToUint8Array(base64String: string): Uint8Array<ArrayBuffer> {
  const padding = '='.repeat((4 - (base64String.length % 4)) % 4);
  const base64 = (base64String + padding).replace(/-/g, '+').replace(/_/g, '/');
  const rawData = window.atob(base64);
  const outputArray = new Uint8Array(rawData.length);
  for (let i = 0; i < rawData.length; ++i) outputArray[i] = rawData.charCodeAt(i);
  return outputArray;
}
