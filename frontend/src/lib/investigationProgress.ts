export interface InvestigationProgressStep {
  id: string;
  label: string;
  description: string;
  durationMs: number;
  /** Micro-status lines cycled while this step is active (connection / processing feel). */
  activity?: string[];
}

export type InvestigationProgressPhase = 'deterministic' | 'finalizing' | 'partial' | 'complete' | 'error';

export interface InvestigationProgressError {
  message: string;
  code?: string | null;
  recoverable?: boolean;
}

export interface InvestigationLlmWarning {
  message: string;
  code?: string | null;
}

export interface InvestigationFinalizationState {
  phase: InvestigationProgressPhase;
  statusLine: string;
  timeoutTier: 0 | 1 | 2 | 3;
  partialFallback: boolean;
  currentServerStage?: string | null;
  mcpDetail?: string | null;
  showRetryHint: boolean;
}

export interface InvestigationProgressState {
  steps: InvestigationProgressStep[];
  activeStepIndex: number;
  completedStepIds: string[];
  /** True when deterministic steps finished but final answer not yet received. */
  finalization?: InvestigationFinalizationState;
  /** Server-reported pipeline stage (live chat stream). */
  serverStage?: string | null;
  /** Non-fatal live LLM issue; deterministic answer still expected. */
  llmWarning?: InvestigationLlmWarning | null;
  /** Fatal stream/pipeline failure before an answer was delivered. */
  error?: InvestigationProgressError | null;
}

/** Maps backend progress stage ids to loader step ids. */
export const SERVER_STAGE_TO_STEP_ID: Record<string, string> = {
  queued: 'query',
  understanding_query: 'query',
  classifying_intent: 'route',
  planning_evidence: 'workflow',
  route_adjudication: 'workflow',
  retrieving_knowledge: 'rag',
  generating_spl: 'spl_validation',
  checking_mcp: 'mcp_connect',
  mapping_mitre: 'mitre',
  checking_sufficiency: 'severity',
  generating_answer: 'llm_governance',
  validating_answer: 'package',
};

const BASE_STEPS: Omit<InvestigationProgressStep, 'durationMs' | 'activity'>[] = [
  {
    id: 'query',
    label: 'Understanding query',
    description: 'Normalizing intent, entities, and expected output type.',
  },
  {
    id: 'route',
    label: 'Routing skill',
    description: 'Selecting the governed skill chain and tool plan.',
  },
  {
    id: 'workflow',
    label: 'Planning workflow',
    description: 'Building the investigation workflow (execution remains gated).',
  },
];

function step(
  partial: Omit<InvestigationProgressStep, 'durationMs'> & { durationMs?: number },
  durationMs: number,
): InvestigationProgressStep {
  const { durationMs: _ignored, ...rest } = partial as InvestigationProgressStep;
  return { ...rest, durationMs };
}

export function buildInvestigationProgressSteps(options?: {
  expectedSkill?: string | null;
  expectedSources?: string[];
  demoMode?: boolean;
}): InvestigationProgressStep[] {
  const skill = options?.expectedSkill ?? 'investigation';
  const sources = new Set(options?.expectedSources ?? []);
  const demo = options?.demoMode ?? true;

  const steps: InvestigationProgressStep[] = [
    step(
      {
        id: 'query',
        label: 'Understanding query',
        description: 'Parsing analyst intent and mapping to SOC use cases.',
        activity: ['Tokenizing query…', 'Extracting entities (host, index, window)…'],
      },
      700,
    ),
    step(
      {
        id: 'route',
        label: 'Routing skill',
        description: `Selecting governed route for ${skill.replace(/_/g, ' ')}.`,
        activity: ['Comparing deterministic router vs registry…', 'Tool plan locked for this turn'],
      },
      800,
    ),
    step(
      {
        id: 'workflow',
        label: 'Planning workflow',
        description: 'Building investigation steps (workflow execution stays disabled).',
        activity: ['Assigning connectors and safety gates…'],
      },
      700,
    ),
  ];

  const needsSpl =
    skill === 'spl_generation' ||
    sources.has('spl_policy') ||
    sources.has('mcp:splunk');
  const needsMcp = sources.has('mcp:splunk');
  const needsRag = sources.has('rag:sop');

  if (needsSpl) {
    steps.push(
      step(
        {
          id: 'spl_validation',
          label: 'Validating SPL',
          description: demo
            ? 'Running deterministic SPL policy on fixture candidate (not executed).'
            : 'Running deterministic SPL policy checks on the candidate query.',
          activity: ['Policy spl-policy-v1…', 'Normalizing time range and index constraints…'],
        },
        850,
      ),
    );
  }

  if (needsMcp) {
    steps.push(
      step(
        {
          id: 'mcp_connect',
          label: 'Connecting Splunk MCP',
          description: demo
            ? 'Checking Splunk MCP registry and tool readiness (fixture path; no live search).'
            : 'Checking Splunk MCP registry, transport, and tool policy.',
          activity: [
            'Resolving splunk server from MCP registry…',
            'Verifying splunk.search is allowed for this skill…',
            demo ? 'Connection ready — execution gate remains closed' : 'Awaiting execution gate approval…',
          ],
        },
        1200,
      ),
      step(
        {
          id: 'mcp_evidence',
          label: 'Splunk evidence',
          description: demo
            ? 'Packaging COE synthetic rows into SplunkResultEnvelope.'
            : 'Packaging search results into governed SourceEvidence.',
          activity: [
            'Preparing search preview request…',
            'Normalizing fields and row counts…',
            demo ? 'Fixture envelope attached (schema_unconfirmed)' : 'Redacting sensitive fields…',
          ],
        },
        1000,
      ),
    );
  }

  if (needsRag) {
    steps.push(
      step(
        {
          id: 'rag',
          label: 'Governed SOC KB',
          description: 'Retrieving approved SOP and playbook context into SourceEvidence.',
          activity: ['Querying governed knowledge index…', 'Binding SOC-SOP citations to context…'],
        },
        900,
      ),
    );
  }

  if (skill !== 'knowledge_recall' || needsMcp) {
    steps.push(
      step(
        {
          id: 'mitre',
          label: 'MITRE mapping',
          description: 'Applying local technique candidates with support status.',
          activity: ['Matching TTPs to evidence refs…', 'Setting supported vs requires_validation…'],
        },
        750,
      ),
    );
  }

  steps.push(
    step(
      {
        id: 'severity',
        label: 'Severity & sufficiency',
        description: 'Running severity matrix and context sufficiency gates.',
        activity: ['Evaluating P1/P2 escalation thresholds…', 'Computing synthesis readiness (gated)…'],
      },
      800,
    ),
  );

  steps.push(
    step(
      {
        id: 'llm_governance',
        label: 'LLM governance pass',
        description: demo
          ? 'Applying captured Foundation-sec signal under V.AI SOC policy (no live model call).'
          : 'Running governed LLM layer when enabled (advisory + overrides only).',
        activity: demo
          ? [
              'Loading captured Foundation-sec instruct output…',
              'Applying severity, MITRE, and SPL governance overrides…',
              'Final synthesis disabled for Experience Center',
            ]
          : [
              'Selecting instruct provider from registry…',
              'Structured JSON extraction and schema validation…',
              'Answer guard: planned / not executed in this stage',
            ],
      },
      1100,
    ),
  );

  steps.push(
    step(
      {
        id: 'package',
        label: 'Packaging analyst answer',
        description: demo
          ? 'Assembling the analyst card, actions, and trace from governed fixtures.'
          : 'Assembling the analyst summary from evidence and policy outputs.',
        activity: ['Formatting severity and MITRE tables…', 'Attaching recommended actions (P1–P4)…'],
      },
      850,
    ),
  );

  return steps;
}

export function delay(ms: number): Promise<void> {
  return new Promise((resolve) => {
    window.setTimeout(resolve, ms);
  });
}

export async function playInvestigationProgress(
  steps: InvestigationProgressStep[],
  onUpdate: (state: InvestigationProgressState) => void,
  options?: { skipCompletion?: boolean },
): Promise<void> {
  const completedStepIds: string[] = [];
  for (let index = 0; index < steps.length; index += 1) {
    onUpdate({ steps, activeStepIndex: index, completedStepIds: [...completedStepIds] });
    await delay(steps[index].durationMs);
    completedStepIds.push(steps[index].id);
  }
  if (options?.skipCompletion) {
    onUpdate({
      steps,
      activeStepIndex: steps.length - 1,
      completedStepIds: steps.slice(0, -1).map((step) => step.id),
      finalization: {
        phase: 'finalizing',
        statusLine: 'Generating final answer…',
        timeoutTier: 0,
        partialFallback: false,
        showRetryHint: false,
      },
    });
    return;
  }
  onUpdate({ steps, activeStepIndex: steps.length, completedStepIds: [...completedStepIds] });
}

export function applyServerProgressStage(
  state: InvestigationProgressState,
  stage: string,
  detail?: string,
): InvestigationProgressState {
  const stepId = SERVER_STAGE_TO_STEP_ID[stage];
  if (!stepId) {
    return { ...state, serverStage: stage };
  }
  const index = state.steps.findIndex((step) => step.id === stepId);
  if (index < 0) {
    return { ...state, serverStage: stage };
  }
  const completedStepIds = state.steps.slice(0, index).map((step) => step.id);
  const isFinalization = stage === 'generating_answer' || stage === 'validating_answer';
  let finalization = state.finalization;
  if (stage === 'checking_mcp' && detail) {
    finalization = {
      phase: finalization?.phase ?? 'deterministic',
      statusLine: finalization?.statusLine ?? 'Checking MCP…',
      timeoutTier: finalization?.timeoutTier ?? 0,
      partialFallback: false,
      mcpDetail: detail,
      showRetryHint: false,
    };
  } else if (isFinalization) {
    finalization = {
      phase: 'finalizing',
      statusLine:
        stage === 'validating_answer'
          ? 'Validating answer safety and evidence grounding…'
          : state.finalization?.statusLine ?? 'Generating final answer…',
      timeoutTier: state.finalization?.timeoutTier ?? 0,
      partialFallback: false,
      currentServerStage: stage,
      mcpDetail: state.finalization?.mcpDetail,
      showRetryHint: state.finalization?.showRetryHint ?? false,
    };
  }
  return {
    ...state,
    serverStage: stage,
    activeStepIndex: index,
    completedStepIds,
    finalization,
  };
}
