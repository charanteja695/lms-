import { DIFFICULTY_LABELS, DIFFICULTY_TONES } from "@/modules/code-execution/common/labels";
import type { Difficulty } from "@/modules/code-execution/common/types";
import { Badge } from "@/shared/ui";

export function DifficultyBadge({ difficulty }: { difficulty: Difficulty }) {
  return <Badge tone={DIFFICULTY_TONES[difficulty]}>{DIFFICULTY_LABELS[difficulty]}</Badge>;
}
