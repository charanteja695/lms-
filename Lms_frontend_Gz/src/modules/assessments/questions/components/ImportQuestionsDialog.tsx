// src/modules/assessments/questions/components/ImportQuestionsDialog.tsx
import { useState } from "react";
import { Modal, Button, Alert, Card, DataTable, Badge, FileDropzone } from "@/shared/ui";
import { useImportQuestionsMutation, type BulkImportResult } from "@/modules/assessments/questions/api/questionsApi";
import { useNotify } from "@/core/hooks/useNotify";

export interface ImportQuestionsDialogProps {
  open: boolean;
  onClose: () => void;
  /** Called with IDs of created question drafts */
  onImported?: (questionIds: string[]) => void;
}

export function ImportQuestionsDialog({ open, onClose, onImported }: ImportQuestionsDialogProps) {
  const notify = useNotify();
  const [file, setFile] = useState<File | null>(null);
  const [problem, setProblem] = useState<string | null>(null);
  const [result, setResult] = useState<BulkImportResult | null>(null);
  const [run, { isLoading }] = useImportQuestionsMutation();

  const readQuestions = async (file: File): Promise<unknown[]> => {
    const parsed = JSON.parse(await file.text());
    const list = Array.isArray(parsed) ? parsed : (parsed as { questions?: unknown }).questions;
    if (!Array.isArray(list) || list.length === 0) throw new Error("The file needs a list of questions.");
    return list;
  };

  const submit = async () => {
    if (!file) return;
    setProblem(null);
    try {
      const questions = await readQuestions(file);
      const outcome = await run({ questions, key: crypto.randomUUID() }).unwrap();
      setResult(outcome);
      const ids = outcome.results.filter((r) => !!r.question_id).map((r) => r.question_id as string);
      onImported?.(ids);
      notify.success(`${outcome.created} of ${outcome.created + outcome.failed} questions imported`);
    } catch (e) {
      if (e instanceof Error) {
        setProblem(e.message === "Unexpected end of JSON input" ? "That file is not valid JSON." : e.message);
      } else {
        notify.apiError(e);
      }
    }
  };
  const footer = (
    <>
      <Button variant="secondary" onClick={onClose}>Cancel</Button>
      <Button icon="upload" loading={isLoading} disabled={!file} onClick={submit}>Import</Button>
    </>
  );
  return (
    <Modal open={open} onClose={onClose} title="Import questions" size="lg" footer={footer}>
      <p className="text-sm text-slate-600">
        Upload a <span className="font-medium">.json</span> file containing a list of questions in the same shape the API expects (POST /questions). Max 5 MB.
      </p>
      <FileDropzone
        file={file}
        onFileChange={(f) => {
          setFile(f);
          setResult(null);
          setProblem(null);
        }}
        accept=".json,application/json"
        maxBytes={5 * 1024 * 1024}
        hint="JSON, up to 5 MB"
      />
      {problem && <Alert tone="error" title="Can’t read this file">{problem}</Alert>}
      {result && (
        <Card title="Results" description={`${result.created} imported, ${result.failed} failed`} bodyClassName="p-0">
          <DataTable
            columns={[
              { key: "row", header: "Row", render: (r) => r.index + 1 },
              {
                key: "status",
                header: "Result",
                render: (r) => r.question_id ? <Badge tone="green">Imported</Badge> : <Badge tone="red">Not imported</Badge>,
              },
              {
                key: "detail",
                header: "Details",
                render: (r) =>
                  r.question_id ? (
                    <a href={`/questions/${r.question_id}`} className="text-brand-700 hover:underline">Open draft</a>
                  ) : (
                    <span className="text-sm text-slate-600">
                      {r.details.map((d) => [d.field, d.message].filter(Boolean).join(": ")).join("; ") || r.error}
                    </span>
                  ),
              },
            ]}
            rows={result.results}
            rowKey={(r) => String(r.index)}
          />
        </Card>
      )}
    </Modal>
  );
}
