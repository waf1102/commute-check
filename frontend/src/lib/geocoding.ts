export interface GeocodeResult {
  place_id: number | string;
  name: string;
  display_name: string;
  lat: number;
  lon: number;
}

/**
 * Searches for an address or place using the OpenStreetMap Nominatim geocoding API.
 * 
 * @param query The address or location query string
 * @param fetchFn Fetch implementation (defaults to global fetch)
 * @returns Array of geocoded results with name, lat, and lon
 */
export async function searchAddress(query: string, fetchFn: typeof fetch = fetch): Promise<GeocodeResult[]> {
  const trimmed = query?.trim();
  if (!trimmed) return [];

  const url = `https://nominatim.openstreetmap.org/search?format=json&q=${encodeURIComponent(trimmed)}&limit=5`;
  const res = await fetchFn(url, {
    headers: {
      'Accept': 'application/json'
    }
  });

  if (!res.ok) {
    throw new Error(`Nominatim geocoding request failed with status: ${res.status}`);
  }

  const data = await res.json();
  if (!Array.isArray(data)) return [];

  return data.map((item: any) => {
    const rawLat = parseFloat(item.lat);
    const rawLon = parseFloat(item.lon);
    return {
      place_id: item.place_id,
      name: item.name || (item.display_name ? item.display_name.split(',')[0].trim() : 'Location'),
      display_name: item.display_name || '',
      lat: isNaN(rawLat) ? 0 : parseFloat(rawLat.toFixed(4)),
      lon: isNaN(rawLon) ? 0 : parseFloat(rawLon.toFixed(4))
    };
  });
}
