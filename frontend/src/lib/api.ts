import { get } from 'svelte/store';
import { jwt_token } from './auth'; // Assuming auth.ts is in the same directory

const API_BASE_URL = '/api'; // Adjust if your API is hosted elsewhere

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
