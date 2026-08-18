import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { EcInvestigationWorkspace } from '@/components/ec/EcInvestigationWorkspace';

vi.mock('@/api/ecClient', () => ({
  listEcScenarios: vi.fn(async () => ({
    scenarios: [
      {
        scenario_id: 's1_governed_splunk_investigation',
        label: 'S1 · Governed large-scale investigation',
        category: 'Flagship',
        query: 'Find suspicious IP',
        expected_skill: 'attack_discovery',
      },
    ],
    count: 1,
  })),
  runEcScenario: vi.fn(),
  followUpEcScenario: vi.fn(),
  approveEcAction: vi.fn(),
  executeEcAction: vi.fn(),
  verifyEcAction: vi.fn(),
}));

describe('EcInvestigationWorkspace /clear', () => {
  it('resets the cockpit stream when the user types /clear', async () => {
    render(<EcInvestigationWorkspace />);
    const input = await screen.findByPlaceholderText(/\/clear to reset/i);
    fireEvent.change(input, { target: { value: '/clear' } });
    fireEvent.keyDown(input, { key: 'Enter' });
    expect(screen.getByText(/AI Investigation Cockpit/i)).toBeInTheDocument();
    expect(screen.queryByText(/SOC Answer/i)).not.toBeInTheDocument();
  });
});
