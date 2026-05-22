import { KeyboardEvent, useState } from 'react';
import { Send } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';

interface ChatInputProps {
  disabled?: boolean;
  onSend: (message: string) => void;
}

export function ChatInput({ disabled, onSend }: ChatInputProps) {
  const [text, setText] = useState('');

  const submit = () => {
    const value = text.trim();
    if (!value) return;
    onSend(value);
    setText('');
  };

  const handleKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      submit();
    }
  };

  return (
    <div className="flex items-end gap-2 border-t border-slate-800 bg-slate-950/80 p-4">
      <Textarea
        className="max-h-32 min-h-[46px] resize-none"
        disabled={disabled}
        onChange={(event) => setText(event.target.value)}
        onKeyDown={handleKeyDown}
        placeholder="Ask V.AI SOC to investigate, generate SPL, map MITRE, or prepare notes..."
        value={text}
      />
      <Button type="button" size="icon" disabled={disabled || !text.trim()} onClick={submit} aria-label="Send message">
        <Send className="h-4 w-4" />
      </Button>
    </div>
  );
}
