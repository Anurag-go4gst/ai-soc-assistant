import { useMemo, useState } from 'react';
import { toast } from 'sonner';
import { sendChatMessage } from '@/api/client';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { ScrollArea } from '@/components/ui/scroll-area';
import { ChatBubble, type SocChatMessage } from './ChatBubble';
import { ChatInput } from './ChatInput';
import { StarterPrompts } from './StarterPrompts';
import type { PlaceholderResponse } from '@/types/api';

interface ChatPanelProps {
  onTrace: (response: PlaceholderResponse) => void;
}

export function ChatPanel({ onTrace }: ChatPanelProps) {
  const welcome = useMemo<SocChatMessage>(
    () => ({
      id: 'welcome',
      role: 'assistant',
      content: 'Hi Anurag. I am V.AI SOC. Choose a starter prompt or ask for triage, SPL, MITRE mapping, or investigation notes.',
      note: 'LangGraph placeholder',
    }),
    [],
  );
  const [messages, setMessages] = useState<SocChatMessage[]>([welcome]);
  const [loading, setLoading] = useState(false);

  const handleSend = async (message: string) => {
    const userMessage: SocChatMessage = { id: crypto.randomUUID(), role: 'user', content: message };
    setMessages((current) => [...current, userMessage]);
    setLoading(true);

    try {
      const response = await sendChatMessage(message);
      onTrace(response);
      setMessages((current) => [
        ...current,
        {
          id: response.trace_id,
          role: 'assistant',
          content: response.message,
          traceId: response.trace_id,
          note: response.note,
        },
      ]);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Chat request failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <Card className="soc-panel flex min-h-[640px] flex-col overflow-hidden">
      <CardHeader className="border-b border-slate-800">
        <CardTitle>Investigation Workspace</CardTitle>
        <StarterPrompts disabled={loading} onPick={handleSend} />
      </CardHeader>
      <CardContent className="min-h-0 flex-1 p-0">
        <ScrollArea className="h-[460px] p-5">
          <div className="space-y-5">
            {messages.map((message) => (
              <ChatBubble key={message.id} message={message} />
            ))}
            {loading ? (
              <ChatBubble message={{ id: 'typing', role: 'assistant', content: 'Preparing governed placeholder response...' }} />
            ) : null}
          </div>
        </ScrollArea>
      </CardContent>
      <ChatInput disabled={loading} onSend={handleSend} />
    </Card>
  );
}
