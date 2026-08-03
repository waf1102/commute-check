import type { PageLoad } from './$types';
import { getCommuteConfig, checkRoute } from '../lib/api';
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

        // 2. Fetch assessment for each commute using checkRoute
        const assessments = await Promise.all(commutes.map(async (commute: any) => {
            try {
                const assessmentData = await checkRoute({
                    commute_id: commute.id,
                    lat: commute.lat,
                    lon: commute.lon,
                    dest_name: commute.dest_name,
                    dest_lat: commute.dest_lat,
                    dest_lon: commute.dest_lon,
                    schedule_time: commute.schedule_time,
                    return_schedule_time: commute.return_schedule_time
                });
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
