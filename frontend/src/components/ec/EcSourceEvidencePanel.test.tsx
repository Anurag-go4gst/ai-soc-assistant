import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { EcSourceEvidencePanel } from '@/components/ec/EcSourceEvidencePanel';
import type { EcSourceEvidenceItem } from '@/components/ec/types';

describe('EcSourceEvidencePanel', () => {
  it('renders kb_fixture policy rule text from preview_rows', () => {
    const items: EcSourceEvidenceItem[] = [
      {
        evidence_id: 'ev-s5-policy',
        source_type: 'kb_fixture',
        source_name: 'Enterprise hardening policy',
        provenance: 'ec_scenario_policy',
        preview_rows: [
          {
            rule: 'A compromised device running version 14 must be upgraded to version 15',
            applies_because: ['device affected', 'current_version=14'],
          },
        ],
      },
    ];

    render(<EcSourceEvidencePanel items={items} />);

    expect(
      screen.getByText('A compromised device running version 14 must be upgraded to version 15'),
    ).toBeInTheDocument();
    expect(screen.getByText('Enterprise hardening policy')).toBeInTheDocument();
    expect(screen.getByText('EC scenario policy')).toBeInTheDocument();
  });
});
