import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { EcInvestigationAnswer } from '@/components/ec/EcInvestigationAnswer';
import type { ExperienceCenterResponse } from '@/components/ec/types';

// The S4 hunt SPL was generated and validated but never printed on layer 1:
// EcSplArtifactPanel reads analyst.spl_code (empty for S4) and the fallback
// block rendered a heading with no code. A viewer asking "which query ran?"
// had to open the transparency drawer. Pin the query text to layer 1.
const SPL =
  'search index=pgcil_soc sourcetype=pgcil:vpn earliest=-7d latest=now ' +
  '(uri="*/api/v1/mgmt/session*" OR url="*/mgmt/session*") ' +
  '| stats count values(src) as src values(dest) as dest by uri action | head 100';

function envelope(): ExperienceCenterResponse {
  return {
    scenario_id: 's4_zero_day_no_playbook',
    candidate_spl: { candidate_spl: SPL, execution_eligible: false },
    analyst: {},
  } as unknown as ExperienceCenterResponse;
}

describe('EcInvestigationAnswer candidate SPL', () => {
  it('prints the hunt query on layer 1, not just a heading', () => {
    render(<EcInvestigationAnswer envelope={envelope()} />);

    expect(screen.getByText(/Candidate SPL/i)).toBeInTheDocument();
    expect(screen.getByText(/index=pgcil_soc/)).toBeInTheDocument();
    expect(screen.getByText(/mgmt\/session/)).toBeInTheDocument();
  });

  it('still marks the query review-only', () => {
    render(<EcInvestigationAnswer envelope={envelope()} />);
    expect(screen.getAllByText(/Review-only candidate/i).length).toBeGreaterThan(0);
  });
});
