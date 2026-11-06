import { useState } from "react";

import { useConfirmAction } from "@/core/hooks/useConfirmAction";
import { useNotify } from "@/core/hooks/useNotify";
import { formatDateTime } from "@/core/lib/format";
import { useListResumeVersionsQuery, useRestoreResumeVersionMutation, useSaveResumeVersionMutation } from "@/modules/career/resumes/api/resumesApi";
import { VersionPreviewDialog } from "@/modules/career/resumes/components/tools/VersionPreviewDialog";
import { Button, ConfirmDialog, Input } from "@/shared/ui";

/** Frozen snapshots of the resume; restoring one saves the current draft as a version first (server-side). */
export function VersionsPanel({ resumeId }: { resumeId: string }) {
  const notify = useNotify();
  const confirm = useConfirmAction();
  const { data: versions = [] } = useListResumeVersionsQuery(resumeId);
  const [save, { isLoading: saving }] = useSaveResumeVersionMutation();
  const [restore] = useRestoreResumeVersionMutation();
  const [label, setLabel] = useState("");
  const [viewing, setViewing] = useState<number | null>(null);

  return (
    <div className="space-y-3">
      <div className="flex gap-2">
        <Input aria-label="Version label" placeholder="Label (e.g. Sent to Acme)" maxLength={120} value={label} onChange={(e) => setLabel(e.target.value)} />
        <Button
          size="sm"
          loading={saving}
          onClick={async () => {
            try {
              await save({ resumeId, label: label.trim() || undefined }).unwrap();
              setLabel("");
              notify.success("Version saved");
            } catch (error) {
              notify.apiError(error);
            }
          }}
        >
          Save version
        </Button>
      </div>
      {versions.length === 0 ? (
        <p className="text-sm text-slate-500">No versions yet. Save one before you send this resume anywhere.</p>
      ) : (
        <ul className="divide-y divide-slate-100 text-sm">
          {versions.map((version) => (
            <li key={version.version_no} className="flex items-center justify-between gap-2 py-2">
              <div className="min-w-0">
                <p className="truncate text-slate-800">v{version.version_no}{version.label ? ` · ${version.label}` : ""}</p>
                <p className="text-xs text-slate-500">{formatDateTime(version.created_at)}{version.ats_score != null ? ` · ATS ${version.ats_score}` : ""}</p>
              </div>
              <div className="flex shrink-0 gap-1">
                <Button variant="ghost" size="sm" onClick={() => setViewing(version.version_no)}>View</Button>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() =>
                    confirm.ask({ title: `Restore v${version.version_no}?`, description: "Your current draft is saved as a version first, so nothing is lost.", confirmLabel: "Restore", tone: "primary" }, async () => {
                      try {
                        await restore({ resumeId, versionNo: version.version_no }).unwrap();
                        notify.success("Version restored");
                      } catch (error) {
                        notify.apiError(error);
                      }
                    })
                  }
                >
                  Restore
                </Button>
              </div>
            </li>
          ))}
        </ul>
      )}
      {viewing != null && <VersionPreviewDialog resumeId={resumeId} versionNo={viewing} onClose={() => setViewing(null)} />}
      <ConfirmDialog {...confirm.dialogProps} />
    </div>
  );
}
