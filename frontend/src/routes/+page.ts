import type { PageLoad } from './$types';
import { browser } from '$app/environment';

export const load: PageLoad = async ({ fetch }) => {
    let lat = 51.5074;
    let lon = -0.1278;
    let queryParams = new URLSearchParams();

    if (browser) {
        const stored = localStorage.getItem('commute-settings');
        if (stored) {
            const settings = JSON.parse(stored);
            lat = settings.lat || lat;
            lon = settings.lon || lon;
            if (settings.min_temp_caution) queryParams.append('min_temp_caution', settings.min_temp_caution);
            if (settings.min_temp_no_go) queryParams.append('min_temp_no_go', settings.min_temp_no_go);
            if (settings.max_wind_caution) queryParams.append('max_wind_caution', settings.max_wind_caution);
            if (settings.max_wind_no_go) queryParams.append('max_wind_no_go', settings.max_wind_no_go);
            if (settings.rain_threshold) queryParams.append('rain_threshold', settings.rain_threshold);
            if (settings.webhook_url) queryParams.append('webhook_url', settings.webhook_url);
        }
    }

    queryParams.append('lat', lat.toString());
    queryParams.append('lon', lon.toString());
    
    // Use an environment variable if available, otherwise default to localhost
    const backendUrl = (import.meta as any).env?.VITE_BACKEND_URL || 'http://localhost:8000';
    
    try {
        const response = await fetch(`${backendUrl}/assess?${queryParams.toString()}`);
        if (!response.ok) {
            throw new Error('Failed to fetch assessment');
        }
        const data = await response.json();
        return { assessment: data };
    } catch (error) {
        console.error('Fetch error:', error);
        return { 
            assessment: null,
            error: 'Could not load weather assessment. Is the backend running?'
        };
    }
};
