import { describe, expect, it } from 'vitest';
import { readinessLabelForActionChip } from '@/lib/ecOperationalLink';

describe('readinessLabelForActionChip', () => {
  it('maps S5 ticket follow-up to readiness row', () => {
    expect(
      readinessLabelForActionChip({
        follow_up_id: 'create_change_ticket',
        label: 'Create change ticket',
        advances_state: true,
        group: 'action',
        leads_to_action: true,
      }),
    ).toBe('Create change ticket');
  });

  it('returns null for continue chips', () => {
    expect(
      readinessLabelForActionChip({
        follow_up_id: 'show_hardening_policy',
        label: 'Show hardening policy',
        advances_state: true,
      }),
    ).toBeNull();
  });
});
