import type { CaseDraft } from "@/modules/catalog/course-tests/hooks/useProgramSaving";
import { Button, Icon, Textarea } from "@/shared/ui";

/** Test cases as input → expected output pairs. Samples are shown to learners; hidden ones never are. */
export function CaseList({ title, hint, cases, onChange }: { title: string; hint: string; cases: CaseDraft[]; onChange: (cases: CaseDraft[]) => void }) {
  const update = (index: number, changes: Partial<CaseDraft>) => onChange(cases.map((c, i) => (i === index ? { ...c, ...changes } : c)));
  return (
    <section className="space-y-3 rounded-2xl bg-white p-5 shadow-card ring-1 ring-slate-200/60">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <h3 className="text-[15px] font-bold text-navy-950">{title} · {cases.length}</h3>
          <p className="text-[13px] text-slate-500">{hint}</p>
        </div>
        <Button variant="secondary" size="sm" icon="plus" onClick={() => onChange([...cases, { input: "", expected: "" }])}>Add case</Button>
      </div>
      {cases.map((testCase, index) => (
        <div key={index} className="grid gap-2 rounded-xl bg-slate-50 p-3 sm:grid-cols-[minmax(0,1fr)_minmax(0,1fr)_auto]">
          <Textarea aria-label={`${title} ${index + 1} input`} placeholder="Input (stdin)" rows={2} value={testCase.input} onChange={(event) => update(index, { input: event.target.value })} className="font-mono text-[13px]" />
          <Textarea aria-label={`${title} ${index + 1} expected output`} placeholder="Expected output" rows={2} value={testCase.expected} onChange={(event) => update(index, { expected: event.target.value })} className="font-mono text-[13px]" />
          <Button variant="ghost" size="icon" onClick={() => onChange(cases.filter((_, i) => i !== index))} aria-label={`Remove ${title.toLowerCase()} ${index + 1}`}>
            <Icon name="trash" size={16} />
          </Button>
        </div>
      ))}
    </section>
  );
}
