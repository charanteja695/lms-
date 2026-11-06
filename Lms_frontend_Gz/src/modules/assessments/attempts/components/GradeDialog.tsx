import { useState } from "react";
import { FormProvider, useForm } from "react-hook-form";

import { useNotify } from "@/core/hooks/useNotify";
import { useGradeAnswerMutation } from "@/modules/assessments/attempts/api/attemptsApi";
import { AnswerPreview } from "@/modules/assessments/attempts/components/grading/AnswerPreview";
import type { GradingQueueItem } from "@/modules/assessments/attempts/gradingTypes";
import { TextareaField, TextField } from "@/shared/form";
import { Button, Input, Modal } from "@/shared/ui";

interface GradeFormValues {
  marks: string;
  feedback: string;
}

interface RubricCriterion {
  id: string;
  criterion: string;
  max_marks: number;
}

export function GradeDialog({ open, onClose, item }: { open: boolean; onClose: () => void; item: GradingQueueItem }) {
  const notify = useNotify();
  const [gradeAnswer, { isLoading }] = useGradeAnswerMutation();
  const form = useForm<GradeFormValues>({ defaultValues: { marks: "", feedback: "" } });
  const rubric = item.rubric as unknown as RubricCriterion[];
  const [rubricScores, setRubricScores] = useState<Record<string, string>>({});

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="Grade this answer"
      size="lg"
      footer={
        <>
          <Button variant="secondary" onClick={onClose} disabled={isLoading}>
            Cancel
          </Button>
          <Button type="submit" form="grade-form" loading={isLoading}>
            Save grade
          </Button>
        </>
      }
    >
      <div className="mb-4 space-y-3">
        <p className="whitespace-pre-wrap text-sm text-slate-700">{item.text}</p>
        <div className="rounded-xl bg-slate-50 p-4 ring-1 ring-slate-200/70">
          <p className="mb-2 text-xs font-bold uppercase tracking-[0.06em] text-slate-500">Student's answer</p>
          <AnswerPreview item={item} />
        </div>
      </div>
      <FormProvider {...form}>
        <form
          id="grade-form"
          noValidate
          className="space-y-4"
          onSubmit={form.handleSubmit(async (values) => {
            try {
              await gradeAnswer({
                attemptId: item.attempt_id,
                questionId: item.question_id,
                body: rubric.length
                  ? { rubric_scores: Object.fromEntries(rubric.map((criterion) => [criterion.id, Number(rubricScores[criterion.id] ?? 0)])), feedback: values.feedback || null }
                  : { marks: Number(values.marks), feedback: values.feedback || null },
              }).unwrap();
              notify.success("Grade saved");
              onClose();
            } catch (error) {
              notify.apiError(error);
            }
          })}
        >
          {rubric.length > 0 ? (
            <div className="space-y-2">
              {rubric.map((criterion) => (
                <div key={criterion.id} className="flex items-center justify-between gap-3">
                  <span className="text-sm text-slate-700">{criterion.criterion}</span>
                  <Input
                    type="number"
                    max={criterion.max_marks}
                    value={rubricScores[criterion.id] ?? ""}
                    onChange={(event) => setRubricScores({ ...rubricScores, [criterion.id]: event.target.value })}
                    placeholder={`/ ${criterion.max_marks}`}
                    className="w-24"
                  />
                </div>
              ))}
            </div>
          ) : (
            <TextField<GradeFormValues> name="marks" label={`Marks (max ${item.marks})`} type="number" required />
          )}
          <TextareaField<GradeFormValues> name="feedback" label="Feedback" rows={3} hint="Required if you're overriding an automatic grade." />
        </form>
      </FormProvider>
    </Modal>
  );
}
