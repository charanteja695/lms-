import { useState } from "react";

import { SharePanel } from "@/modules/career/resumes/components/tools/SharePanel";
import { VersionsPanel } from "@/modules/career/resumes/components/tools/VersionsPanel";
import type { Resume, ResumeOptions } from "@/modules/career/resumes/types";
import { Modal, Tabs } from "@/shared/ui";

type Tab = "share" | "versions";

/** Download, share link and saved versions in one pop-up, so the editor keeps a single export button. */
export function ShareDialog({ resume, options, onClose }: { resume: Resume; options: ResumeOptions; onClose: () => void }) {
  const [tab, setTab] = useState<Tab>("share");
  return (
    <Modal open onClose={onClose} title="Download or share" description="A share link always shows a frozen copy, so later edits never change what someone already saw.">
      <div className="space-y-4">
        <Tabs variant="pills" value={tab} onChange={setTab} tabs={[{ value: "share", label: "Download & link" }, { value: "versions", label: "Saved versions" }]} />
        {tab === "share" ? <SharePanel resume={resume} expiryDays={options.share_expiry_days} defaultDays={options.share_default_days} /> : <VersionsPanel resumeId={resume.resume_id} />}
      </div>
    </Modal>
  );
}
