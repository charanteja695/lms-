import { useState } from "react";

import { JobTabs } from "@/modules/job-portal/common/components/JobTabs";
import { EmployersReview } from "@/modules/job-portal/admin/components/EmployersReview";
import { JobsReview } from "@/modules/job-portal/admin/components/JobsReview";
import { PageHeader, Tabs } from "@/shared/ui";

export function JobAdminPage() {
  const [tab, setTab] = useState<"jobs" | "employers">("jobs");
  return (
    <>
      <PageHeader title="Job Approvals" description="Review and approve company job postings before students can view and apply." />
      <JobTabs />
      <div className="mt-4">
        <Tabs tabs={[{ value: "jobs", label: "Jobs to approve" }, { value: "employers", label: "Companies" }]} value={tab} onChange={setTab} />
        <div className="mt-4">{tab === "jobs" ? <JobsReview /> : <EmployersReview />}</div>
      </div>
    </>
  );
}
