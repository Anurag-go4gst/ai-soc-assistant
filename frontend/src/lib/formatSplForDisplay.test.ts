import { describe, expect, it } from 'vitest';
import { formatSplForDisplay } from '@/lib/formatSplForDisplay';

describe('formatSplForDisplay', () => {
  it('wraps long single-line SPL at pipe boundaries', () => {
    const spl =
      'search index=pgcil_soc sourcetype=pgcil:firewall earliest=-60d latest=-30d | stats count | head 100';
    const out = formatSplForDisplay(spl);
    expect(out).toContain('\n| stats count');
    expect(out).toContain('\n| head 100');
    expect(out.split('\n').length).toBeGreaterThan(1);
  });

  it('preserves existing newlines', () => {
    const spl = 'search index=pgcil_soc\n| stats count';
    expect(formatSplForDisplay(spl)).toBe(spl);
  });
});
