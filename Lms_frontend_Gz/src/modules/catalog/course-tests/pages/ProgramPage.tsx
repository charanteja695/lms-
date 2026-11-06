import { useState } from "react";
import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom";

import { toApiError } from "@/core/lib/apiError";
import { useNotify } from "@/core/hooks/useNotify";
import { safeInternalPath } from "@/core/lib/safePath";
import { useGetTestQuery } from "@/modules/assessments/tests/api/testsApi";
import { CaseList } from "@/modules/catalog/course-tests/components/CaseList";
import { ProgramSummary } from "@/modules/catalog/course-tests/components/ProgramSummary";
import { type ProgramDraft, useProgramSaving } from "@/modules/catalog/course-tests/hooks/useProgramSaving";
import { useTestQuestions } from "@/modules/catalog/course-tests/hooks/useTestQuestions";
import { useListLanguagesQuery } from "@/modules/code-execution/languages/api/languagesApi";
import { Alert, Button, Field, Icon, Input, PageLoader, Select, Textarea } from "@/shared/ui";

const DIFFICULTY = [
  { value: "easy", label: "Easy" },
  { value: "medium", label: "Medium" },
  { value: "hard", label: "Hard" },
];
const TIME_LIMITS = [1000, 2000, 5000].map((ms) => ({ value: String(ms), label: `${ms / 1000} second${ms === 1000 ? "" : "s"}` }));

/** A program question: what to build, the languages allowed, and the test cases that judge it. */
export function ProgramPage() {
  const { courseId = "", versionId = "", testId = "", questionId } = useParams();
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const notify = useNotify();
  const back = safeInternalPath(params.get("back")) ?? `/courses/${courseId}/versions/${versionId}`;
  const { data: test, isLoading } = useGetTestQuery(testId, { skip: !testId });
  const { data: languages = [] } = useListLanguagesQuery();
  const questions = useTestQuestions(test);
  const saveProgram = useProgramSaving(questions);
  const [draft, setDraft] = useState<ProgramDraft | null>(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (isLoading || !test) return <PageLoader />;
  const isFinal = test.kind === "final";
  const form: ProgramDraft = draft ?? {
    title: "", difficulty: isFinal ? "hard" : "easy", marks: isFinal ? 20 : 4, timeLimitMs: 2000, statement: "", inputFormat: "", outputFormat: "", constraints: "",
    languages: [], samples: [{ input: "", expected: "" }], hidden: [{ input: "", expected: "" }], allOrNothing: isFinal,
  };
  const set = (changes: Partial<ProgramDraft>) => setDraft({ ...form, ...changes });
  const codeLanguages = languages.filter((language) => language.kind !== "sql");
  const ready = form.title.trim().length >= 3 && form.statement.trim() && form.samples.length > 0 && form.hidden.length > 0 && [...form.samples, ...form.hidden].every((c) => c.expected.trim());

  const save = async () => {
    setSaving(true);
    setError(null);
    try {
      await saveProgram(form);
      notify.success("Program added", "Learners write code that must pass its test cases.");
      navigate(back);
    } catch (caught) {
      const apiError = toApiError(caught);
      setError(apiError.details.length ? apiError.details.map((detail) => detail.message).join(". ") : apiError.message);
    } finally {
      setSaving(false);
    }
  };

  return (
    <>
      <header className="mb-5 flex flex-wrap items-center gap-3">
        <Link to={back} aria-label="Back to the test" className="flex h-10 w-10 items-center justify-center rounded-xl bg-white text-slate-600 shadow-card ring-1 ring-slate-200/60 hover:text-navy-950">
          <Icon name="chevronLeft" size={18} />
        </Link>
        <div className="min-w-0 flex-1">
          <p className="truncate text-[13px] font-semibold text-brand-700">{test.title}</p>
          <h1 className="text-2xl font-extrabold tracking-tight text-navy-950">{questionId ? "Program" : "Add a program"}</h1>
        </div>
        {!questionId && <Button loading={saving} disabled={!ready} onClick={() => void save()}>Save program</Button>}
      </header>

      {questionId ? (
        <ProgramSummary questionId={questionId} />
      ) : (
        <div className="grid items-start gap-5 xl:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
          <div className="space-y-5">
            {error && <Alert tone="error">{error}</Alert>}
            <section className="grid gap-4 rounded-2xl bg-white p-5 shadow-card ring-1 ring-slate-200/60 sm:grid-cols-3">
              <Field label="Title" required className="sm:col-span-3">
                {(props) => <Input {...props} value={form.title} maxLength={200} placeholder="e.g. Library fine calculator" onChange={(event) => set({ title: event.target.value })} />}
              </Field>
              <Field label="Difficulty">{(props) => <Select {...props} options={DIFFICULTY} value={form.difficulty} onChange={(event) => set({ difficulty: event.target.value as ProgramDraft["difficulty"] })} />}</Field>
              <Field label="Marks">{(props) => <Input {...props} type="number" min={1} value={form.marks} onChange={(event) => set({ marks: Number(event.target.value) || 1 })} />}</Field>
              <Field label="Time per run">{(props) => <Select {...props} options={TIME_LIMITS} value={String(form.timeLimitMs)} onChange={(event) => set({ timeLimitMs: Number(event.target.value) })} />}</Field>
            </section>
            <section className="space-y-4 rounded-2xl bg-white p-5 shadow-card ring-1 ring-slate-200/60">
              <Field label="Problem statement" required>{(props) => <Textarea {...props} rows={6} value={form.statement} placeholder="What the program must do, with an example." onChange={(event) => set({ statement: event.target.value })} />}</Field>
              <div className="grid gap-4 sm:grid-cols-2">
                <Field label="Input format">{(props) => <Textarea {...props} rows={3} value={form.inputFormat} onChange={(event) => set({ inputFormat: event.target.value })} />}</Field>
                <Field label="Output format">{(props) => <Textarea {...props} rows={3} value={form.outputFormat} onChange={(event) => set({ outputFormat: event.target.value })} />}</Field>
              </div>
              <Field label="Constraints">{(props) => <Input {...props} value={form.constraints} placeholder="e.g. 1 ≤ n ≤ 100000" onChange={(event) => set({ constraints: event.target.value })} />}</Field>
              <fieldset className="space-y-2">
                <legend className="text-sm font-semibold text-slate-800">Languages learners may use <span className="font-normal text-slate-500">· none chosen: every language</span></legend>
                <div className="flex flex-wrap gap-2">
                  {codeLanguages.map((language) => {
                    const on = form.languages.includes(language.code);
                    return (
                      <button key={language.code} type="button" aria-pressed={on} onClick={() => set({ languages: on ? form.languages.filter((code) => code !== language.code) : [...form.languages, language.code] })}
                        className={on ? "h-10 rounded-full bg-brand-700 px-4 text-sm font-bold text-white" : "h-10 rounded-full px-4 text-sm font-bold text-slate-700 ring-1 ring-slate-300 hover:bg-slate-50"}>
                        {language.name}
                      </button>
                    );
                  })}
                </div>
              </fieldset>
            </section>
          </div>
          <div className="space-y-5">
            <label className="flex cursor-pointer gap-3 rounded-2xl bg-white p-5 shadow-card ring-1 ring-slate-200/60">
              <input type="checkbox" className="mt-1 h-5 w-5" checked={form.allOrNothing} onChange={(event) => set({ allOrNothing: event.target.checked })} />
              <span>
                <span className="block text-[15px] font-bold text-navy-950">Full marks only when every test case passes</span>
                <span className="block text-[13px] text-slate-600">Hackathon rule: 9 of 10 cases scores 0. Off: marks for each case passed (good for topic tests).</span>
              </span>
            </label>
            <CaseList title="Sample cases" hint="Learners see these and can run them." cases={form.samples} onChange={(samples) => set({ samples })} />
            <CaseList title="Hidden cases" hint="Learners never see these. Cover the edge cases." cases={form.hidden} onChange={(hidden) => set({ hidden })} />
          </div>
        </div>
      )}
    </>
  );
}
