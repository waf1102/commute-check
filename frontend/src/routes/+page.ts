import type { PageLoad } from './$types';
import { getCommuteConfig, getCommuteAssessment } from '../lib/api';
import { get } from 'svelte/store';
import { jwt_token } from '$lib/auth';

export const load: PageLoad = async () => {
    // Check for authentication token before fetching data
    const token = get(jwt_token);
    if (!token) {
        return {
            assessments: [],
            error: 'Please log in to view your commute data.'
        };
    }

    try {
        // 1. Fetch all commutes
        const commutes = await getCommuteConfig();
        
        if (!commutes || commutes.length === 0) {
            return { assessments: [], error: 'No commutes configured. Please visit Settings to create one.' };
        }

        // 2. Fetch assessment for each commute
        const assessments = await Promise.all(commutes.map(async (commute: any) => {
            const queryParams = new URLSearchParams({
                lat: commute.lat.toString(),
                lon: commute.lon.toString(),
                min_temp: commute.min_temp_caution.toString(),
                max_temp: '95', // Default from main.py if not specified
                max_wind: commute.max_wind_caution.toString(),
                max_precip: commute.rain_threshold.toString(),
                unit_system: commute.unit_system || 'imperial'
            });

            try {
                const assessmentData = await getCommuteAssessment(queryParams);
                return { ...commute, assessment: assessmentData };
            } catch (e) {
                return { ...commute, assessment: null, error: 'Assessment failed' };
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
