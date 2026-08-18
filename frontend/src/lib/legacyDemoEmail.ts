import { approveEcAction, executeEcAction, prepareEcAction } from '@/api/ecClient';
import type { EcActionRecord } from '@/components/ec/types';
import {
  completeLegacyDemoCoordinationVerification,
  confirmLegacyDemoCoordinationAction,
  isEmailCoordinationAction,
  type LegacyDemoCoordinationAction,
  type PriorityLegacyDemoScenarioId,
} from '@/lib/legacyDemoCoordination';

export const EC_EMAIL_CONFIGURATION_REQUIRED = 'REAL_EMAIL_CONFIGURATION_REQUIRED';

const EMAIL_DRAFTS: Record<
  Extract<PriorityLegacyDemoScenarioId, 'cert_in_ot_reporting_obligation' | 'guided_investigation_supply_chain'>,
  { logical_recipient: string; subject: string; body: string }
> = {
  cert_in_ot_reporting_obligation: {
    logical_recipient: 'SOC_LEAD',
    subject: '[SOC Coordination] CERT-In 6-hour OT reporting — stakeholder alignment required',
    body: [
      'Dear SOC Leadership,',
      '',
      'A suspected OT incident requires alignment on the CERT-In 6-hour reporting obligation.',
      'Governed SOC-KB guidance indicates CISO and legal/compliance must review applicability before filing.',
      '',
      'Requested actions:',
      '• Preserve ICS/OT logs and capture the incident timeline',
      '• Confirm whether the event meets CERT-In notifiable-incident criteria',
      '• Advise on reporting channel and filing owner',
    ].join('\n'),
  },
  guided_investigation_supply_chain: {
    logical_recipient: 'APPSEC_TEAM',
    subject: '[SOC Coordination] Supply-chain hunt follow-up — supplier security liaison',
    body: [
      'Dear Application Security Team,',
      '',
      'An out-of-catalog CI/CD supply-chain hunt is underway with review-only guidance.',
      'No governed SPL template covers this hunt; analyst-authored SPL remains required before execution.',
      '',
      'Requested actions:',
      '• Review build-agent egress and pipeline definition changes for the suspected window',
      '• Coordinate with supplier security on artifact signing and CI runner credential access',
      '• Confirm whether supplier liaison should join the investigation bridge',
    ].join('\n'),
  },
};

function buildEmailExtra(action: LegacyDemoCoordinationAction, sessionId?: string | null) {
  if (
    action.scenario_id !== 'cert_in_ot_reporting_obligation' &&
    action.scenario_id !== 'guided_investigation_supply_chain'
  ) {
    throw new Error(`legacy_email_not_configured:${action.scenario_id}`);
  }
  const draft = EMAIL_DRAFTS[action.scenario_id];
  return {
    logical_recipient: draft.logical_recipient,
    email: {
      to: draft.logical_recipient,
      subject: draft.subject,
      body: draft.body,
    },
    idempotency_key: `legacy-coord-${action.scenario_id}-${sessionId ?? 'anon'}`,
  };
}

function mapEmailReceipt(
  action: LegacyDemoCoordinationAction,
  executed: EcActionRecord,
): LegacyDemoCoordinationAction {
  const receipt = executed.receipt ?? {};
  const status = String(receipt.status ?? '');
  const summary = String(receipt.summary ?? receipt.reason ?? 'Email was not sent.');
  if (executed.state === 'EXECUTED' && status === 'SUCCESS') {
    return {
      ...action,
      status: 'completed',
      available: false,
      ec_action_id: executed.action_id,
      result_message: summary,
      email_receipt: receipt,
    };
  }
  if (status === EC_EMAIL_CONFIGURATION_REQUIRED) {
    return {
      ...action,
      status: 'configuration_required',
      available: false,
      ec_action_id: executed.action_id,
      result_message: summary,
      email_receipt: receipt,
    };
  }
  if (receipt.reason === 'recipient_not_allowlisted') {
    return {
      ...action,
      status: 'rejected',
      available: false,
      ec_action_id: executed.action_id,
      result_message: summary,
      email_receipt: receipt,
    };
  }
  return {
    ...action,
    status: 'failed',
    available: false,
    ec_action_id: executed.action_id,
    result_message: summary,
    email_receipt: receipt,
  };
}

export async function executeLegacyDemoEmailCoordination(
  action: LegacyDemoCoordinationAction,
  sessionId?: string | null,
): Promise<LegacyDemoCoordinationAction> {
  const extra = buildEmailExtra(action, sessionId);
  const prepared = await prepareEcAction({
    kind: 'email_send',
    label: action.label,
    scenario_id: action.scenario_id,
    session_id: sessionId ?? undefined,
    extra,
  });
  const approved = await approveEcAction(prepared.action_id, prepared);
  const executed = await executeEcAction(
    approved.action_id,
    {
      to: String(extra.email.to),
      subject: String(extra.email.subject),
      body: String(extra.email.body),
      logical_recipient: extra.logical_recipient,
    },
    approved,
  );
  return mapEmailReceipt(action, executed);
}

export async function executeLegacyDemoCoordination(
  action: LegacyDemoCoordinationAction,
  sessionId?: string | null,
): Promise<LegacyDemoCoordinationAction> {
  if (isEmailCoordinationAction(action)) {
    return executeLegacyDemoEmailCoordination(action, sessionId);
  }
  const submitting = confirmLegacyDemoCoordinationAction(action);
  await new Promise((resolve) => {
    window.setTimeout(resolve, 700);
  });
  return completeLegacyDemoCoordinationVerification(submitting);
}
