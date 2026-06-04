import { useState } from 'react';
import type { ReactNode } from 'react';
import { AlertTriangle, Check, Loader2, MessageSquarePlus, ThumbsDown, ThumbsUp, X } from 'lucide-react';
import { submitChatAnswerFeedback } from '@/api/client';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip';
import { cn } from '@/lib/utils';
import type { ChatAnswerFeedbackRating } from '@/types/api';

interface AnswerFeedbackControlsProps {
  turnId?: string | null;
  traceId?: string | null;
}

type SaveState = 'idle' | 'saving' | 'saved' | 'error';

const REMARK_LIMIT = 2000;

export function AnswerFeedbackControls({ turnId, traceId }: AnswerFeedbackControlsProps) {
  const [rating, setRating] = useState<ChatAnswerFeedbackRating | null>(null);
  const [remark, setRemark] = useState('');
  const [remarkOpen, setRemarkOpen] = useState(false);
  const [saveState, setSaveState] = useState<SaveState>('idle');
  const [error, setError] = useState<string | null>(null);

  if (!turnId) return null;

  const trimmedRemark = remark.trim();
  const remaining = REMARK_LIMIT - remark.length;
  const remarkTooLong = remaining < 0;

  const saveFeedback = async (nextRating: ChatAnswerFeedbackRating = rating ?? 'neutral') => {
    if (remarkTooLong || saveState === 'saving') return;
    setRating(nextRating);
    setSaveState('saving');
    setError(null);
    try {
      await submitChatAnswerFeedback({
        turn_id: turnId,
        trace_id: traceId ?? null,
        rating: nextRating,
        remark: trimmedRemark || null,
      });
      setSaveState('saved');
    } catch (err) {
      setSaveState('error');
      setError(err instanceof Error ? err.message : 'Feedback save failed');
    }
  };

  const statusBadge = (() => {
    if (saveState === 'saving') {
      return (
        <Badge variant="secondary" className="gap-1">
          <Loader2 className="h-3 w-3 animate-spin" />
          saving
        </Badge>
      );
    }
    if (saveState === 'saved') {
      return (
        <Badge variant="success" className="gap-1">
          <Check className="h-3 w-3" />
          saved
        </Badge>
      );
    }
    if (saveState === 'error') {
      return (
        <Badge variant="destructive" className="gap-1">
          <AlertTriangle className="h-3 w-3" />
          error
        </Badge>
      );
    }
    return <span className="text-[0.7rem] text-slate-500">answer feedback</span>;
  })();

  return (
    <div className="max-w-[68ch] rounded-lg border border-slate-800/70 bg-slate-950/45 p-2.5">
      <div className="flex flex-wrap items-center gap-2">
        {statusBadge}
        <div className="ml-auto flex items-center gap-1">
          <FeedbackIconButton
            label="Mark answer useful"
            active={rating === 'up'}
            disabled={saveState === 'saving'}
            onClick={() => void saveFeedback('up')}
          >
            <ThumbsUp className="h-3.5 w-3.5" />
          </FeedbackIconButton>
          <FeedbackIconButton
            label="Flag answer for review"
            active={rating === 'down'}
            disabled={saveState === 'saving'}
            onClick={() => void saveFeedback('down')}
          >
            <ThumbsDown className="h-3.5 w-3.5" />
          </FeedbackIconButton>
          <FeedbackIconButton
            label={remarkOpen ? 'Hide remarks' : 'Add remarks'}
            active={remarkOpen}
            disabled={saveState === 'saving'}
            onClick={() => setRemarkOpen((value) => !value)}
          >
            {remarkOpen ? <X className="h-3.5 w-3.5" /> : <MessageSquarePlus className="h-3.5 w-3.5" />}
          </FeedbackIconButton>
        </div>
      </div>
      {remarkOpen ? (
        <div className="mt-2 space-y-2">
          <Textarea
            value={remark}
            maxLength={REMARK_LIMIT + 200}
            onChange={(event) => {
              setRemark(event.target.value);
              if (saveState === 'error') {
                setSaveState('idle');
                setError(null);
              }
            }}
            placeholder="Optional analyst note for answer-quality review."
            className="min-h-20 text-xs"
          />
          <div className="flex flex-wrap items-center gap-2">
            <Button
              size="sm"
              variant="secondary"
              disabled={saveState === 'saving' || remarkTooLong}
              onClick={() => void saveFeedback(rating ?? 'neutral')}
            >
              {saveState === 'saving' ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Check className="h-3.5 w-3.5" />}
              Save remark
            </Button>
            <span className={cn('text-[0.7rem]', remarkTooLong ? 'text-red-200' : 'text-slate-500')}>
              {Math.max(remaining, 0)} chars left
            </span>
            {error ? <span className="text-[0.7rem] text-red-200">{error}</span> : null}
          </div>
        </div>
      ) : error ? (
        <p className="mt-2 text-[0.7rem] text-red-200">{error}</p>
      ) : null}
    </div>
  );
}

function FeedbackIconButton({
  active,
  children,
  disabled,
  label,
  onClick,
}: {
  active?: boolean;
  children: ReactNode;
  disabled?: boolean;
  label: string;
  onClick: () => void;
}) {
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <Button
          type="button"
          size="icon"
          variant={active ? 'outline' : 'ghost'}
          aria-label={label}
          disabled={disabled}
          onClick={onClick}
          className="h-7 w-7 rounded-md"
        >
          {children}
        </Button>
      </TooltipTrigger>
      <TooltipContent>{label}</TooltipContent>
    </Tooltip>
  );
}
