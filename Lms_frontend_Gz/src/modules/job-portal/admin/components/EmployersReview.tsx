import { useState } from "react";

import { useConfirmAction } from "@/core/hooks/useConfirmAction";
import { useNotify } from "@/core/hooks/useNotify";
import { toOptions } from "@/core/lib/options";
import { EmployerStatusBadge } from "@/modules/job-portal/common/components/JobBadges";
import { EMPLOYER_STATUS_LABELS } from "@/modules/job-portal/common/labels";
import type { EmployerStatus } from "@/modules/job-portal/common/types";
import { useListEmployersForReviewQuery, useReinstateEmployerMutation, useReviewEmployerMutation, useSuspendEmployerMutation } from "@/modules/job-portal/admin/api/jobAdminApi";
import type { Company } from "@/modules/job-portal/employer/types";
import { Button, ConfirmDialog, DataTable, EmptyState, FilterSelect, type Column } from "@/shared/ui";

/** Verify a company (its jobs can then go live), refuse with a note, suspend (pauses its open jobs) or reinstate. */
export function EmployersReview() {
  const notify = useNotify();
  const confirm = useConfirmAction();
  const [status, setStatus] = useState<EmployerStatus | undefined>("pending");
  const { data, isFetching } = useListEmployersForReviewQuery({ status, per_page: 50 });
  const [review] = useReviewEmployerMutation();
  const [suspend] = useSuspendEmployerMutation();
  const [reinstate] = useReinstateEmployerMutation();
  const done = (message: string) => () => notify.success(message);

  const columns: Column<Company>[] = [
    { key: "name", header: "Company", render: (c) => <div><p className="font-medium text-slate-900">{c.company_name}</p><p className="text-xs text-slate-500">{[c.industry, c.website].filter(Boolean).join(" · ")}</p></div> },
    { key: "about", header: "About", hideOnMobile: true, render: (c) => <span className="line-clamp-2 text-slate-600">{c.about}</span> },
    { key: "status", header: "Status", render: (c) => <EmployerStatusBadge status={c.status} /> },
    {
      key: "actions",
      header: "",
      render: (c) => (
        <div className="flex justify-end gap-1">
          {c.status === "pending" && <Button size="sm" onClick={() => void review({ id: c.organization_id, approve: true }).unwrap().then(done("Company verified"), notify.apiError)}>Verify</Button>}
          {c.status === "pending" && (
            <Button size="sm" variant="secondary" onClick={() => confirm.ask({ title: `Refuse ${c.company_name}?`, description: "The note is shown to the company.", confirmLabel: "Refuse", withReason: true }, async (note) => { await review({ id: c.organization_id, approve: false, note: note || "Incomplete profile" }).unwrap().then(done("Refused"), notify.apiError); })}>Refuse</Button>
          )}
          {c.status === "verified" && (
            <Button size="sm" variant="danger" onClick={() => confirm.ask({ title: `Suspend ${c.company_name}?`, description: "Its open jobs are paused.", confirmLabel: "Suspend", withReason: true }, async (note) => { await suspend({ id: c.organization_id, note: note || "Suspended by a careers manager" }).unwrap().then(done("Suspended"), notify.apiError); })}>Suspend</Button>
          )}
          {c.status === "suspended" && <Button size="sm" variant="secondary" onClick={() => void reinstate(c.organization_id).unwrap().then(done("Reinstated"), notify.apiError)}>Reinstate</Button>}
        </div>
      ),
    },
  ];

  return (
    <div className="space-y-3">
      <FilterSelect label="Status" value={status} options={toOptions(EMPLOYER_STATUS_LABELS)} onChange={(v) => setStatus(v as EmployerStatus | undefined)} />
      <DataTable columns={columns} rows={data?.items ?? []} rowKey={(c) => c.organization_id} loading={isFetching} empty={<EmptyState icon="building" title="Nothing to review" description="Companies asking to be verified appear here." />} />
      <ConfirmDialog {...confirm.dialogProps} />
    </div>
  );
}
