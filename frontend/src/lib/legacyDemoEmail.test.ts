import { afterEach, describe, expect, it, vi } from 'vitest';
import * as ecClient from '@/api/ecClient';
import {
  createLegacyDemoCoordinationAction,
  isEmailCoordinationAction,
} from '@/lib/legacyDemoCoordination';
import { EC_EMAIL_CONFIGURATION_REQUIRED, executeLegacyDemoEmailCoordination } from '@/lib/legacyDemoEmail';

afterEach(() => {
  vi.restoreAllMocks();
});

describe('legacyDemoEmail transport', () => {
  it('classifies only cert and supply-chain as email coordination', () => {
    expect(isEmailCoordinationAction(createLegacyDemoCoordinationAction('cert_in_ot_reporting_obligation'))).toBe(true);
    expect(isEmailCoordinationAction(createLegacyDemoCoordinationAction('guided_investigation_supply_chain'))).toBe(true);
    expect(isEmailCoordinationAction(createLegacyDemoCoordinationAction('firewall_deny_coordinated_attack'))).toBe(false);
    expect(isEmailCoordinationAction(createLegacyDemoCoordinationAction('ir_containment_advisory_firewall_incident'))).toBe(false);
  });

  it('uses existing EC email route contract on analyst confirm', async () => {
    const prepare = vi.spyOn(ecClient, 'prepareEcAction').mockResolvedValue({
      action_id: 'ec-act-test',
      kind: 'email_send',
      label: 'Coordinate CERT-In reporting stakeholders',
      state: 'APPROVAL_REQUIRED',
      provenance: 'simulated_phase10_action',
      production_side_effect: false,
    });
    const approve = vi.spyOn(ecClient, 'approveEcAction').mockResolvedValue({
      action_id: 'ec-act-test',
      kind: 'email_send',
      label: 'Coordinate CERT-In reporting stakeholders',
      state: 'APPROVED',
      provenance: 'simulated_phase10_action',
      production_side_effect: false,
    });
    const execute = vi.spyOn(ecClient, 'executeEcAction').mockResolvedValue({
      action_id: 'ec-act-test',
      kind: 'email_send',
      label: 'Coordinate CERT-In reporting stakeholders',
      state: 'EXECUTED',
      provenance: 'simulated_phase10_action',
      production_side_effect: false,
      receipt: {
        status: 'SUCCESS',
        summary: 'Test transport recorded email to lead@example.test (not a live send).',
        execution_mode: 'fake_test_transport',
      },
    });

    const action = createLegacyDemoCoordinationAction('cert_in_ot_reporting_obligation');
    const result = await executeLegacyDemoEmailCoordination(action, 'sess-1');

    expect(prepare).toHaveBeenCalledWith(
      expect.objectContaining({
        kind: 'email_send',
        scenario_id: 'cert_in_ot_reporting_obligation',
        extra: expect.objectContaining({ logical_recipient: 'SOC_LEAD' }),
      }),
    );
    expect(approve).toHaveBeenCalled();
    expect(execute).toHaveBeenCalled();
    expect(result.status).toBe('completed');
    expect(result.result_message).toMatch(/not a live send/i);
  });

  it('maps missing SMTP configuration honestly', async () => {
    vi.spyOn(ecClient, 'prepareEcAction').mockResolvedValue({
      action_id: 'ec-act-unconfigured',
      kind: 'email_send',
      label: 'Coordinate CERT-In reporting stakeholders',
      state: 'APPROVAL_REQUIRED',
      provenance: 'simulated_phase10_action',
      production_side_effect: false,
    });
    vi.spyOn(ecClient, 'approveEcAction').mockResolvedValue({
      action_id: 'ec-act-unconfigured',
      kind: 'email_send',
      label: 'Coordinate CERT-In reporting stakeholders',
      state: 'APPROVED',
      provenance: 'simulated_phase10_action',
      production_side_effect: false,
    });
    vi.spyOn(ecClient, 'executeEcAction').mockResolvedValue({
      action_id: 'ec-act-unconfigured',
      kind: 'email_send',
      label: 'Coordinate CERT-In reporting stakeholders',
      state: 'FAILED',
      provenance: 'simulated_phase10_action',
      production_side_effect: false,
      receipt: {
        status: EC_EMAIL_CONFIGURATION_REQUIRED,
        summary: 'Email was not sent.',
        reason: EC_EMAIL_CONFIGURATION_REQUIRED,
      },
    });

    const result = await executeLegacyDemoEmailCoordination(
      createLegacyDemoCoordinationAction('cert_in_ot_reporting_obligation'),
      'sess-2',
    );
    expect(result.status).toBe('configuration_required');
    expect(result.result_message).not.toMatch(/^email sent/i);
  });

  it('maps allowlist rejection without fake success', async () => {
    vi.spyOn(ecClient, 'prepareEcAction').mockResolvedValue({
      action_id: 'ec-act-reject',
      kind: 'email_send',
      label: 'Request supplier security coordination',
      state: 'APPROVAL_REQUIRED',
      provenance: 'simulated_phase10_action',
      production_side_effect: false,
    });
    vi.spyOn(ecClient, 'approveEcAction').mockResolvedValue({
      action_id: 'ec-act-reject',
      kind: 'email_send',
      label: 'Request supplier security coordination',
      state: 'APPROVED',
      provenance: 'simulated_phase10_action',
      production_side_effect: false,
    });
    vi.spyOn(ecClient, 'executeEcAction').mockResolvedValue({
      action_id: 'ec-act-reject',
      kind: 'email_send',
      label: 'Request supplier security coordination',
      state: 'FAILED',
      provenance: 'simulated_phase10_action',
      production_side_effect: false,
      receipt: {
        status: 'FAILED',
        reason: 'recipient_not_allowlisted',
        summary: 'Email was not sent.',
      },
    });

    const result = await executeLegacyDemoEmailCoordination(
      createLegacyDemoCoordinationAction('guided_investigation_supply_chain'),
      'sess-3',
    );
    expect(result.status).toBe('rejected');
    expect(result.result_message).toMatch(/not sent/i);
  });
});
