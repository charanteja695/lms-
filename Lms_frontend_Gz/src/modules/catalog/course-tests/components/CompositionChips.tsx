import { cn } from "@/core/lib/cn";
import type { TestComposition } from "@/modules/assessments/tests/reportTypes";

/** "Multiple choice 3 / 5", "Programs 1 / 1": green once the requirement is met. Counts come from the server. */
export function CompositionChips({ composition }: { composition: TestComposition }) {
  const chips = [
    { label: "Multiple choice", have: composition.multiple_choice, need: composition.required_multiple_choice },
    { label: "Programs", have: composition.programs, need: composition.required_programs },
  ];
  return (
    <div className="flex flex-wrap gap-2">
      {chips.map((chip) => {
        const met = chip.have >= chip.need;
        return (
          <span key={chip.label} className={cn("rounded-full px-3 py-1.5 text-xs font-bold", met ? "bg-brand-50 text-brand-800 ring-1 ring-brand-200" : "bg-amber-100 text-amber-900 ring-1 ring-amber-300")}>
            {chip.label} {chip.have}{chip.need ? ` / ${chip.need}` : ""}
          </span>
        );
      })}
    </div>
  );
}
