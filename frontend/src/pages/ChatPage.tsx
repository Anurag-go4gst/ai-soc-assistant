import { ChatPanel } from '@/components/ChatPanel';

export function ChatPage() {
  return (
    <div className="flex h-full min-h-0 justify-center p-4 lg:p-6">
      <div className="flex h-full min-h-0 w-full max-w-[1040px] flex-col">
        <ChatPanel title="Chat" />
      </div>
    </div>
  );
}
