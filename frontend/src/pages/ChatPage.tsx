import { ChatPanel } from '@/components/ChatPanel';

export function ChatPage() {
  return (
    <div className="h-full min-h-0 w-full min-w-0">
      <ChatPanel title="Chat" flush />
    </div>
  );
}
