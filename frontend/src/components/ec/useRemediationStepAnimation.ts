import { useCallback, useEffect, useRef, useState } from 'react';

const QUEUE_HOLD_MS = 5000;
const STAGGER_MS = 450;

export type RemediationAnimationPhase = 'idle' | 'queued' | 'completing' | 'done';

export function useRemediationStepAnimation(
  stepIds: string[],
  active: boolean,
  options?: { terminalStatus?: string },
) {
  const terminalStatus = (options?.terminalStatus ?? 'COMPLETE').toUpperCase();
  const [phase, setPhase] = useState<RemediationAnimationPhase>('idle');
  const [statusByStepId, setStatusByStepId] = useState<Record<string, string>>({});
  const timersRef = useRef<Array<ReturnType<typeof setTimeout>>>([]);

  const clearTimers = useCallback(() => {
    for (const timer of timersRef.current) {
      clearTimeout(timer);
    }
    timersRef.current = [];
  }, []);

  const reset = useCallback(() => {
    clearTimers();
    setPhase('idle');
    setStatusByStepId({});
  }, [clearTimers]);

  useEffect(() => {
    if (!active || stepIds.length === 0) {
      reset();
      return;
    }

    clearTimers();
    const queued = Object.fromEntries(stepIds.map((id) => [id, 'QUEUED']));
    setStatusByStepId(queued);
    setPhase('queued');

    const holdTimer = setTimeout(() => {
      setPhase('completing');
      const order = [...stepIds].sort(() => Math.random() - 0.5);
      order.forEach((stepId, index) => {
        const staggerTimer = setTimeout(() => {
          setStatusByStepId((current) => ({ ...current, [stepId]: terminalStatus }));
          if (index === order.length - 1) {
            setPhase('done');
          }
        }, index * STAGGER_MS);
        timersRef.current.push(staggerTimer);
      });
    }, QUEUE_HOLD_MS);
    timersRef.current.push(holdTimer);

    return () => {
      clearTimers();
    };
  }, [active, clearTimers, reset, stepIds.join('|'), terminalStatus]);

  const runAnimation = useCallback(
    (ids: string[]): Promise<void> =>
      new Promise((resolve) => {
        clearTimers();
        if (ids.length === 0) {
          resolve();
          return;
        }
        const queued = Object.fromEntries(ids.map((id) => [id, 'QUEUED']));
        setStatusByStepId(queued);
        setPhase('queued');

        const holdTimer = setTimeout(() => {
          setPhase('completing');
          const order = [...ids].sort(() => Math.random() - 0.5);
          order.forEach((stepId, index) => {
            const staggerTimer = setTimeout(() => {
              setStatusByStepId((current) => ({ ...current, [stepId]: 'COMPLETE' }));
              if (index === order.length - 1) {
                setPhase('done');
                resolve();
              }
            }, index * STAGGER_MS);
            timersRef.current.push(staggerTimer);
          });
        }, QUEUE_HOLD_MS);
        timersRef.current.push(holdTimer);
      }),
    [clearTimers],
  );

  return { phase, statusByStepId, runAnimation, reset };
}
