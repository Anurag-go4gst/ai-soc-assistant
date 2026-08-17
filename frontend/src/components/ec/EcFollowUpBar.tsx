import type { EcFollowUpChip } from '@/components/ec/types';
import { Button } from '@/components/ui/button';

export function EcFollowUpBar({
  chips,
  disabled,
  onSelect,
}: {
  chips: EcFollowUpChip[];
  disabled?: boolean;
  onSelect: (followUpId: string, chip: EcFollowUpChip) => void;
}) {
  if (!chips.length) return null;
  const continueChips = chips.filter((chip) => chip.group !== 'action' && !chip.leads_to_action);
  const actionChips = chips.filter((chip) => chip.group === 'action' || Boolean(chip.leads_to_action));
  return (
    <div className="space-y-4" data-ec-followups="true">
      {continueChips.length ? (
        <section>
          <p className="soc-eyebrow text-cyan-400">Continue investigation</p>
          <div className="mt-2 flex flex-wrap gap-2">
            {continueChips.map((chip) => (
              <Button
                key={chip.follow_up_id}
                type="button"
                size="sm"
                variant="secondary"
                disabled={disabled}
                onClick={() => onSelect(chip.follow_up_id, chip)}
              >
                {chip.label}
              </Button>
            ))}
          </div>
        </section>
      ) : null}
      {actionChips.length ? (
        <section>
          <p className="soc-eyebrow text-cyan-400">Recommended actions</p>
          <div className="mt-2 flex flex-wrap gap-2">
            {actionChips.map((chip) => (
              <Button
                key={chip.follow_up_id}
                type="button"
                size="sm"
                disabled={disabled}
                onClick={() => onSelect(chip.follow_up_id, chip)}
              >
                {chip.label}
              </Button>
            ))}
          </div>
        </section>
      ) : null}
    </div>
  );
}
