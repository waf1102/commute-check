import { render, screen } from '@testing-library/svelte';
import { describe, it, expect } from 'vitest';
import LegRiskCard from '../LegRiskCard.svelte';
import type { LegAssessment } from '$lib/api';

describe('LegRiskCard Component', () => {
  const sampleOutbound: LegAssessment = {
    leg_type: 'outbound',
    location_name: 'Home -> Work',
    schedule_time: '08:00',
    status: 'Go',
    score: 95,
    reasons: ['Mild weather', 'Low wind']
  };

  const sampleReturn: LegAssessment = {
    leg_type: 'return',
    location_name: 'Work -> Home',
    schedule_time: '17:00',
    status: 'Caution',
    score: 60,
    reasons: ['High wind speed (20 mph)']
  };

  it('renders outbound leg status, score, location, departure time, and reasons', () => {
    render(LegRiskCard, {
      props: {
        outboundLeg: sampleOutbound,
        returnLeg: sampleReturn
      }
    });

    expect(screen.getByTestId('leg-risk-card')).toBeInTheDocument();
    expect(screen.getByText('Home -> Work')).toBeInTheDocument();
    expect(screen.getByText(/08:00/)).toBeInTheDocument();
    expect(screen.getByText('95')).toBeInTheDocument();
    expect(screen.getByText('Mild weather')).toBeInTheDocument();
    expect(screen.getByText('Low wind')).toBeInTheDocument();
  });

  it('renders return leg status, score, location, departure time, and reasons side-by-side', () => {
    render(LegRiskCard, {
      props: {
        outboundLeg: sampleOutbound,
        returnLeg: sampleReturn
      }
    });

    expect(screen.getByText('Work -> Home')).toBeInTheDocument();
    expect(screen.getByText(/17:00/)).toBeInTheDocument();
    expect(screen.getByText('60')).toBeInTheDocument();
    expect(screen.getByText('High wind speed (20 mph)')).toBeInTheDocument();
  });

  it('handles snake_case props (outbound_leg, return_leg) correctly', () => {
    render(LegRiskCard, {
      props: {
        outbound_leg: sampleOutbound,
        return_leg: sampleReturn
      }
    });

    expect(screen.getByTestId('leg-risk-card')).toBeInTheDocument();
    expect(screen.getByText('Home -> Work')).toBeInTheDocument();
    expect(screen.getByText('Work -> Home')).toBeInTheDocument();
  });

  it('renders correctly when only outbound leg is present', () => {
    render(LegRiskCard, {
      props: {
        outboundLeg: sampleOutbound
      }
    });

    expect(screen.getByTestId('leg-risk-card')).toBeInTheDocument();
    expect(screen.getByText('Home -> Work')).toBeInTheDocument();
    expect(screen.queryByText('Work -> Home')).not.toBeInTheDocument();
  });
});
