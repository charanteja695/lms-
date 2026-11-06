import { useState } from "react";

import { formatDate } from "@/core/lib/format";
import { toOptions } from "@/core/lib/options";
import { JobTabs } from "@/modules/job-portal/common/components/JobTabs";
import { ApplicationStatusBadge } from "@/modules/job-portal/common/components/JobBadges";
import { formatCtc } from "@/modules/job-portal/common/format";
import { APPLICATION_STATUS_LABELS } from "@/modules/job-portal/common/labels";
import type { ApplicationStatus } from "@/modules/job-portal/common/types";
import { useGetInstitutionSummaryQuery, useListPlacementsQuery, useListStudentApplicationsQuery, type StudentApplication } from "@/modules/job-portal/institution/api/institutionApi";
import { Card, DataTable, EmptyState, FilterRow, FilterSelect, PageHeader, Pagination, StatTile, Tabs, type Column } from "@/shared/ui";

const COLUMNS: Column<StudentApplication>[] = [
  { key: "student", header: "Student", render: (a) => <div><p className="font-medium text-slate-900">{a.student.name}</p><p className="text-xs text-slate-500">{a.student.email}</p></div> },
  { key: "job", header: "Job", render: (a) => <div><p>{a.job_title}</p><p className="text-xs text-slate-500">{a.company_name}</p></div> },
  { key: "status", header: "Status", render: (a) => <ApplicationStatusBadge status={a.status} /> },
  { key: "ctc", header: "CTC", hideOnMobile: true, render: (a) => formatCtc(a.ctc, a.currency ?? "INR") ?? "—" },
  { key: "date", header: "Applied", hideOnMobile: true, render: (a) => formatDate(a.applied_at) },
];

/** Institution staff/heads: their students' applications and placements (read only); drives are one click away. */
export function InstitutionPlacementsPage() {
  const [tab, setTab] = useState<"applications" | "placements">("applications");
  const [status, setStatus] = useState<ApplicationStatus | undefined>();
  const [page, setPage] = useState(1);
  const { data: summary } = useGetInstitutionSummaryQuery();
  const applications = useListStudentApplicationsQuery({ status, page, per_page: 20 }, { skip: tab !== "applications" });
  const placements = useListPlacementsQuery({ page, per_page: 20 }, { skip: tab !== "placements" });
  const current = tab === "applications" ? applications : placements;

  return (
    <>
      <PageHeader title="Jobs" description="Your students' job applications and offers." />
      <JobTabs />
      <div className="mb-4 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatTile icon="users" label="Students who applied" value={summary?.students_applied ?? "—"} />
        <StatTile icon="briefcase" label="Applications" value={summary?.applications ?? "—"} />
        <StatTile icon="check" label="Students placed" value={summary?.placed_students ?? "—"} />
        <StatTile icon="building" label="Companies" value={summary?.employers ?? "—"} />
      </div>
      <Tabs tabs={[{ value: "applications", label: "Applications" }, { value: "placements", label: "Placements" }]} value={tab} onChange={(t) => { setTab(t); setPage(1); }} />
      <Card bodyClassName="p-0" className="mt-4">
        {tab === "applications" && (
          <FilterRow>
            <FilterSelect label="Status" value={status} options={toOptions(APPLICATION_STATUS_LABELS)} onChange={(v) => { setStatus(v as ApplicationStatus | undefined); setPage(1); }} />
          </FilterRow>
        )}
        <DataTable columns={COLUMNS} rows={current.data?.items ?? []} rowKey={(a) => a.application_id} loading={current.isFetching} empty={<EmptyState icon="briefcase" title={tab === "applications" ? "No applications yet" : "No placements yet"} description={tab === "applications" ? "Your students' job applications appear here." : "Students who accept an offer appear here."} />} />
        <Pagination pageContext={current.data?.pageContext} disabled={current.isFetching} onPageChange={setPage} onPerPageChange={() => setPage(1)} />
      </Card>
    </>
  );
}
