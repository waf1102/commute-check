import { describe, it, expect, vi, beforeEach } from 'vitest';
import { getCommuteStats, recordDecision } from './api';

describe('API analytics client', () => {
  const originalFetch = global.fetch;

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('omits user_id query param when userId is undefined or empty', async () => {
    let capturedUrl = '';
    global.fetch = vi.fn().mockImplementation((url) => {
      capturedUrl = String(url);
      return Promise.resolve({
        ok: true,
        json: async () => [],
      });
    });

    await getCommuteStats(undefined, '2026-10-01', '2026-10-03');
    expect(capturedUrl).toContain('start_date=2026-10-01');
    expect(capturedUrl).toContain('end_date=2026-10-03');
    expect(capturedUrl).not.toContain('user_id');

    await getCommuteStats('', '2026-10-01', '2026-10-03');
    expect(capturedUrl).not.toContain('user_id');

    global.fetch = originalFetch;
  });

  it('includes user_id query param when userId is provided', async () => {
    let capturedUrl = '';
    global.fetch = vi.fn().mockImplementation((url) => {
      capturedUrl = String(url);
      return Promise.resolve({
        ok: true,
        json: async () => [],
      });
    });

    await getCommuteStats('42', '2026-10-01', '2026-10-03');
    expect(capturedUrl).toContain('user_id=42');
    expect(capturedUrl).toContain('start_date=2026-10-01');
    expect(capturedUrl).toContain('end_date=2026-10-03');

    global.fetch = originalFetch;
  });

  it('sends POST request to record-decision with json payload', async () => {
    let capturedUrl = '';
    let capturedOptions: any = {};
    global.fetch = vi.fn().mockImplementation((url, options) => {
      capturedUrl = String(url);
      capturedOptions = options;
      return Promise.resolve({
        ok: true,
        json: async () => ({ id: 1, commute_type: 'riding' }),
      });
    });

    const res = await recordDecision({ decision: 'riding', commute_distance_km: 15.0 });
    expect(capturedUrl).toContain('/api/analytics/record-decision');
    expect(capturedOptions.method).toBe('POST');
    expect(JSON.parse(capturedOptions.body)).toEqual({
      decision: 'riding',
      commute_distance_km: 15.0,
    });
    expect(res.commute_type).toBe('riding');

    global.fetch = originalFetch;
  });
});
