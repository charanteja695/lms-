import { ImportExcelModal } from "@/modules/catalog/course-tests/components/ImportExcelModal";
import { useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

import { toApiError } from "@/core/lib/apiError";
import { useNotify } from "@/core/hooks/useNotify";
import { TestStatusBadge } from "@/modules/assessments/common/components/TestStatusBadge";
import type { Question } from "@/modules/assessments/questions/types";
import { CompositionChips } from "@/modules/catalog/course-tests/components/CompositionChips";
import { emptyMcq, McqEditor } from "@/modules/catalog/course-tests/components/McqEditor";
import { paperEntries, QuestionList } from "@/modules/catalog/course-tests/components/QuestionList";
import { TestSettingsBar } from "@/modules/catalog/course-tests/components/TestSettingsBar";
import { type CourseTestKind, useCourseTest } from "@/modules/catalog/course-tests/hooks/useCourseTest";
import type { McqDraft } from "@/modules/catalog/course-tests/hooks/useTestQuestions";
import { useTestQuestions } from "@/modules/catalog/course-tests/hooks/useTestQuestions";
import { useTestPublishing } from "@/modules/catalog/course-tests/hooks/useTestPublishing";
import { useGetCourseQuery, useGetVersionQuery } from "@/modules/catalog/courses/api/coursesApi";
import { useCan } from "@/modules/user-management/common/permissions/useCan";
import { Alert, Button, EmptyState, Icon, PageLoader } from "@/shared/ui";

function draftFrom(question: Question): McqDraft {
  const version = question.working ?? question.current;
  return {
    questionId: question.question_id,
    text: version?.text ?? "",
    options: ((version?.body.options as McqDraft["options"] | undefined) ?? []).map((option) => ({ id: option.id, text: option.text })),
    correct: String(version?.answer_key.correct ?? "a"),
    explanation: version?.explanation ?? "",
    marks: version?.default_marks ?? 1,
  };
}

/** One course test: a topic's test or the final test. Questions on the left, the one being written on the right. */
export function CourseTestPage({ kind }: { kind: CourseTestKind }) {
  const { courseId = "", versionId = "", topicId } = useParams();
  const navigate = useNavigate();
  const notify = useNotify();
  const { can } = useCan();
  const { data: course } = useGetCourseQuery(courseId, { skip: !courseId });
  const { data: version } = useGetVersionQuery({ courseId, versionId }, { skip: !courseId || !versionId });
  const { targetId, test, validation, publishedOther, place, isLoading } = useCourseTest(kind, courseId, topicId, version);
  const questions = useTestQuestions(test);
  const publishing = useTestPublishing(kind, { courseId, versionId, targetId });
  const [editing, setEditing] = useState<McqDraft | null>(null);
  const [publishError, setPublishError] = useState<string | null>(null);
  const [publishBusy, setPublishBusy] = useState(false);
  const [showImportModal, setShowImportModal] = useState(false);

  const base = `/courses/${courseId}/versions/${versionId}`;
  const title = kind === "final" ? "Final course test" : "Topic test";
  const context = kind === "final" ? `${course?.title ?? "Course"} · after every module` : place ? `Module ${place.code.split(".")[0]} · ${place.code} ${place.topic.title}` : "";
  const canAuthor = can("content.author");
  const editable = Boolean(test && test.status === "draft" && canAuthor);
  const entries = test ? paperEntries(test) : [];

  if (isLoading) return <PageLoader />;

  const publish = async () => {
    if (!test) return;
    setPublishBusy(true);
    setPublishError(null);
    try {
      const outcome = await publishing.publish(test, publishedOther);
      notify.success(outcome === "published" ? `${title} published` : "Sent for review", outcome === "published" ? (kind === "topic" ? "Learners take it after this topic's lessons." : "It is now the course's final test.") : undefined);
      navigate(base);
    } catch (caught) {
      const apiError = toApiError(caught);
      setPublishError(apiError.details.length ? apiError.details.map((detail) => detail.message).join(". ") : apiError.message);
    } finally {
      setPublishBusy(false);
    }
  };
  const openQuestion = (question: Question) => {
    if (question.question_type === "coding") navigate(`${base}/tests/${test?.test_id}/programs/${question.question_id}?back=${encodeURIComponent(location.pathname)}`);
    else setEditing(draftFrom(question));
  };

  return (
    <>
      <header className="mb-5 flex flex-wrap items-center gap-3">
        <Link to={base} aria-label="Back to the builder" className="flex h-10 w-10 items-center justify-center rounded-xl bg-white text-slate-600 shadow-card ring-1 ring-slate-200/60 hover:text-navy-950">
          <Icon name="chevronLeft" size={18} />
        </Link>
        <div className="min-w-0 flex-1">
          <p className="truncate text-[13px] font-semibold text-brand-700">{context}</p>
          <div className="flex flex-wrap items-center gap-2.5">
            <h1 className="text-2xl font-extrabold tracking-tight text-navy-950">{title}</h1>
            {test && <TestStatusBadge status={test.status} />}
          </div>
        </div>
        {validation && <CompositionChips composition={validation.composition} />}
        {test?.status === "draft" && canAuthor && (
          <Button loading={publishBusy} disabled={!validation?.valid} onClick={() => void publish()}>{can("content.review") ? "Publish test" : "Send for review"}</Button>
        )}
        {test?.status === "in_review" && can("content.review") && <Button loading={publishBusy} onClick={() => void publish()}>Publish test</Button>}
        {test?.status === "published" && canAuthor && (
          <Button variant="secondary" loading={publishing.busy} onClick={() => void publishing.makeChanges(test).then(() => notify.info("Editing a copy", "Publish it to replace the current test."))}>Make changes</Button>
        )}
      </header>

      {!test ? (
        <EmptyState
          icon="clipboardCheck"
          title={`No ${title.toLowerCase()} yet`}
          description={kind === "final" ? "Multiple-choice questions and coding assessments for the course. Passing it earns the certificate." : "Multiple-choice questions for the topic or module assessment."}
          action={canAuthor ? <Button loading={publishing.busy} onClick={() => void publishing.create(`${kind === "final" ? course?.title ?? "Course" : place?.topic.title ?? "Topic"} · ${title}`).catch((error) => notify.apiError(error, "Could not create the test"))}>Create {title.toLowerCase()}</Button> : undefined}
        />
      ) : (
        <div className="space-y-5">
          {publishError && <Alert tone="error">{publishError}</Alert>}
          {validation && !validation.valid && editable && (
            <Alert tone="warning" title="Before it can be published">{validation.issues.map((issue) => issue.message).join(". ")}.</Alert>
          )}
          <TestSettingsBar test={test} editable={editable} />
          <div className="grid items-start gap-5 lg:grid-cols-[360px_minmax(0,1fr)]">
            <section className="space-y-3">
              <h2 className="text-xs font-extrabold uppercase tracking-[0.08em] text-slate-500">Questions · {entries.length}</h2>
              <QuestionList
                test={test}
                selectedId={editing?.questionId ?? null}
                editable={editable}
                onSelect={openQuestion}
                onRemove={(entry) => void questions.removeFromPaper(entry.sectionIndex, entry.slotIndex).catch((error) => notify.apiError(error, "Could not remove the question"))}
              />
              {editable && (
                <div className="space-y-2">
                  <div className="grid grid-cols-2 gap-2">
                    <Button variant="secondary" icon="plus" onClick={() => setEditing(emptyMcq())}>Multiple choice</Button>
                    <Button variant="secondary" icon="terminal" onClick={() => navigate(`${base}/tests/${test.test_id}/programs/new?back=${encodeURIComponent(location.pathname)}`)}>Program</Button>
                  </div>
                  <Button
                    variant="secondary"
                    icon="fileSpreadsheet"
                    fullWidth
                    onClick={() => setShowImportModal(true)}
                    className="border-emerald-300 bg-emerald-50/60 font-bold text-emerald-800 hover:bg-emerald-100 hover:text-emerald-950"
                  >
                    Import from Excel
                  </Button>
                </div>
              )}
            </section>
            {editing ? (
              <McqEditor
                key={editing.questionId ?? "new"}
                initial={editing}
                number={editing.questionId ? entries.findIndex((entry) => entry.questionId === editing.questionId) + 1 : entries.length + 1}
                onCancel={() => setEditing(null)}
                onSave={async (draft) => {
                  await questions.saveMcq(draft);
                  notify.success(draft.questionId ? "Question saved" : "Question added");
                  setEditing(draft.questionId ? null : emptyMcq());
                }}
              />
            ) : (
              <div className="flex min-h-64 flex-col items-center justify-center gap-2 rounded-2xl border-2 border-dashed border-slate-300 p-8 text-center">
                <Icon name="helpCircle" size={26} className="text-slate-400" />
                <p className="font-semibold text-slate-700">{editable ? "Add a question, or pick one to edit it." : "Pick a question to read it."}</p>
                <p className="text-sm text-slate-500">Programs open on their own page, with their test cases.</p>
              </div>
            )}
          </div>
        </div>
      )}
      {showImportModal && test && (
        <ImportExcelModal
          existingQuestions={[]}
          onClose={() => setShowImportModal(false)}
          onImport={async (drafts, onProgress) => {
            const created = await questions.importMcqs(drafts, onProgress);
            notify.success(
              `Imported ${created.length} question${created.length === 1 ? "" : "s"} from Excel!`,
              "Questions are saved to this test as draft."
            );
          }}
        />
      )}
    </>
  );
}
