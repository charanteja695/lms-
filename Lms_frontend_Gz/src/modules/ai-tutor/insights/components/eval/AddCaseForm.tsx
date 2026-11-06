import { useState } from "react";

import { useNotify } from "@/core/hooks/useNotify";
import { useAddEvalCaseMutation } from "@/modules/ai-tutor/insights/api/insightsApi";
import { useCourseLessons } from "@/modules/ai-tutor/insights/hooks/useCourseLessons";
import { Button, Card, Checkbox, Field, Input } from "@/shared/ui";

const MAX_EXPECTED = 10;

/** A question students ask, and the lesson(s) that should come back for it (1–10). */
export function AddCaseForm({ evalSetId, courseId }: { evalSetId: string; courseId: string }) {
  const notify = useNotify();
  const { lessons, isFetching, unavailable } = useCourseLessons(courseId);
  const [add, { isLoading }] = useAddEvalCaseMutation();
  const [question, setQuestion] = useState("");
  const [expected, setExpected] = useState<string[]>([]);
  const [typedIds, setTypedIds] = useState("");
  const ids = unavailable ? typedIds.split(/[\s,]+/).filter(Boolean) : expected;

  const toggle = (itemId: string) =>
    setExpected((current) => (current.includes(itemId) ? current.filter((id) => id !== itemId) : current.length < MAX_EXPECTED ? [...current, itemId] : current));

  return (
    <Card title="Add a question">
      <div className="space-y-4">
        <Field label="Question" required>{(props) => <Input {...props} value={question} maxLength={500} placeholder="What is a base case in recursion?" onChange={(event) => setQuestion(event.target.value)} />}</Field>
        {unavailable ? (
          <Field label="Expected lesson ids" required hint="The course's lessons couldn't be listed here; paste lesson (topic item) ids, comma separated.">
            {(props) => <Input {...props} value={typedIds} onChange={(event) => setTypedIds(event.target.value)} />}
          </Field>
        ) : (
          <div>
            <p className="mb-2 text-sm font-medium text-slate-700">Lessons that answer it ({expected.length}/{MAX_EXPECTED})</p>
            <div className="max-h-56 space-y-1 overflow-y-auto rounded-lg border border-slate-200 p-2">
              {isFetching && <p className="text-sm text-slate-500">Loading lessons…</p>}
              {lessons.map((lesson) => (
                <Checkbox
                  key={lesson.item_id}
                  label={`${lesson.title} — ${lesson.path}`}
                  checked={expected.includes(lesson.item_id)}
                  onChange={() => toggle(lesson.item_id)}
                />
              ))}
            </div>
          </div>
        )}
        <div className="flex justify-end">
          <Button
            icon="plus"
            loading={isLoading}
            disabled={!question.trim() || ids.length === 0}
            onClick={async () => {
              try {
                await add({ evalSetId, question: question.trim(), expected_item_ids: ids }).unwrap();
                setQuestion("");
                setExpected([]);
                setTypedIds("");
              } catch (error) {
                notify.apiError(error);
              }
            }}
          >
            Add question
          </Button>
        </div>
      </div>
    </Card>
  );
}
