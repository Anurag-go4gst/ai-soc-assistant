import type { ReactNode } from 'react';
import { Bot, User } from 'lucide-react';
import { cn } from '@/lib/utils';

export function EcChatBubble({
  role,
  children,
  className,
}: {
  role: 'user' | 'assistant';
  children: ReactNode;
  className?: string;
}) {
  const isUser = role === 'user';
  return (
    <div className={cn('flex gap-3', isUser && 'flex-row-reverse', className)} data-ec-chat-role={role}>
      <div
        className={cn(
          'flex h-8 w-8 shrink-0 items-center justify-center rounded-full',
          isUser ? 'bg-cyan-400 text-slate-950' : 'bg-slate-800 text-cyan-200 ring-1 ring-cyan-400/25',
        )}
      >
        {isUser ? <User className="h-4 w-4" /> : <Bot className="h-4 w-4" />}
      </div>
      <div
        className={cn(
          'min-w-0 flex-1 rounded-2xl px-4 py-3 text-sm leading-relaxed shadow-sm break-words',
          isUser
            ? 'max-w-[min(100%,48rem)] bg-cyan-500/15 text-slate-50 ring-1 ring-cyan-400/25'
            : 'max-w-full soc-panel text-slate-200 ring-1 ring-slate-800/80',
        )}
      >
        {children}
      </div>
    </div>
  );
}
