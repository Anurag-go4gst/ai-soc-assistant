import type { EcFollowUpChip } from '@/components/ec/types';
import { Button } from '@/components/ui/button';

export function EcFollowUpBar({
  chips,
  disabled,
  onSelect,
}: {
  chips: EcFollowUpChip[];
  disabled?: boolean;
  onSelect: (followUpId: string) => void;
}) {
  if (!chips.length) return null;
  return (
    <div className="flex flex-wrap gap-2" data-ec-followups="true">
      {chips.map((chip) => (
        <Button
          key={chip.follow_up_id}
          type="button"
          size="sm"
          variant="secondary"
          disabled={disabled}
          onClick={() => onSelect(chip.follow_up_id)}
        >
          {chip.label}
        </Button>
      ))}
    </div>
  );
}
