import { Bot, User } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { cn } from '@/lib/utils';

export interface SocChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  traceId?: string;
  note?: string;
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
      </div>
    </div>
  );
}
