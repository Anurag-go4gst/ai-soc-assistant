export interface InvestigationProgressStep {
  id: string;
  label: string;
  description: string;
  durationMs: number;
  /** Micro-status lines cycled while this step is active (connection / processing feel). */
  activity?: string[];
}

export type InvestigationProgressStepStatus = 'pending' | 'active' | 'completed' | 'skipped' | 'blocked' | 'fallback';
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
  stepStatuses?: Record<string, InvestigationProgressStepStatus>;
  stepDisplayText?: Record<string, string>;
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
  generating_spl: 'spl_evidence',
  checking_mcp: 'mcp_gate',
  retrieving_knowledge: 'rag',
  mapping_mitre: 'mitre_severity',
  checking_sufficiency: 'mitre_severity',
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

const LIVE_LINEAR_STEPS: InvestigationProgressStep[] = [
  {
      id: 'query',
      label: 'Understanding query',
      description: 'Parsing analyst intent and safe routing context.',
      activity: ['Normalizing query…', 'Identifying entities and requested outcome…'],
    
    durationMs: 700,
  },
  {
      id: 'route',
      label: 'Selecting route',
      description: 'Selecting the governed SOC route for this turn.',
      activity: ['Checking deterministic routing…', 'Locking route authority…'],
    
    durationMs: 700,
  },
  {
      id: 'workflow',
      label: 'Planning workflow',
      description: 'Planning the investigation path without changing execution gates.',
      activity: ['Planning evidence needs…', 'Applying workflow gates…'],
    
    durationMs: 700,
  },
  {
      id: 'spl_evidence',
      label: 'Preparing SPL / evidence path',
      description: 'Preparing governed query or evidence handling when needed.',
      activity: ['Checking governed SPL and evidence policy…'],
    
    durationMs: 800,
  },
  {
      id: 'mcp_gate',
      label: 'Checking MCP gate',
      description: 'Checking whether MCP execution is allowed for this request.',
      activity: ['Evaluating MCP and HIL gates…'],
    
    durationMs: 750,
  },
  {
      id: 'rag',
      label: 'Retrieving SOC knowledge',
      description: 'Retrieving governed SOC knowledge only when the path requests it.',
      activity: ['Looking up approved SOC knowledge…'],
    
    durationMs: 850,
  },
  {
      id: 'mitre_severity',
      label: 'Mapping MITRE / severity',
      description: 'Applying MITRE visibility and severity policy.',
      activity: ['Applying MITRE evidence policy…', 'Checking severity and sufficiency…'],
    
    durationMs: 800,
  },
  {
      id: 'llm_governance',
      label: 'Applying LLM / answer governance',
      description: 'Applying answer governance and deterministic fallback policy.',
      activity: ['Checking governed answer policy…'],
    
    durationMs: 900,
  },
  {
      id: 'package',
      label: 'Packaging analyst answer',
      description: 'Packaging the analyst-visible answer or review-required response.',
      activity: ['Final analyst answer is being packaged…'],
    
    durationMs: 800,
  },
];

const LIVE_OPTIONAL_STEP_IDS = new Set(['spl_evidence', 'mcp_gate', 'rag']);

function isLiveLinearProgress(steps: InvestigationProgressStep[]): boolean {
  const ids = new Set(steps.map((item) => item.id));
  return ids.has('spl_evidence') && ids.has('mcp_gate') && ids.has('package');
}

/**
 * Captured per-stage latency for replay (B4). `replayed_ms` is the recorded latency
 * already capped (5–6 s/stage) by the capture harness; replay advances on it.
 */
export interface StageLatency {
  stage: string;
  recorded_ms?: number;
  replayed_ms: number;
}

/**
 * Maps captured `stage_latencies[].stage` names onto the loader step ids. Covers the
 * full demo journey: query understanding → routing → SPL validate → MCP lifecycle
 * (registry resolve → TLS/bearer → tools/list → submit sid → poll 1/3..3/3 → DONE) →
 * LLM synthesis → final. Multiple stage names can fold into one visible step (their
 * replayed_ms is summed) — e.g. all MCP sub-hops roll up into `mcp_connect`.
 */
const STAGE_NAME_TO_STEP_ID: Record<string, string> = {
  // Query understanding
  query: 'query',
  query_understanding: 'query',
  understanding_query: 'query',
  // Routing / resource plan
  route: 'route',
  routing: 'route',
  route_adjudication: 'route',
  resource_plan: 'route',
  workflow: 'workflow',
  tool_selection: 'workflow',
  // SPL validate
  spl: 'spl_validation',
  spl_validate: 'spl_validation',
  spl_validation: 'spl_validation',
  generating_spl: 'spl_validation',
  // MCP lifecycle (folds into the connect step)
  mcp: 'mcp_connect',
  mcp_connect: 'mcp_connect',
  mcp_registry_resolve: 'mcp_connect',
  mcp_tls_bearer: 'mcp_connect',
  mcp_tools_list: 'mcp_connect',
  mcp_submit: 'mcp_connect',
  mcp_poll: 'mcp_connect',
  mcp_done: 'mcp_connect',
  mcp_fetch: 'mcp_evidence',
  mcp_evidence: 'mcp_evidence',
  // Knowledge / RAG
  rag: 'rag',
  retrieving_knowledge: 'rag',
  // MITRE / severity
  mitre: 'mitre',
  mitre_severity: 'mitre',
  severity: 'severity',
  // LLM synthesis
  llm: 'llm_governance',
  llm_synthesis: 'llm_governance',
  llm_governance: 'llm_governance',
  generating_answer: 'llm_governance',
  // Final packaging
  final: 'package',
  package: 'package',
  validating_answer: 'package',
};

/**
 * Overrides step durations from a captured `stage_latencies` array (B4). Stage names
 * are mapped to step ids; replayed_ms for stages folding into the same step are summed.
 * Steps with no captured latency keep their existing (jittered) duration. Returns a new
 * array; does not mutate the input. When `stageLatencies` is empty/absent, returns the
 * steps unchanged so non-captured scenarios fall back to jitter behavior.
 */
export function applyStageLatencies(
  steps: InvestigationProgressStep[],
  stageLatencies?: StageLatency[] | null,
): InvestigationProgressStep[] {
  if (!stageLatencies || stageLatencies.length === 0) {
    return steps;
  }
  const replayByStepId = new Map<string, number>();
  for (const entry of stageLatencies) {
    if (!entry || typeof entry.replayed_ms !== 'number' || entry.replayed_ms < 0) continue;
    const stepId = STAGE_NAME_TO_STEP_ID[entry.stage];
    if (!stepId) continue;
    replayByStepId.set(stepId, (replayByStepId.get(stepId) ?? 0) + entry.replayed_ms);
  }
  if (replayByStepId.size === 0) {
    return steps;
  }
  return steps.map((item) => {
    const replayed = replayByStepId.get(item.id);
    return typeof replayed === 'number' ? { ...item, durationMs: replayed } : { ...item };
  });
}

/**
 * Demo step durations are jittered (±30%, with an occasional slow stage) so the
 * Experience Center never plays an identical, obviously-staged timeline twice.
 */
export function jitterMs(base: number): number {
  const spread = base * 0.3;
  let value = base - spread + Math.random() * spread * 2;
  if (Math.random() < 0.18) {
    value *= 1.45; // occasional "slow" stage, like a real backend hiccup
  }
  return Math.round(value);
}

/** Splunk-style search job sid for the MCP handshake micro-sequence. */
export function generateJobSid(): string {
  const epoch = 1718_000_000 + Math.floor(Math.random() * 9_000_000);
  const suffix = 1000 + Math.floor(Math.random() * 9000);
  return `${epoch}.${suffix}`;
}

/**
 * Global tempo for the Experience Center staged playback. The raw per-step values
 * sum to ~11s on an MCP-heavy scenario (+ finalization → 12–18s); scaling them keeps
 * the realistic staging while landing total time-to-answer at ~8–10s. Demo-only:
 * the live path uses LIVE_LINEAR_STEPS and never calls step().
 */
const DEMO_DURATION_SCALE = 0.62;

function step(
  partial: Omit<InvestigationProgressStep, 'durationMs'> & { durationMs?: number },
  durationMs: number,
): InvestigationProgressStep {
  const { durationMs: _ignored, ...rest } = partial as InvestigationProgressStep;
  return { ...rest, durationMs: jitterMs(Math.round(durationMs * DEMO_DURATION_SCALE)) };
}

export function buildInvestigationProgressSteps(options?: {
  expectedSkill?: string | null;
  expectedSources?: string[];
  demoMode?: boolean;
}): InvestigationProgressStep[] {
  const skill = options?.expectedSkill ?? 'investigation';
  const sources = new Set(options?.expectedSources ?? []);
  const demo = options?.demoMode ?? true;

  if (!demo) {
    return LIVE_LINEAR_STEPS.map((item) => ({ ...item, activity: item.activity ? [...item.activity] : undefined }));
  }

  const jobSid = generateJobSid();
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
        label: 'Resource planning',
        description: `Selecting governed capability and resources for ${skill.replace(/_/g, ' ')}.`,
        activity: ['Mapping capability and evidence needs…', 'Resource plan locked for this turn'],
      },
      800,
    ),
    step(
      {
        id: 'workflow',
        label: 'Selecting MCP tool',
        description: 'Selecting the governed MCP tool and input contract.',
        activity: ['Selecting splunk_run_query when Splunk evidence is required…', 'Applying safety gates…'],
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
            ? 'Running deterministic SPL policy on the governed candidate query.'
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
          label: demo ? 'Connecting Splunk MCP search' : 'Calling MCP search',
          description: demo
            ? 'Connecting to the Splunk MCP server and running the governed search lifecycle.'
            : 'Checking Splunk MCP registry, transport, and tool policy.',
          activity: demo
            ? [
                'Resolving splunk server from MCP registry…',
                'TLS handshake 127.0.0.1 · bearer auth ✓',
                'tools/list → splunk_run_query allowed for this skill ✓',
                `Submitting search job · sid=${jobSid}`,
                `Polling job ${jobSid} · 1/3…`,
                `Polling job ${jobSid} · 2/3…`,
                'Job dispatchState=DONE · results ready',
              ]
            : [
                'Resolving splunk server from MCP registry…',
                'Verifying splunk.search is allowed for this skill…',
                'Awaiting execution gate approval…',
              ],
        },
        demo ? 2600 : 1200,
      ),
      step(
        {
          id: 'mcp_evidence',
          label: 'Packaging SourceEvidence',
          description: demo
            ? 'Fetching governed result rows and packaging them into SourceEvidence.'
            : 'Packaging search results into governed SourceEvidence.',
          activity: demo
            ? [
                `Fetching results · sid=${jobSid}…`,
                'Normalizing fields and row counts…',
                'SourceEvidence package attached · governed',
              ]
            : [
                'Preparing search preview request…',
                'Normalizing fields and row counts…',
                'Redacting sensitive fields…',
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
          label: 'Retrieving governed SOC knowledge',
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
          label: 'Mapping MITRE and severity',
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
        label: 'Applying answer governance',
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
        label: 'Applying answer governance',
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
              'Answer governance: deterministic governed answer used',
            ],
      },
      1100,
    ),
  );

  steps.push(
    step(
      {
        id: 'package',
        label: 'Packaging final analyst answer',
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
  const liveLinear = isLiveLinearProgress(state.steps);
  const stepStatuses: Record<string, InvestigationProgressStepStatus> = {
    ...(state.stepStatuses ?? {}),
  };
  const stepDisplayText: Record<string, string> = {
    ...(state.stepDisplayText ?? {}),
  };
  for (let i = 0; i < index; i += 1) {
    const id = state.steps[i].id;
    const current = stepStatuses[id];
    if (current === 'completed' || current === 'blocked' || current === 'fallback') continue;
    stepStatuses[id] = liveLinear && LIVE_OPTIONAL_STEP_IDS.has(id) ? 'skipped' : 'completed';
  }
  stepStatuses[stepId] = 'active';
  const isFinalization = stage === 'generating_answer' || stage === 'validating_answer';
  let finalization = state.finalization;
  if (stage === 'checking_mcp' && detail) {
    stepDisplayText[stepId] = detail;
    finalization = {
      phase: finalization?.phase ?? 'deterministic',
      statusLine: finalization?.statusLine ?? 'Checking MCP…',
      timeoutTier: finalization?.timeoutTier ?? 0,
      partialFallback: false,
      mcpDetail: detail,
      showRetryHint: false,
    };
  } else if (isFinalization) {
    if (stage === 'generating_answer') {
      stepDisplayText[stepId] = 'Applying governed answer policy.';
    }
    if (stage === 'validating_answer') {
      stepDisplayText[stepId] = 'Final analyst answer is being packaged…';
    }
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
    completedStepIds: Object.entries(stepStatuses)
      .filter(([, status]) => status === 'completed')
      .map(([id]) => id),
    stepStatuses,
    stepDisplayText,
    finalization,
  };
}
