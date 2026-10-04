import { describe, it, expect } from 'vitest';
import {
  parseDaysOfWeek,
  serializeDaysOfWeek,
  normalizeDayToken,
  formatDaysSummary,
  DAYS_OF_WEEK,
  WEEKDAYS,
  ALL_DAYS
} from './schedule';

describe('schedule utility functions', () => {
  describe('normalizeDayToken', () => {
    it('normalizes 3-letter day names case-insensitively', () => {
      expect(normalizeDayToken('mon')).toBe('mon');
      expect(normalizeDayToken('MON')).toBe('mon');
      expect(normalizeDayToken(' Fri ')).toBe('fri');
      expect(normalizeDayToken('sun')).toBe('sun');
    });

    it('normalizes full day names', () => {
      expect(normalizeDayToken('monday')).toBe('mon');
      expect(normalizeDayToken('Wednesday')).toBe('wed');
      expect(normalizeDayToken('SUNDAY')).toBe('sun');
    });

    it('normalizes valid numeric day values (0-6)', () => {
      expect(normalizeDayToken('0')).toBe('mon');
      expect(normalizeDayToken('4')).toBe('fri');
      expect(normalizeDayToken('6')).toBe('sun');
    });

    it('returns null for invalid day strings', () => {
      expect(normalizeDayToken('funday')).toBeNull();
      expect(normalizeDayToken('7')).toBeNull();
      expect(normalizeDayToken('')).toBeNull();
    });
  });

  describe('parseDaysOfWeek', () => {
    it('parses standard "mon-fri" range into active weekdays', () => {
      expect(parseDaysOfWeek('mon-fri')).toEqual(['mon', 'tue', 'wed', 'thu', 'fri']);
    });

    it('parses comma-separated day lists (e.g. mon,wed,thu)', () => {
      expect(parseDaysOfWeek('mon,wed,thu')).toEqual(['mon', 'wed', 'thu']);
    });

    it('parses comma-separated day lists with spaces and mixed case', () => {
      expect(parseDaysOfWeek('Mon, Wed, Fri')).toEqual(['mon', 'wed', 'fri']);
    });

    it('parses single day', () => {
      expect(parseDaysOfWeek('tue')).toEqual(['tue']);
    });

    it('parses weekend range "sat-sun"', () => {
      expect(parseDaysOfWeek('sat-sun')).toEqual(['sat', 'sun']);
    });

    it('parses entire week with wildcard "*"', () => {
      expect(parseDaysOfWeek('*')).toEqual(['mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun']);
    });

    it('parses entire week range "mon-sun"', () => {
      expect(parseDaysOfWeek('mon-sun')).toEqual(['mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun']);
    });

    it('returns empty array for empty, whitespace, null, or undefined values', () => {
      expect(parseDaysOfWeek('')).toEqual([]);
      expect(parseDaysOfWeek('   ')).toEqual([]);
      expect(parseDaysOfWeek(null)).toEqual([]);
      expect(parseDaysOfWeek(undefined)).toEqual([]);
    });

    it('sorts parsed days canonically in Monday-Sunday order regardless of input ordering', () => {
      expect(parseDaysOfWeek('fri,mon,wed')).toEqual(['mon', 'wed', 'fri']);
    });

    it('handles wrap-around range like "fri-mon"', () => {
      expect(parseDaysOfWeek('fri-mon')).toEqual(['mon', 'fri', 'sat', 'sun']);
    });
  });

  describe('serializeDaysOfWeek', () => {
    it('serializes selected days into backend cron format (e.g. mon,wed,thu)', () => {
      expect(serializeDaysOfWeek(['mon', 'wed', 'thu'])).toBe('mon,wed,thu');
    });

    it('serializes weekdays in canonical order', () => {
      expect(serializeDaysOfWeek(['mon', 'tue', 'wed', 'thu', 'fri'])).toBe('mon,tue,wed,thu,fri');
    });

    it('maintains Monday-Sunday ordering even if input array was unordered', () => {
      expect(serializeDaysOfWeek(['thu', 'mon', 'fri'])).toBe('mon,thu,fri');
    });

    it('ignores invalid day keys', () => {
      expect(serializeDaysOfWeek(['mon', 'invalid', 'wed'])).toBe('mon,wed');
    });

    it('returns empty string when no days selected', () => {
      expect(serializeDaysOfWeek([])).toBe('');
    });
  });

  describe('formatDaysSummary', () => {
    it('formats weekdays cleanly', () => {
      expect(formatDaysSummary(WEEKDAYS)).toBe('Weekdays (Mon–Fri)');
    });

    it('formats all days cleanly', () => {
      expect(formatDaysSummary(ALL_DAYS)).toBe('All Days (Everyday)');
    });

    it('formats weekends cleanly', () => {
      expect(formatDaysSummary(['sat', 'sun'])).toBe('Weekends (Sat–Sun)');
    });

    it('formats specific days cleanly', () => {
      expect(formatDaysSummary(['mon', 'wed', 'thu'])).toBe('Mon, Wed, Thu');
    });

    it('handles empty days', () => {
      expect(formatDaysSummary([])).toBe('No days selected');
    });
  });
});
