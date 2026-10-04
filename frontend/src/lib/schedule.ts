export interface DayOption {
  key: string; // 'mon', 'tue', etc.
  label: string; // 'Mon', 'Tue', etc.
  fullName: string; // 'Monday', 'Tuesday', etc.
}

export const DAYS_OF_WEEK: DayOption[] = [
  { key: 'mon', label: 'Mon', fullName: 'Monday' },
  { key: 'tue', label: 'Tue', fullName: 'Tuesday' },
  { key: 'wed', label: 'Wed', fullName: 'Wednesday' },
  { key: 'thu', label: 'Thu', fullName: 'Thursday' },
  { key: 'fri', label: 'Fri', fullName: 'Friday' },
  { key: 'sat', label: 'Sat', fullName: 'Saturday' },
  { key: 'sun', label: 'Sun', fullName: 'Sunday' }
];

export const ORDERED_DAY_KEYS = DAYS_OF_WEEK.map((d) => d.key);
export const WEEKDAYS = ['mon', 'tue', 'wed', 'thu', 'fri'];
export const ALL_DAYS = ['mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun'];

const DAY_ALIASES: Record<string, string> = {
  monday: 'mon',
  tuesday: 'tue',
  wednesday: 'wed',
  thursday: 'thu',
  friday: 'fri',
  saturday: 'sat',
  sunday: 'sun'
};

/**
 * Normalizes an individual day token into a 3-letter abbreviation ('mon' - 'sun').
 * Supports 3-letter names, full day names, and numeric cron representations (0-6).
 */
export function normalizeDayToken(token: string): string | null {
  const t = token.trim().toLowerCase();
  if (DAY_ALIASES[t]) return DAY_ALIASES[t];
  if (ORDERED_DAY_KEYS.includes(t)) return t;

  // Numeric support (0=Mon through 6=Sun in APScheduler standard)
  const num = parseInt(t, 10);
  if (!isNaN(num) && num >= 0 && num < ORDERED_DAY_KEYS.length) {
    return ORDERED_DAY_KEYS[num];
  }
  return null;
}

/**
 * Parses a backend cron days_of_week expression into an array of active day keys.
 * Handles ranges (e.g. 'mon-fri', 'sat-sun'), comma-separated lists (e.g. 'mon,wed,thu'),
 * wildcards ('*'), and mixed whitespace/casing.
 */
export function parseDaysOfWeek(value?: string | null): string[] {
  if (!value || typeof value !== 'string') return [];
  const trimmed = value.trim().toLowerCase();
  if (!trimmed) return [];
  if (trimmed === '*') return [...ALL_DAYS];

  const selected = new Set<string>();
  const tokens = trimmed.split(',');

  for (const rawToken of tokens) {
    const token = rawToken.trim();
    if (!token) continue;

    if (token.includes('-')) {
      const parts = token.split('-');
      if (parts.length === 2) {
        const startDay = normalizeDayToken(parts[0]);
        const endDay = normalizeDayToken(parts[1]);
        if (startDay && endDay) {
          const startIdx = ORDERED_DAY_KEYS.indexOf(startDay);
          const endIdx = ORDERED_DAY_KEYS.indexOf(endDay);
          if (startIdx !== -1 && endIdx !== -1) {
            if (startIdx <= endIdx) {
              for (let i = startIdx; i <= endIdx; i++) {
                selected.add(ORDERED_DAY_KEYS[i]);
              }
            } else {
              // Wrap around (e.g. fri-mon)
              for (let i = startIdx; i < ORDERED_DAY_KEYS.length; i++) {
                selected.add(ORDERED_DAY_KEYS[i]);
              }
              for (let i = 0; i <= endIdx; i++) {
                selected.add(ORDERED_DAY_KEYS[i]);
              }
            }
          }
        }
      }
    } else {
      const day = normalizeDayToken(token);
      if (day) {
        selected.add(day);
      }
    }
  }

  // Return in canonical Monday-Sunday order
  return ORDERED_DAY_KEYS.filter((d) => selected.has(d));
}

/**
 * Serializes an array of active day keys back to backend cron format (e.g. 'mon,wed,thu').
 * Guarantees canonical Monday-Sunday ordering and deduplication.
 */
export function serializeDaysOfWeek(days: string[]): string {
  if (!days || days.length === 0) return '';
  const filtered = ORDERED_DAY_KEYS.filter((d) => days.includes(d));
  return filtered.join(',');
}

/**
 * Formats active days into a friendly human-readable summary.
 */
export function formatDaysSummary(days: string[]): string {
  if (!days || days.length === 0) return 'No days selected';
  const serialized = serializeDaysOfWeek(days);
  if (serialized === 'mon,tue,wed,thu,fri') return 'Weekdays (Mon–Fri)';
  if (serialized === 'mon,tue,wed,thu,fri,sat,sun') return 'All Days (Everyday)';
  if (serialized === 'sat,sun') return 'Weekends (Sat–Sun)';

  return days.map((k) => DAYS_OF_WEEK.find((d) => d.key === k)?.label || k).join(', ');
}
