import { useState } from "react";

import { useNotify } from "@/core/hooks/useNotify";
import { useBulkCreateTestCasesMutation } from "@/modules/code-execution/problems/api/problemsApi";
import type { TestCaseCreateBody } from "@/modules/code-execution/problems/types";
import { Alert, Button, FileDropzone, Modal } from "@/shared/ui";

/** Many test cases at once from a .json list of {input, expected, is_sample?, weight?, explanation?}. The server checks each. */
export function TestCaseImportDialog({ problemId, onClose }: { problemId: string; onClose: () => void }) {
  const notify = useNotify();
  const [file, setFile] = useState<File | null>(null);
  const [problem, setProblem] = useState<string | null>(null);
  const [importCases, { isLoading }] = useBulkCreateTestCasesMutation();

  const submit = async () => {
    if (!file) return;
    try {
      const parsed: unknown = JSON.parse(await file.text());
      const list = (Array.isArray(parsed) ? parsed : (parsed as { test_cases?: unknown }).test_cases) as TestCaseCreateBody[] | undefined;
      if (!Array.isArray(list) || list.length === 0) throw new Error("The file needs a list of test cases.");
      if (list.length > 200) throw new Error("Up to 200 test cases per file.");
      await importCases({ problemId, testCases: list }).unwrap();
      notify.success(`${list.length} test cases added`);
      onClose();
    } catch (error) {
      if (error instanceof SyntaxError) setProblem("That file is not valid JSON.");
      else if (error instanceof Error) setProblem(error.message);
      else notify.apiError(error);
    }
  };

  return (
    <Modal
      open
      onClose={onClose}
      title="Import test cases"
      description="Each entry: input, expected, and optionally is_sample, weight, explanation. All are added, or none if one is invalid."
      footer={<><Button variant="secondary" onClick={onClose}>Cancel</Button><Button icon="upload" loading={isLoading} disabled={!file} onClick={() => void submit()}>Import</Button></>}
    >
      <div className="space-y-3">
        <FileDropzone file={file} onFileChange={(f) => { setFile(f); setProblem(null); }} accept=".json,application/json" maxBytes={5 * 1024 * 1024} hint="JSON, up to 200 cases" />
        {problem && <Alert tone="error" title="Can't import this file">{problem}</Alert>}
      </div>
    </Modal>
  );
}
