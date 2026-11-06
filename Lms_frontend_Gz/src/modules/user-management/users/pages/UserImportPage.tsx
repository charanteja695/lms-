import { useState } from "react";
import { useNavigate } from "react-router-dom";

import { downloadFile } from "@/core/api/download";
import { useNotify } from "@/core/hooks/useNotify";
import { useCreateImportJobMutation, useImportUsersMutation } from "@/modules/user-management/users/api/usersApi";
import { ImportReport } from "@/modules/user-management/users/components/import/ImportReport";
import type { ImportMode, ImportResult } from "@/modules/user-management/users/types";
import { Alert, Button, Card, Field, FileDropzone, PageHeader, Select } from "@/shared/ui";

const MODES = [
  { value: "all_or_nothing", label: "All or nothing: import only if every row is valid" },
  { value: "skip_invalid", label: "Skip invalid rows: import the valid rows" },
];

/** Files up to 5,000 rows are imported straight away; bigger ones run in the background. */
const DIRECT_IMPORT_MAX_BYTES = 5 * 1024 * 1024;

export function UserImportPage() {
  const navigate = useNavigate();
  const notify = useNotify();
  const [file, setFile] = useState<File | null>(null);
  const [mode, setMode] = useState<ImportMode>("all_or_nothing");
  const [result, setResult] = useState<ImportResult | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [importUsers, { isLoading, originalArgs }] = useImportUsersMutation();
  const [createImportJob, { isLoading: queueing }] = useCreateImportJobMutation();
  const [templateBusy, setTemplateBusy] = useState(false);
  const large = (file?.size ?? 0) > DIRECT_IMPORT_MAX_BYTES;

  const submit = async (dryRun: boolean) => {
    if (!file) return;
    try {
      const response = await importUsers({ file, dryRun, mode }).unwrap();
      setResult(response.import_result);
      setMessage(response.message);
      if (!dryRun && response.import_result.created > 0) notify.success(response.message);
    } catch (error) {
      setResult(null);
      notify.apiError(error, "Import failed");
    }
  };

  const queueInBackground = async () => {
    if (!file) return;
    try {
      const job = await createImportJob({ file, dryRun: false, mode }).unwrap();
      notify.success("Import queued", "You will be emailed when it has finished.");
      navigate(`/downloads/${job.job_id}`);
    } catch (error) {
      notify.apiError(error, "Could not queue the import");
    }
  };

  const downloadTemplate = async () => {
    setTemplateBusy(true);
    try {
      await downloadFile("/users/import/template", {}, "user-import-template.csv");
    } catch (error) {
      notify.apiError(error, "Could not download the template");
    } finally {
      setTemplateBusy(false);
    }
  };

  return (
    <>
      <PageHeader title="Import users" description="Create many users at once from a CSV file." backTo="/users" backLabel="Users" />
      <div className="grid gap-6 lg:grid-cols-3">
        <Card title="1. Prepare the file" className="lg:col-span-1">
          <ol className="list-decimal space-y-2 pl-5 text-sm text-slate-600">
            <li>Download the template. It includes a staff and a student example row.</li>
            <li>Fill one row per person. Required: role, first name, last name; email for everyone except students.</li>
            <li>Students need date of birth, admission number and a guardian if under 18. Staff need phone and employee code.</li>
            <li>Save as CSV (UTF-8). Up to 5,000 rows here, or 50,000 as a background import.</li>
          </ol>
          <Button className="mt-4" variant="secondary" icon="download" loading={templateBusy} onClick={() => void downloadTemplate()}>
            Download template
          </Button>
          <p className="mt-4 text-xs text-slate-500">
            No passwords go in the file. Each person receives an email to set up their account; students without an email address get a
            temporary password in the result.
          </p>
        </Card>

        <Card title="2. Upload and check" className="lg:col-span-2">
          <div className="space-y-4">
            <FileDropzone
              file={file}
              maxBytes={50 * 1024 * 1024}
              hint="CSV up to 50 MB"
              onFileChange={(next) => {
                setFile(next);
                setResult(null);
              }}
            />
            <Field label="Import mode">
              {(props) => <Select {...props} options={MODES} value={mode} onChange={(event) => setMode(event.target.value as ImportMode)} />}
            </Field>
            {large && (
              <Alert tone="info" title="Large file">
                This file is too big to import directly. Queue it as a background import and we will email you the report.
              </Alert>
            )}
            <div className="flex flex-wrap gap-3">
              <Button variant="secondary" disabled={!file || large} loading={isLoading && originalArgs?.dryRun} onClick={() => void submit(true)}>
                Check file
              </Button>
              <Button
                icon="upload"
                disabled={!file || large || (result?.dry_run && result.valid_rows === 0)}
                loading={isLoading && originalArgs?.dryRun === false}
                onClick={() => void submit(false)}
              >
                Import
              </Button>
              <Button variant="secondary" icon="clock" disabled={!file} loading={queueing} onClick={() => void queueInBackground()}>
                Import in the background
              </Button>
            </div>
          </div>
        </Card>
      </div>

      {result && <ImportReport result={result} message={message} onViewUsers={() => navigate("/users")} />}
    </>
  );
}
