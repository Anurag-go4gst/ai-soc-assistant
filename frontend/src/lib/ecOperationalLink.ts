import type { EcFollowUpChip } from '@/components/ec/types';

const READINESS_BY_FOLLOW_UP: Record<string, string> = {
  show_hardening_policy: 'Review hardening policy',
  check_current_version: 'Confirm current version',
  create_change_ticket: 'Create change ticket',
  request_network_approval: 'Request network approval',
  approve_upgrade: 'Execute cisco.upgrade',
  execute_upgrade: 'Execute cisco.upgrade',
  verify_version: 'Verify version 15',
  send_firewall_email: 'Send firewall-block request',
  notify_soc_lead: 'Notify SOC lead',
  remove_whitelist: 'Remove vendor whitelist',
  request_ip_block: 'Request IP block',
};

export function readinessLabelForActionChip(chip?: EcFollowUpChip | null): string | null {
  if (!chip) return null;
  const mapped = READINESS_BY_FOLLOW_UP[chip.follow_up_id];
  if (mapped) return mapped;
  if (chip.group === 'action' || chip.leads_to_action) return chip.label;
  return null;
}

export function evidenceIdForChip(chip?: EcFollowUpChip | null): string | null {
  if (!chip) return null;
  switch (chip.follow_up_id) {
    case 'show_hardening_policy':
      return 'ev-s5-policy';
    case 'check_current_version':
      return 'ev-s5-version';
    case 'check_maintenance_window':
      return 'ev-s5-window';
    default:
      return null;
  }
}
