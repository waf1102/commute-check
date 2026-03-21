import type { PageLoad } from './$types';

export const load: PageLoad = async ({ fetch }) => {
    const backendUrl = import.meta.env?.VITE_BACKEND_URL || 'http://localhost:8000';
    
    try {
        // 1. Fetch all commutes
        const configResponse = await fetch(`${backendUrl}/config`);
        if (!configResponse.ok) {
            throw new Error('Failed to load commutes from backend');
        }
        
        const commutes = await configResponse.json();
        
        if (!commutes || commutes.length === 0) {
            return { assessments: [], error: 'No commutes configured. Please visit Settings to create one.' };
        }

        // 2. Fetch assessment for each commute
        const assessments = await Promise.all(commutes.map(async (commute: any) => {
            const queryParams = new URLSearchParams({
                lat: commute.lat.toString(),
                lon: commute.lon.toString(),
                min_temp: commute.min_temp_caution.toString(),
                max_temp: 95, // Default from main.py if not specified
                max_wind: commute.max_wind_caution.toString(),
                max_precip: commute.rain_threshold.toString(),
                unit_system: commute.unit_system || 'imperial'
            });

            try {
                const assessRes = await fetch(`${backendUrl}/assess?${queryParams.toString()}`);
                if (!assessRes.ok) return { ...commute, assessment: null, error: 'Assessment failed' };
                const assessmentData = await assessRes.json();
                return { ...commute, assessment: assessmentData };
            } catch (e) {
                return { ...commute, assessment: null, error: 'Network error' };
            }
        }));

        return { assessments };

    } catch (error) {
        console.error('Fetch error:', error);
        return { 
            assessments: [],
            error: 'Could not load weather assessments. Is the backend running?'
        };
    }
};
