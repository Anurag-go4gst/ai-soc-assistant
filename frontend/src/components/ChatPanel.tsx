import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { toast } from 'sonner';
import { runDemoScenario, sendChatMessage } from '@/api/client';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { ScrollArea } from '@/components/ui/scroll-area';
import { ChatBubble, type SocChatMessage } from './ChatBubble';
import { ChatInput } from './ChatInput';
import { DemoScenarioPicker } from './DemoScenarioPicker';
import { StarterPrompts } from './StarterPrompts';
import { cn } from '@/lib/utils';
import { isClearChatCommand } from '@/lib/chatCommands';
import {
  buildInvestigationProgressSteps,
  delay,
  playInvestigationProgress,
} from '@/lib/investigationProgress';
import type { DemoScenarioSummary, PlaceholderResponse } from '@/types/api';

interface ChatPanelProps {
  onTrace?: (response: PlaceholderResponse) => void;
  onClear?: () => void;
  title?: string;
  compactHeader?: boolean;
  flush?: boolean;
}

function assistantMessageFromResponse(response: PlaceholderResponse): Omit<SocChatMessage, 'id' | 'role'> {
  return {
    content: response.message,
    traceId: response.trace_id,
    note: response.note,
    trace: response,
    routing: {
      selectedSkill: response.selected_skill,
      confidence: response.confidence,
      toolPlan: response.tool_plan,
      disagreement: response.disagreement,
      disagreementReason: response.disagreement_reason,
    },
    workflowPlan: response.workflow_plan,
    candidateSpl: response.candidate_spl,
    splValidation: response.spl_validation,
    execution: response.execution,
    humanReview: response.human_review,
  };
}

export function ChatPanel({ onTrace, onClear, title = 'Investigation Workspace', compactHeader = false, flush = false }: ChatPanelProps) {
  const welcome = useMemo<SocChatMessage>(
    () => ({
      id: 'welcome',
      role: 'assistant',
      content:
        'Hi Anurag. I am V.AI SOC. Choose a starter prompt or ask for triage, SPL, MITRE mapping, or investigation notes.',
    }),
    [],
  );
  const [messages, setMessages] = useState<SocChatMessage[]>([welcome]);
  const [loading, setLoading] = useState(false);
  const investigationEpochRef = useRef(0);

  const conversationStarted = messages.some((message) => message.role === 'user');

  const isStaleInvestigation = (epoch: number) => epoch !== investigationEpochRef.current;

  useEffect(() => {
    const last = messages[messages.length - 1];
    if (!last) return;

    const scrollTo = (selector: string, block: ScrollLogicalPosition) => {
      requestAnimationFrame(() => {
        document.querySelector(selector)?.scrollIntoView({ behavior: 'smooth', block, inline: 'nearest' });
      });
    };

    if (last.role === 'user') {
      scrollTo(`[data-message-id="${last.id}"]`, 'end');
      return;
    }
    if (last.displayStage === 'progress') {
      scrollTo(`[data-message-id="${last.id}"]`, 'start');
      return;
    }
    if (last.displayStage === 'summary' || last.displayStage === 'complete') {
      scrollTo(`[data-answer-scroll-anchor="${last.id}"]`, 'start');
    }
  }, [messages]);

  const runStagedInvestigation = async (
    fetcher: () => Promise<PlaceholderResponse>,
    hints?: {
      expectedSkill?: string | null;
      expectedSources?: string[];
      demoMode?: boolean;
    },
  ) => {
    const epoch = investigationEpochRef.current;
    const progressId = `progress-${crypto.randomUUID()}`;
    const steps = buildInvestigationProgressSteps({
      expectedSkill: hints?.expectedSkill,
      expectedSources: hints?.expectedSources,
      demoMode: hints?.demoMode ?? true,
    });

    setMessages((current) => [
      ...current,
      {
        id: progressId,
        role: 'assistant',
        content: 'Running governed investigation pipeline…',
        displayStage: 'progress',
        investigationProgress: { steps, activeStepIndex: 0, completedStepIds: [] },
      },
    ]);
    setLoading(true);

    try {
      const fetchPromise = fetcher();
      await playInvestigationProgress(steps, (investigationProgress) => {
        if (isStaleInvestigation(epoch)) return;
        setMessages((current) =>
          current.map((message) =>
            message.id === progressId ? { ...message, investigationProgress } : message,
          ),
        );
      });
      const response = await fetchPromise;
      if (isStaleInvestigation(epoch)) return;
      onTrace?.(response);

      const payload = assistantMessageFromResponse(response);

      setMessages((current) =>
        current.map((message) =>
          message.id === progressId
            ? {
                id: response.trace_id,
                role: 'assistant',
                displayStage: 'summary',
                investigationProgress: undefined,
                ...payload,
              }
            : message,
        ),
      );

      await delay(550);

      if (isStaleInvestigation(epoch)) return;

      setMessages((current) =>
        current.map((message) =>
          message.id === response.trace_id ? { ...message, displayStage: 'complete' } : message,
        ),
      );
    } catch (error) {
      if (!isStaleInvestigation(epoch)) {
        setMessages((current) => current.filter((message) => message.id !== progressId));
        toast.error(error instanceof Error ? error.message : 'Investigation request failed');
      }
    } finally {
      if (!isStaleInvestigation(epoch)) {
        setLoading(false);
      }
    }
  };

  const handleClear = useCallback(() => {
    investigationEpochRef.current += 1;
    setLoading(false);
    setMessages([welcome]);
    onClear?.();
  }, [onClear, welcome]);

  const handleSend = async (message: string) => {
    if (isClearChatCommand(message)) {
      handleClear();
      return;
    }
    const userMessage: SocChatMessage = { id: crypto.randomUUID(), role: 'user', content: message };
    setMessages((current) => [...current, userMessage]);
    await runStagedInvestigation(() => sendChatMessage(message), { demoMode: false });
  };

  const handleRunDemo = async (scenario: DemoScenarioSummary) => {
    const userMessage: SocChatMessage = {
      id: crypto.randomUUID(),
      role: 'user',
      content: scenario.query,
    };
    setMessages((current) => [...current, userMessage]);
    await runStagedInvestigation(() => runDemoScenario(scenario.scenario_id), {
      expectedSkill: scenario.expected_skill,
      expectedSources: scenario.expected_sources,
      demoMode: true,
    });
  };

  return (
    <Card
      className={cn(
        'flex h-full min-h-0 flex-col overflow-hidden',
        flush ? 'rounded-none border-0 bg-transparent shadow-none' : 'soc-panel',
      )}
    >
      <CardHeader className={compactHeader ? 'border-b border-slate-800/70 py-3' : 'border-b border-slate-800/70'}>
        <CardTitle className="text-sm font-semibold">{title}</CardTitle>
        {!conversationStarted ? (
          <>
            <StarterPrompts disabled={loading} onPick={handleSend} />
            <DemoScenarioPicker disabled={loading} onRun={handleRunDemo} />
          </>
        ) : null}
      </CardHeader>
      <CardContent className="min-h-0 flex-1 p-0">
        <ScrollArea className="h-full">
          <div className="space-y-4 px-5 pb-8 pt-4">
            {messages.map((message) => (
              <ChatBubble key={message.id} message={message} />
            ))}
          </div>
        </ScrollArea>
      </CardContent>
      <ChatInput disabled={loading} onClear={handleClear} onSend={handleSend} />
    </Card>
  );
}
