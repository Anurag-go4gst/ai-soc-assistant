import { Bot, User } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { cn } from '@/lib/utils';

export interface SocChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  traceId?: string;
  note?: string;
  routing?: {
    selectedSkill?: string | null;
    confidence?: number | null;
    toolPlan?: string[] | null;
    disagreement?: boolean | null;
    disagreementReason?: string | null;
  };
}

interface ChatBubbleProps {
  message: SocChatMessage;
}

export function ChatBubble({ message }: ChatBubbleProps) {
  const isUser = message.role === 'user';

  return (
    <div className={cn('flex gap-3', isUser && 'flex-row-reverse')}>
      <div
        className={cn(
          'flex h-9 w-9 shrink-0 items-center justify-center rounded-full',
          isUser ? 'bg-cyan-400 text-slate-950' : 'bg-slate-800 text-cyan-200 ring-1 ring-cyan-400/30',
        )}
      >
        {isUser ? <User className="h-4 w-4" /> : <Bot className="h-4 w-4" />}
      </div>
      <div className={cn('max-w-[86%] space-y-2', isUser && 'items-end')}>
        <div
          className={cn(
            'rounded-2xl px-4 py-3 text-sm leading-6 shadow-sm',
            isUser
              ? 'rounded-tr-md bg-cyan-400 text-slate-950'
              : 'rounded-tl-md border border-slate-800 bg-slate-900/90 text-slate-100',
          )}
        >
          {message.content}
        </div>
        {!isUser && (message.traceId || message.note) ? (
          <div className="flex flex-wrap gap-2">
            {message.traceId ? <Badge variant="secondary">trace {message.traceId.slice(0, 8)}</Badge> : null}
            {message.note ? <Badge>{message.note}</Badge> : null}
          </div>
        ) : null}
        {!isUser && message.routing?.selectedSkill ? (
          <div className="rounded-md border border-slate-800 bg-slate-950/60 p-3 text-xs text-slate-300">
            <div className="flex flex-wrap items-center gap-2">
              <Badge variant="secondary">{message.routing.selectedSkill}</Badge>
              {typeof message.routing.confidence === 'number' ? (
                <Badge>{message.routing.confidence.toFixed(2)}</Badge>
              ) : null}
              <Badge variant={message.routing.disagreement ? 'warning' : 'success'}>
                {message.routing.disagreement ? 'compare: disagree' : 'compare: agree'}
              </Badge>
            </div>
            {message.routing.toolPlan?.length ? (
              <p className="mt-2 font-mono text-[0.7rem] text-slate-400">{message.routing.toolPlan.join(' → ')}</p>
            ) : null}
            <p className="mt-2 text-slate-400">Routing complete. SPL/MCP execution is not enabled yet.</p>
          </div>
        ) : null}
      </div>
    </div>
  );
}
