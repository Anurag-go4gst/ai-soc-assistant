import { useMemo, useRef, useState, useEffect } from 'react';
import { toast } from 'sonner';
import { runDemoScenario, sendChatMessage } from '@/api/client';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { ScrollArea } from '@/components/ui/scroll-area';
import { ChatBubble, type SocChatMessage } from './ChatBubble';
import { ChatInput } from './ChatInput';
import { DemoScenarioPicker } from './DemoScenarioPicker';
import { StarterPrompts } from './StarterPrompts';
import type { DemoScenarioSummary, PlaceholderResponse } from '@/types/api';

interface ChatPanelProps {
  onTrace?: (response: PlaceholderResponse) => void;
  title?: string;
  compactHeader?: boolean;
}

export function ChatPanel({ onTrace, title = 'Investigation Workspace', compactHeader = false }: ChatPanelProps) {
  const welcome = useMemo<SocChatMessage>(
    () => ({
      id: 'welcome',
      role: 'assistant',
      content:
        'Hi Anurag. I am V.AI SOC. Choose a starter prompt or ask for triage, SPL, MITRE mapping, or investigation notes.',
      note: 'LangGraph placeholder',
    }),
    [],
  );
  const [messages, setMessages] = useState<SocChatMessage[]>([welcome]);
  const [loading, setLoading] = useState(false);
  const bottomRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' });
  }, [messages, loading]);

  const appendAssistantResponse = (response: PlaceholderResponse) => {
    onTrace?.(response);
    setMessages((current) => [
      ...current,
      {
        id: response.trace_id,
        role: 'assistant',
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
      },
    ]);
  };

  const handleSend = async (message: string) => {
    const userMessage: SocChatMessage = { id: crypto.randomUUID(), role: 'user', content: message };
    setMessages((current) => [...current, userMessage]);
    setLoading(true);

    try {
      const response = await sendChatMessage(message);
      appendAssistantResponse(response);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Chat request failed');
    } finally {
      setLoading(false);
    }
  };

  const handleRunDemo = async (scenario: DemoScenarioSummary) => {
    const userMessage: SocChatMessage = {
      id: crypto.randomUUID(),
      role: 'user',
      content: scenario.query,
    };
    setMessages((current) => [...current, userMessage]);
    setLoading(true);

    try {
      const response = await runDemoScenario(scenario.scenario_id);
      appendAssistantResponse(response);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Demo scenario failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <Card className="soc-panel flex h-full min-h-0 flex-col overflow-hidden">
      <CardHeader className={compactHeader ? 'border-b border-slate-800/70 py-3' : 'border-b border-slate-800/70'}>
        <CardTitle className="text-sm font-semibold">{title}</CardTitle>
        <StarterPrompts disabled={loading} onPick={handleSend} />
        <DemoScenarioPicker disabled={loading} onRun={handleRunDemo} />
      </CardHeader>
      <CardContent className="min-h-0 flex-1 p-0">
        <ScrollArea className="h-full">
          <div className="space-y-4 px-5 py-4">
            {messages.map((message) => (
              <ChatBubble key={message.id} message={message} />
            ))}
            {loading ? (
              <ChatBubble
                message={{ id: 'typing', role: 'assistant', content: 'Preparing governed placeholder response…' }}
              />
            ) : null}
            <div ref={bottomRef} />
          </div>
        </ScrollArea>
      </CardContent>
      <ChatInput disabled={loading} onSend={handleSend} />
    </Card>
  );
}
