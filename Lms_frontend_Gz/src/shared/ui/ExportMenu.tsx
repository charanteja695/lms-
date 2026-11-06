import { useState } from "react";
import { useNavigate } from "react-router-dom";

import { downloadFile } from "@/core/api/download";
import { useNotify } from "@/core/hooks/useNotify";
import type { Job } from "@/modules/user-management/downloads/types";
import { Button } from "./Button";
import { Menu } from "./Menu";

/** "Download now" streams the CSV; "Email me when ready" queues a background job for very large exports. */
export function ExportMenu({ path, filters, fileName, createJob }: {
  path: string;
  filters: Record<string, unknown>;
  fileName: string;
  createJob: () => Promise<Job>;
}) {
  const notify = useNotify();
  const navigate = useNavigate();
  const [busy, setBusy] = useState(false);

  const downloadNow = async () => {
    setBusy(true);
    try {
      await downloadFile(path, filters, fileName);
    } catch (error) {
      notify.apiError(error, "Export failed");
    } finally {
      setBusy(false);
    }
  };

  const queue = async () => {
    setBusy(true);
    try {
      const job = await createJob();
      notify.success("Export queued", "We'll email you when it's ready. You can also follow it under Downloads.");
      navigate(`/downloads?highlight=${job.job_id}`);
    } catch (error) {
      notify.apiError(error, "Export not queued");
    } finally {
      setBusy(false);
    }
  };

  return (
    <Menu
      trigger={
        <Button variant="secondary" icon="download" loading={busy}>
          Export
        </Button>
      }
      items={[
        { label: "Download CSV now", icon: "download", onSelect: () => void downloadNow() },
        { label: "Email me when ready (large)", icon: "mail", onSelect: () => void queue() },
      ]}
    />
  );
}
