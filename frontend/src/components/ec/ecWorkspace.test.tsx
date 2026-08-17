import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { ScenariosPage } from '@/pages/ScenariosPage';

vi.mock('@/api/ecClient', () => ({
  listEcScenarios: vi.fn(async () => ({ scenarios: [], count: 0 })),
  runEcScenario: vi.fn(),
  followUpEcScenario: vi.fn(),
  approveEcAction: vi.fn(),
  executeEcAction: vi.fn(),
  verifyEcAction: vi.fn(),
}));

describe('Experience Center workspace', () => {
  it('mounts the /scenarios investigation workspace', () => {
    render(<ScenariosPage />);
    expect(screen.getByText(/Investigation workspace/i)).toBeInTheDocument();
    expect(screen.getByText(/Production chat on \/chat is unchanged/i)).toBeInTheDocument();
  });
});
