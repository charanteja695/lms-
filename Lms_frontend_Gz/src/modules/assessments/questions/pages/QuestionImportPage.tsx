import { useState } from "react";
import { Link } from "react-router-dom";

import { useNotify } from "@/core/hooks/useNotify";
import { useImportQuestionsMutation, type BulkImportResult } from "@/modules/assessments/questions/api/questionsApi";
import { Alert, Badge, Button, Card, DataTable, FileDropzone, PageHeader, type Column } from "@/shared/ui";

type Row = BulkImportResult["results"][number];

const COLUMNS: Column<Row>[] = [
  { key: "row", header: "Row", render: (r) => r.index + 1 },
  { key: "status", header: "Result", render: (r) => (r.question_id ? <Badge tone="green">Imported</Badge> : <Badge tone="red">Not imported</Badge>) },
  {
    key: "detail",
    header: "Details",
    render: (r) =>
      r.question_id ? (
        <Link to={`/questions/${r.question_id}`} className="text-brand-700 hover:underline">Open draft</Link>
      ) : (
        <span className="text-sm text-slate-600">{r.details.map((d) => [d.field, d.message].filter(Boolean).join(": ")).join("; ") || r.error}</span>
      ),
  },
];

/** A file shaped like the API's question body is read here and sent as one import; the server checks every row. */
async function readQuestions(file: File): Promise<unknown[]> {
  const parsed: unknown = JSON.parse(await file.text());
  const list = Array.isArray(parsed) ? parsed : (parsed as { questions?: unknown }).questions;
  if (!Array.isArray(list) || list.length === 0) throw new Error("The file needs a list of questions.");
  return list;
}

export function QuestionImportPage() {
  const notify = useNotify();
  const [file, setFile] = useState<File | null>(null);
  const [problem, setProblem] = useState<string | null>(null);
  const [result, setResult] = useState<BulkImportResult | null>(null);
  const [run, { isLoading }] = useImportQuestionsMutation();

  const submit = async () => {
    if (!file) return;
    setProblem(null);
    try {
      const questions = await readQuestions(file);
      const outcome = await run({ questions, key: crypto.randomUUID() }).unwrap();
      setResult(outcome);
      notify.success(`${outcome.created} of ${outcome.created + outcome.failed} questions imported`);
    } catch (error) {
      if (error instanceof Error) setProblem(error.message === "Unexpected end of JSON input" ? "That file is not valid JSON." : error.message);
      else notify.apiError(error);
    }
  };

  return (
    <>
      <PageHeader title="Import questions" description="Add many questions at once. Each one arrives as a draft for review." backTo="/questions" backLabel="Question bank" />
      <Card className="mb-4">
        <div className="space-y-4">
          <p className="text-sm text-slate-600">
            Upload a <span className="font-medium">.json</span> file holding a list of questions, each written the same way as the API&apos;s{" "}
            <span className="font-mono text-xs">POST /questions</span> body (type, text, body, answer key, marks…). Up to 500 per file.
          </p>
          <FileDropzone file={file} onFileChange={(f) => { setFile(f); setResult(null); setProblem(null); }} accept=".json,application/json" maxBytes={5 * 1024 * 1024} hint="JSON, up to 5 MB" />
          {problem && <Alert tone="error" title="Can't read this file">{problem}</Alert>}
          <div className="flex justify-end">
            <Button icon="upload" loading={isLoading} disabled={!file} onClick={() => void submit()}>Import</Button>
          </div>
        </div>
      </Card>
      {result && (
        <Card title="Results" description={`${result.created} imported · ${result.failed} not imported`} bodyClassName="p-0">
          <DataTable columns={COLUMNS} rows={result.results} rowKey={(r) => String(r.index)} />
        </Card>
      )}
    </>
  );
}
