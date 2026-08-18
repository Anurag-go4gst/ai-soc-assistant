import {
  Children,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from 'react';
import { cn } from '@/lib/utils';

const STAGGER_MS = 440;

function prefersReducedMotion(): boolean {
  if (typeof window === 'undefined' || !window.matchMedia) return false;
  return window.matchMedia('(prefers-reduced-motion: reduce)').matches;
}

export function EcAnswerReveal({
  active,
  revealKey,
  children,
  className,
  onRevealStart,
  onRevealComplete,
}: {
  active: boolean;
  revealKey: number;
  children: ReactNode;
  className?: string;
  onRevealStart?: () => void;
  onRevealComplete?: () => void;
}) {
  const blocks = useMemo(() => Children.toArray(children), [children]);
  const blockCount = blocks.length;
  const [visibleCount, setVisibleCount] = useState(0);
  const reducedMotion = prefersReducedMotion();
  const onRevealStartRef = useRef(onRevealStart);
  const onRevealCompleteRef = useRef(onRevealComplete);
  onRevealStartRef.current = onRevealStart;
  onRevealCompleteRef.current = onRevealComplete;

  useEffect(() => {
    if (!active) {
      setVisibleCount(0);
      return;
    }

    if (reducedMotion || blockCount === 0) {
      setVisibleCount(blockCount);
      onRevealStartRef.current?.();
      return;
    }

    setVisibleCount(1);
    onRevealStartRef.current?.();
  }, [active, revealKey, blockCount, reducedMotion]);

  useEffect(() => {
    if (!active || reducedMotion || visibleCount === 0 || visibleCount >= blockCount) return;

    const timer = window.setTimeout(() => {
      setVisibleCount((count) => count + 1);
    }, STAGGER_MS);

    return () => window.clearTimeout(timer);
  }, [active, reducedMotion, visibleCount, blockCount]);

  useEffect(() => {
    if (!active || blockCount === 0) return;
    if (visibleCount >= blockCount) {
      onRevealCompleteRef.current?.();
    }
  }, [active, visibleCount, blockCount]);

  if (!active) {
    return (
      <div
        className={cn('ec-answer-reveal space-y-6', className)}
        data-ec-answer-reveal="idle"
        data-ec-reveal-progress={blockCount}
        data-ec-reveal-total={blockCount}
      >
        {blocks.map((child, index) => (
          <div key={`static-${index}`} className="ec-reveal-block-mount">
            {child}
          </div>
        ))}
      </div>
    );
  }

  const shown = reducedMotion ? blockCount : visibleCount;

  return (
    <div
      key={revealKey}
      className={cn('ec-answer-reveal space-y-6 ec-answer-reveal-active', className)}
      data-ec-answer-reveal="active"
      data-ec-reveal-progress={shown}
      data-ec-reveal-total={blockCount}
    >
      {blocks.slice(0, shown).map((child, index) => (
        <div key={`${revealKey}-${index}`} className="ec-reveal-block-mount">
          {child}
        </div>
      ))}
    </div>
  );
}

export function EcRevealBlock({
  children,
  className,
}: {
  children: ReactNode;
  className?: string;
}) {
  return <div className={cn('ec-reveal-block', className)}>{children}</div>;
}

export function EcStreamingText({
  text,
  className,
  active = true,
  onComplete,
}: {
  text: string;
  className?: string;
  active?: boolean;
  onComplete?: () => void;
}) {
  const [visibleLength, setVisibleLength] = useState(0);
  const reducedMotion = prefersReducedMotion();

  useEffect(() => {
    if (!active || !text) {
      setVisibleLength(text?.length ?? 0);
      return;
    }

    if (reducedMotion) {
      setVisibleLength(text.length);
      onComplete?.();
      return;
    }

    setVisibleLength(0);
    const tickMs = 16;
    const maxDurationMs = 2400;
    const charsPerTick = Math.max(1, Math.ceil(text.length / (maxDurationMs / tickMs)));

    const timer = window.setInterval(() => {
      setVisibleLength((current) => {
        const next = Math.min(text.length, current + charsPerTick);
        if (next >= text.length) {
          window.clearInterval(timer);
          onComplete?.();
        }
        return next;
      });
    }, tickMs);

    return () => window.clearInterval(timer);
  }, [text, active, reducedMotion, onComplete]);

  return (
    <span className={className}>
      {text.slice(0, visibleLength)}
      {active && !reducedMotion && visibleLength < text.length ? (
        <span className="ec-stream-caret ml-0.5 inline-block w-2 animate-pulse text-cyan-400/80" aria-hidden="true">
          |
        </span>
      ) : null}
    </span>
  );
}
