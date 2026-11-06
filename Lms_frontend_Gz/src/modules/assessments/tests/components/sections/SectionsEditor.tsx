import { useState } from "react";

import { useNotify } from "@/core/hooks/useNotify";
import { useReplaceSectionsMutation } from "@/modules/assessments/tests/api/testsApi";
import { SectionCard } from "@/modules/assessments/tests/components/sections/SectionCard";
import type { SectionInput } from "@/modules/assessments/tests/sectionTypes";
import type { Test } from "@/modules/assessments/tests/types";
import { Button, Card, EmptyState } from "@/shared/ui";

function toInput(test: Test): SectionInput[] {
  return test.sections.map((section) => ({
    title: section.title,
    instructions: section.instructions,
    time_limit_minutes: section.time_limit_minutes,
    slots: section.slots.map((slot) => ({ slot_type: slot.slot_type, question_id: slot.question_id, criteria: slot.criteria, count: slot.count, marks: slot.marks })),
  }));
}

export function SectionsEditor({ test, editable }: { test: Test; editable: boolean }) {
  const notify = useNotify();
  const [sections, setSections] = useState<SectionInput[]>(() => toInput(test));
  const [replaceSections, { isLoading }] = useReplaceSectionsMutation();
  const perSection = test.time_mode === "per_section";

  const setSection = (index: number, section: SectionInput) => setSections(sections.map((item, i) => (i === index ? section : item)));
  const moveSection = (index: number, direction: "up" | "down") => {
    const next = [...sections];
    const swapWith = direction === "up" ? index - 1 : index + 1;
    [next[index], next[swapWith]] = [next[swapWith]!, next[index]!];
    setSections(next);
  };

  if (!editable) {
    return (
      <Card title="Sections" description="Read-only once the test leaves draft.">
        {sections.length === 0 ? (
          <EmptyState icon="terminal" title="No sections" description="Add a section to start building this test." />
        ) : (
          <ul className="space-y-2">
            {sections.map((section, index) => (
              <li key={index} className="rounded-lg border border-slate-100 bg-slate-50 px-3 py-2 text-sm text-slate-700">
                {section.title} · {section.slots.length} slot{section.slots.length === 1 ? "" : "s"}
                {section.time_limit_minutes && ` · ${section.time_limit_minutes} min`}
              </li>
            ))}
          </ul>
        )}
      </Card>
    );
  }

  return (
    <Card
      title="Sections"
      description="Replaces the whole structure when saved."
      actions={
        <Button
          size="sm"
          loading={isLoading}
          onClick={async () => {
            try {
              await replaceSections({ testId: test.test_id, sections }).unwrap();
              notify.success("Sections saved");
            } catch (error) {
              notify.apiError(error);
            }
          }}
        >
          Save sections
        </Button>
      }
    >
      <div className="space-y-4">
        {sections.map((section, index) => (
          <SectionCard
            key={index}
            section={section}
            onChange={(next) => setSection(index, next)}
            onRemove={() => setSections(sections.filter((_, i) => i !== index))}
            onMove={(direction) => moveSection(index, direction)}
            canMoveUp={index > 0}
            canMoveDown={index < sections.length - 1}
            showTimeLimit={perSection}
          />
        ))}
        <Button variant="secondary" icon="plus" onClick={() => setSections([...sections, { title: `Section ${sections.length + 1}`, slots: [] }])}>
          Add section
        </Button>
      </div>
    </Card>
  );
}
