import { render, screen, fireEvent } from '@testing-library/svelte';
import { describe, it, expect, vi } from 'vitest';
import DayOfWeekSelector from '../DayOfWeekSelector.svelte';

describe('DayOfWeekSelector component', () => {
  it('renders all 7 days of the week with accessible labels and attributes', () => {
    render(DayOfWeekSelector, {
      props: { value: 'mon-fri' }
    });

    const days = [
      { name: 'Monday', label: 'Mon' },
      { name: 'Tuesday', label: 'Tue' },
      { name: 'Wednesday', label: 'Wed' },
      { name: 'Thursday', label: 'Thu' },
      { name: 'Friday', label: 'Fri' },
      { name: 'Saturday', label: 'Sat' },
      { name: 'Sunday', label: 'Sun' }
    ];

    for (const day of days) {
      const btn = screen.getByRole('button', { name: day.name });
      expect(btn).toBeInTheDocument();
      expect(btn.textContent).toContain(day.label);
    }
  });

  it('correctly sets active/inactive visual states and aria-pressed based on "mon-fri"', () => {
    render(DayOfWeekSelector, {
      props: { value: 'mon-fri' }
    });

    const weekdays = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday'];
    const weekends = ['Saturday', 'Sunday'];

    for (const name of weekdays) {
      const btn = screen.getByRole('button', { name });
      expect(btn).toHaveAttribute('aria-pressed', 'true');
      expect(btn.classList.contains('active')).toBe(true);
    }

    for (const name of weekends) {
      const btn = screen.getByRole('button', { name });
      expect(btn).toHaveAttribute('aria-pressed', 'false');
      expect(btn.classList.contains('active')).toBe(false);
    }
  });

  it('correctly sets active state for hybrid schedules (e.g. mon,wed,thu)', () => {
    render(DayOfWeekSelector, {
      props: { value: 'mon,wed,thu' }
    });

    expect(screen.getByRole('button', { name: 'Monday' })).toHaveAttribute('aria-pressed', 'true');
    expect(screen.getByRole('button', { name: 'Tuesday' })).toHaveAttribute(
      'aria-pressed',
      'false'
    );
    expect(screen.getByRole('button', { name: 'Wednesday' })).toHaveAttribute(
      'aria-pressed',
      'true'
    );
    expect(screen.getByRole('button', { name: 'Thursday' })).toHaveAttribute(
      'aria-pressed',
      'true'
    );
    expect(screen.getByRole('button', { name: 'Friday' })).toHaveAttribute('aria-pressed', 'false');
    expect(screen.getByRole('button', { name: 'Saturday' })).toHaveAttribute(
      'aria-pressed',
      'false'
    );
    expect(screen.getByRole('button', { name: 'Sunday' })).toHaveAttribute('aria-pressed', 'false');
  });

  it('toggles an inactive day to active and triggers onChange with serialized cron format', async () => {
    const onChange = vi.fn();
    render(DayOfWeekSelector, {
      props: {
        value: 'mon,wed,thu',
        onChange
      }
    });

    const fridayBtn = screen.getByRole('button', { name: 'Friday' });
    expect(fridayBtn).toHaveAttribute('aria-pressed', 'false');

    await fireEvent.click(fridayBtn);

    expect(fridayBtn).toHaveAttribute('aria-pressed', 'true');
    expect(fridayBtn.classList.contains('active')).toBe(true);
    expect(onChange).toHaveBeenCalledWith('mon,wed,thu,fri', ['mon', 'wed', 'thu', 'fri']);
  });

  it('toggles an active day to inactive', async () => {
    const onChange = vi.fn();
    render(DayOfWeekSelector, {
      props: {
        value: 'mon,wed,thu',
        onChange
      }
    });

    const wedBtn = screen.getByRole('button', { name: 'Wednesday' });
    expect(wedBtn).toHaveAttribute('aria-pressed', 'true');

    await fireEvent.click(wedBtn);

    expect(wedBtn).toHaveAttribute('aria-pressed', 'false');
    expect(wedBtn.classList.contains('active')).toBe(false);
    expect(onChange).toHaveBeenCalledWith('mon,thu', ['mon', 'thu']);
  });

  it('applies "Weekdays" preset immediately', async () => {
    const onChange = vi.fn();
    render(DayOfWeekSelector, {
      props: {
        value: 'sat,sun',
        onChange
      }
    });

    const weekdaysPreset = screen.getByRole('button', { name: 'Weekdays' });
    await fireEvent.click(weekdaysPreset);

    expect(screen.getByRole('button', { name: 'Monday' })).toHaveAttribute('aria-pressed', 'true');
    expect(screen.getByRole('button', { name: 'Tuesday' })).toHaveAttribute('aria-pressed', 'true');
    expect(screen.getByRole('button', { name: 'Wednesday' })).toHaveAttribute(
      'aria-pressed',
      'true'
    );
    expect(screen.getByRole('button', { name: 'Thursday' })).toHaveAttribute(
      'aria-pressed',
      'true'
    );
    expect(screen.getByRole('button', { name: 'Friday' })).toHaveAttribute('aria-pressed', 'true');
    expect(screen.getByRole('button', { name: 'Saturday' })).toHaveAttribute(
      'aria-pressed',
      'false'
    );
    expect(screen.getByRole('button', { name: 'Sunday' })).toHaveAttribute('aria-pressed', 'false');

    expect(onChange).toHaveBeenCalledWith('mon,tue,wed,thu,fri', [
      'mon',
      'tue',
      'wed',
      'thu',
      'fri'
    ]);
  });

  it('applies "All Days" preset immediately', async () => {
    const onChange = vi.fn();
    render(DayOfWeekSelector, {
      props: {
        value: 'mon',
        onChange
      }
    });

    const allDaysPreset = screen.getByRole('button', { name: 'All Days' });
    await fireEvent.click(allDaysPreset);

    const allDays = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'];
    for (const name of allDays) {
      expect(screen.getByRole('button', { name })).toHaveAttribute('aria-pressed', 'true');
    }

    expect(onChange).toHaveBeenCalledWith('mon,tue,wed,thu,fri,sat,sun', [
      'mon',
      'tue',
      'wed',
      'thu',
      'fri',
      'sat',
      'sun'
    ]);
  });

  it('applies "Clear" preset immediately', async () => {
    const onChange = vi.fn();
    render(DayOfWeekSelector, {
      props: {
        value: 'mon-fri',
        onChange
      }
    });

    const clearPreset = screen.getByRole('button', { name: 'Clear' });
    await fireEvent.click(clearPreset);

    const allDays = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'];
    for (const name of allDays) {
      expect(screen.getByRole('button', { name })).toHaveAttribute('aria-pressed', 'false');
    }

    expect(onChange).toHaveBeenCalledWith('', []);
  });

  it('respects disabled prop', async () => {
    const onChange = vi.fn();
    render(DayOfWeekSelector, {
      props: {
        value: 'mon-fri',
        disabled: true,
        onChange
      }
    });

    const mondayBtn = screen.getByRole('button', { name: 'Monday' });
    expect(mondayBtn).toBeDisabled();

    await fireEvent.click(mondayBtn);
    expect(onChange).not.toHaveBeenCalled();

    const weekdaysPreset = screen.getByRole('button', { name: 'Weekdays' });
    expect(weekdaysPreset).toBeDisabled();
    await fireEvent.click(weekdaysPreset);
    expect(onChange).not.toHaveBeenCalled();
  });
});
