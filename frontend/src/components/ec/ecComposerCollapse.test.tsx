import { fireEvent, render, within } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

vi.mock('@/api/ecClient', () => ({
  listEcScenarios: () =>
    Promise.resolve({
      scenarios: [{ scenario_id: 's1_governed_splunk_investigation', label: 'S1', category: 'Flagship', query: 'Q' }],
    }),
}));

import { EcCockpitComposer } from '@/components/ec/EcCockpitComposer';

describe('EcCockpitComposer', () => {
  it('collapses to one line when an answer is on screen and expands on demand', () => {
    const { container } = render(
      <EcCockpitComposer selectedId="s1_governed_splunk_investigation" onSelect={() => undefined} onRun={() => undefined} compact />,
    );
    const scope = within(container);
    expect(container.querySelector('[data-ec-composer="collapsed"]')).not.toBeNull();
    expect(scope.queryByText('Investigation command')).toBeNull();
    fireEvent.click(scope.getByRole('button', { name: 'Expand the command bar' }));
    expect(container.querySelector('[data-ec-composer="expanded"]')).not.toBeNull();
    expect(scope.getByText('Investigation command')).toBeInTheDocument();
  });

  it('stays fully open before any answer', () => {
    const { container } = render(
      <EcCockpitComposer selectedId="s1_governed_splunk_investigation" onSelect={() => undefined} onRun={() => undefined} />,
    );
    expect(container.querySelector('[data-ec-composer="expanded"]')).not.toBeNull();
  });
});
