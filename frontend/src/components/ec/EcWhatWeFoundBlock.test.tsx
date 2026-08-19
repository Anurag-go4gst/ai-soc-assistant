import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { EcWhatWeFoundBlock } from '@/components/ec/EcWhatWeFoundBlock';

describe('EcWhatWeFoundBlock', () => {
  it('renders fallback text when segments are absent', () => {
    render(<EcWhatWeFoundBlock fallbackText="Plain summary." segments={null} />);
    expect(screen.getByText('Plain summary.')).toBeInTheDocument();
  });

  it('renders evidence links and calls back with evidence id', () => {
    const onEvidenceLinkClick = vi.fn();
    render(
      <EcWhatWeFoundBlock
        fallbackText="unused"
        onEvidenceLinkClick={onEvidenceLinkClick}
        segments={[
          { type: 'text', text: 'Splunk MCP connected. ' },
          {
            type: 'evidence_link',
            text: 'Suspicious External IP — Firewall Activity',
            evidence_id: 'ev-s1-existing-search',
          },
          { type: 'text', text: ' reused for the recent window.' },
        ]}
      />,
    );
    const link = screen.getByRole('button', { name: 'Suspicious External IP — Firewall Activity' });
    fireEvent.click(link);
    expect(onEvidenceLinkClick).toHaveBeenCalledWith('ev-s1-existing-search');
    expect(screen.getByText(/Splunk MCP connected/)).toBeInTheDocument();
  });
});
