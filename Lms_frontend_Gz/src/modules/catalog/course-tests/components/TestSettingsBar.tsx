import { useNotify } from "@/core/hooks/useNotify";
import { useUpdateTestMutation } from "@/modules/assessments/tests/api/testsApi";
import type { Test, TestUpdateBody } from "@/modules/assessments/tests/types";
import { Field, Select } from "@/shared/ui";

const PASS_MARKS = [50, 60, 70, 80].map((value) => ({ value: String(value), label: `${value}%` }));
const ATTEMPTS = [1, 2, 3, 5].map((value) => ({ value: String(value), label: String(value) }));

/** Pass mark, time limit, attempts and shuffling. Each change saves at once (drafts only). */
export function TestSettingsBar({ test, editable }: { test: Test; editable: boolean }) {
  const notify = useNotify();
  const [updateTest] = useUpdateTestMutation();
  const minutes = [10, 15, 20, 30, 45, 60, 90, 120].map((value) => ({ value: String(value), label: `${value} minutes` }));
  const save = (body: TestUpdateBody) => updateTest({ testId: test.test_id, body }).unwrap().catch((error) => notify.apiError(error, "Could not save the setting"));

  return (
    <div className="flex flex-wrap items-end gap-3 rounded-2xl bg-white p-4 shadow-card ring-1 ring-slate-200/60">
      <Field label="Pass mark" className="w-32">
        {(props) => <Select {...props} disabled={!editable} options={PASS_MARKS} value={String(test.pass_mark_percent)} onChange={(event) => void save({ pass_mark_percent: Number(event.target.value) })} />}
      </Field>
      <Field label="Time limit" className="w-40">
        {(props) => <Select {...props} disabled={!editable} options={minutes} value={String(test.duration_minutes ?? 20)} onChange={(event) => void save({ time_mode: "overall", duration_minutes: Number(event.target.value) })} />}
      </Field>
      <Field label="Attempts" className="w-28">
        {(props) => <Select {...props} disabled={!editable} options={ATTEMPTS} value={String(test.max_attempts)} onChange={(event) => void save({ max_attempts: Number(event.target.value) })} />}
      </Field>
      <label className="flex h-11 items-center gap-2 text-sm text-slate-700">
        <input type="checkbox" className="h-[18px] w-[18px]" disabled={!editable} checked={test.shuffle_questions} onChange={(event) => void save({ shuffle_questions: event.target.checked })} />
        Shuffle questions
      </label>
      <label className="flex h-11 items-center gap-2 text-sm text-slate-700">
        <input type="checkbox" className="h-[18px] w-[18px]" disabled={!editable} checked={test.shuffle_options} onChange={(event) => void save({ shuffle_options: event.target.checked })} />
        Shuffle options
      </label>
    </div>
  );
}
