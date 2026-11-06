import { useState } from "react";

import { useNotify } from "@/core/hooks/useNotify";
import { formatDate } from "@/core/lib/format";
import { useExportResumeMutation, useShareResumeMutation, useUnshareResumeMutation, type Share } from "@/modules/career/resumes/api/resumeToolsApi";
import type { Resume } from "@/modules/career/resumes/types";
import { Alert, Button, Checkbox, Input, Select } from "@/shared/ui";


/** Downloads (PDF, JSON Resume) and the public link, which is pinned to a snapshot and replaced by a new one. */
export function SharePanel({ resume, expiryDays, defaultDays }: { resume: Resume; expiryDays: number[]; defaultDays: number }) {
  const notify = useNotify();
  const [exportResume, { isLoading: exporting, originalArgs }] = useExportResumeMutation();
  const [share, { isLoading: sharing }] = useShareResumeMutation();
  const [unshare, { isLoading: unsharing }] = useUnshareResumeMutation();
  const [showContact, setShowContact] = useState(false);
  const [expiry, setExpiry] = useState(String(defaultDays));
  const [created, setCreated] = useState<Share | null>(null);
  const link = created ? `${window.location.origin}/resume/${created.token}` : null;

  const download = async (format: "pdf" | "json-resume") => {
    try {
      const url = await exportResume({ resumeId: resume.resume_id, format }).unwrap();
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = `${resume.title}.${format === "pdf" ? "pdf" : "json"}`;
      anchor.click();
      setTimeout(() => URL.revokeObjectURL(url), 10_000);
    } catch (error) {
      notify.apiError(error);
    }
  };

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap gap-2">
        <Button size="sm" icon="download" loading={exporting && originalArgs?.format === "pdf"} onClick={() => void download("pdf")}>PDF</Button>
        <Button size="sm" variant="secondary" icon="download" loading={exporting && originalArgs?.format === "json-resume"} onClick={() => void download("json-resume")}>JSON Resume</Button>
      </div>
      <div className="space-y-2 border-t border-slate-100 pt-3">
        <p className="text-sm font-medium text-slate-700">Public link</p>
        {resume.shared && !created && <p className="text-sm text-slate-600">A link is live{resume.share_expires_at ? ` until ${formatDate(resume.share_expires_at)}` : ""}. Creating a new one replaces it.</p>}
        <Checkbox label="Show my email, phone and location" checked={showContact} onChange={(e) => setShowContact(e.target.checked)} />
        <Select aria-label="Expiry" value={expiry} options={[...new Set([...expiryDays, defaultDays])].sort((a, b) => a - b).map((days) => ({ value: String(days), label: `Link works for ${days} days` }))} onChange={(e) => setExpiry(e.target.value)} />
        <div className="flex flex-wrap gap-2">
          <Button
            size="sm"
            loading={sharing}
            onClick={async () => {
              try {
                setCreated(await share({ resumeId: resume.resume_id, show_contact: showContact, expires_in_days: Number(expiry) }).unwrap());
              } catch (error) {
                notify.apiError(error);
              }
            }}
          >
            {resume.shared ? "Create a new link" : "Create link"}
          </Button>
          {resume.shared && (
            <Button size="sm" variant="ghost" loading={unsharing} onClick={() => void unshare(resume.resume_id).unwrap().then(() => setCreated(null), notify.apiError)}>
              Turn off sharing
            </Button>
          )}
        </div>
        {link && (
          <Alert tone="success" title={`Shared v${created?.version_no}`}>
            <Input aria-label="Share link" readOnly value={link} onFocus={(e) => e.target.select()} />
          </Alert>
        )}
      </div>
    </div>
  );
}
