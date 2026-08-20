import { describe, expect, it } from 'vitest';
import { resolveEcQueryLocal, scoreQueryMatch, suggestEcQueries } from '@/lib/ecQuerySuggestions';
import type { EcScenarioSummary } from '@/components/ec/types';

const scenarios: EcScenarioSummary[] = [
  {
    scenario_id: 's1_governed_splunk_investigation',
    label: 'S1 · Governed Splunk investigation',
    category: 'Flagship',
    query: 'We have seen a new IP 198.51.100.42. Check and verify over the last 30 days whether it is malicious, and what is the standard SOP to raise monitoring and block it if required.',
    canonical_query: 'We have seen a new IP 198.51.100.42. Check and verify over the last 30 days whether it is malicious, and what is the standard SOP to raise monitoring and block it if required.',
    aliases: ['new IP 198.51.100.42', 'suspicious IP 198.51.100.42 communication'],
    expected_skill: 'attack_discovery',
  },
];

describe('ecQuerySuggestions', () => {
  it('shows suggestions after two characters with fuzzy match', () => {
    const rows = suggestEcQueries(scenarios, 'new ip');
    expect(rows.length).toBeGreaterThan(0);
    expect(rows[0].question).toMatch(/198\.51\.100\.42/);
  });

  it('resolves natural phrasing to scenario', () => {
    const match = resolveEcQueryLocal(scenarios, 'verify new ip 198.51.100.42 last 30 days');
    expect(match?.scenario_id).toBe('s1_governed_splunk_investigation');
  });

  it('scores semantic-style overlap for unrelated example phrasing', () => {
    expect(scoreQueryMatch('why feature phone nps low', 'Why is Feature Phone NPS lower?')).toBeGreaterThan(0.3);
  });
});
