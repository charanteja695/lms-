import { useState } from "react";
import { Link, Navigate } from "react-router-dom";

import { formatDate } from "@/core/lib/format";
import { useListMyApplicationsQuery } from "@/modules/job-portal/applications/api/myApplicationsApi";
import { NextActionBar } from "@/modules/job-portal/applications/components/NextActionBar";
import { ProgressSteps } from "@/modules/job-portal/applications/components/ProgressSteps";
import { CompanyMark } from "@/modules/job-portal/board/components/CompanyMark";
import { ApplicationStatusBadge } from "@/modules/job-portal/common/components/JobBadges";
import { JobTabs } from "@/modules/job-portal/common/components/JobTabs";
import { useJobRights } from "@/modules/job-portal/common/hooks/useJobRights";
import { EmptyState, PageHeader, Pagination, Spinner, Tabs } from "@/shared/ui";

type View = "active" | "closed";

/** Every application as a card: how far it has got, and the one thing to do next (things that need you come first). */
export function MyApplicationsPage() {
  const rights = useJobRights();

  if (!rights.isStudent) {
    return <Navigate to={rights.isSuperAdmin || rights.isAdmin ? "/jobs/employer" : "/jobs/institution"} replace />;
  }

  const [view, setView] = useState<View>("active");
  const [page, setPage] = useState(1);
  const [perPage, setPerPage] = useState(20);
  const { data, isFetching } = useListMyApplicationsQuery({ active: view === "active", page, per_page: perPage });
  const items = [...(data?.items ?? [])].sort((a, b) => Number(Boolean(b.next_action)) - Number(Boolean(a.next_action)));

  return (
    <>
      <PageHeader
        title="Jobs"
        description="Where each application stands, and what you need to do next."
      />
      <JobTabs />
      <div className="mb-4"><Tabs variant="pills" tabs={[{ value: "active", label: "In progress" }, { value: "closed", label: "Closed" }]} value={view} onChange={(v) => { setView(v); setPage(1); }} /></div>
      {isFetching && items.length === 0 ? (
        <Spinner />
      ) : items.length === 0 ? (
        <EmptyState
          icon="briefcase"
          title={view === "active" ? "No applications in progress" : "Nothing closed yet"}
          description={view === "active" ? "Find a job that matches you and apply in one step." : undefined}
          action={view === "active" ? <Link to="/jobs/board" className="inline-flex h-10 items-center rounded-xl bg-brand-700 px-4 text-sm font-bold text-white">Find jobs</Link> : undefined}
        />
      ) : (
        <div className="space-y-3">
          {items.map((application) => (
            <article key={application.application_id} className={application.next_action ? "space-y-4 rounded-2xl bg-white p-4 shadow-card ring-2 ring-accent-400 sm:p-5" : "space-y-4 rounded-2xl bg-white p-4 shadow-card ring-1 ring-slate-200/60 sm:p-5"}>
              <div className="flex flex-wrap items-center gap-3">
                <CompanyMark name={application.company_name} />
                <Link to={`/jobs/applications/${application.application_id}`} className="min-w-[200px] flex-1 hover:underline">
                  <span className="block text-[15px] font-bold text-navy-950">{application.job_title}</span>
                  <span className="block text-[13px] text-slate-500">{application.company_name} · applied {formatDate(application.applied_at)} · resume v{application.resume_version_no}</span>
                </Link>
                <ApplicationStatusBadge status={application.status} />
              </div>
              <ProgressSteps steps={application.progress} />
              <NextActionBar application={application} />
            </article>
          ))}
          <Pagination pageContext={data?.pageContext} disabled={isFetching} onPageChange={setPage} onPerPageChange={(next) => { setPerPage(next); setPage(1); }} />
        </div>
      )}
    </>
  );
}
