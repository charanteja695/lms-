import { useEffect, useState } from "react";
import { useParams, useSearchParams } from "react-router-dom";

import { formatDate } from "@/core/lib/format";
import { JobStatusBadge } from "@/modules/job-portal/common/components/JobBadges";
import { jobMeta } from "@/modules/job-portal/common/format";
import { useGetEmployerJobQuery } from "@/modules/job-portal/employer/api/employerJobsApi";
import { ApplicantsTab } from "@/modules/job-portal/employer/components/job/ApplicantsTab";
import { FunnelTab } from "@/modules/job-portal/employer/components/job/FunnelTab";
import { JobLifecycleActions } from "@/modules/job-portal/employer/components/job/JobLifecycleActions";
import { Alert, Badge, Card, DescriptionList, EmptyState, PageHeader, PageLoader, Tabs } from "@/shared/ui";

type Tab = "overview" | "applicants" | "funnel";

export function EmployerJobPage() {
  const { jobId = "" } = useParams();
  const [searchParams, setSearchParams] = useSearchParams();
  const { data: job, isLoading, isError } = useGetEmployerJobQuery(jobId, { skip: !jobId });
  
  const paramTab = searchParams.get("tab") as Tab | null;
  const [tab, setTab] = useState<Tab>(paramTab || "overview");

  useEffect(() => {
    if (paramTab && (paramTab === "overview" || paramTab === "applicants" || paramTab === "funnel")) {
      setTab(paramTab);
    }
  }, [paramTab]);

  const handleTabChange = (newTab: Tab) => {
    setTab(newTab);
    setSearchParams(newTab === "overview" ? {} : { tab: newTab }, { replace: true });
  };

  if (isLoading) return <PageLoader />;
  if (isError || !job) return <EmptyState icon="alert" title="Job not found" />;
  const hasApplicants = job.status !== "draft" && job.status !== "pending_approval";

  return (
    <>
      <PageHeader
        title={job.title}
        description={
          <span className="flex items-center gap-2">
            <JobStatusBadge status={job.status} /> {jobMeta(job)}
          </span>
        }
        backTo="/jobs/employer"
        backLabel="Jobs"
        actions={<JobLifecycleActions job={job} />}
      />
      {job.review_note && (
        <Alert tone={job.status === "draft" ? "error" : "info"} className="mb-4" title="Reviewer's note">
          {job.review_note}
        </Alert>
      )}
      {job.closed_reason && (
        <Alert tone="info" className="mb-4" title="Closed">
          {job.closed_reason}
        </Alert>
      )}
      <Tabs
        tabs={[
          { value: "overview", label: "Overview" },
          ...(hasApplicants
            ? [
                { value: "applicants" as const, label: `Applicants (${job.applications})` },
                { value: "funnel" as const, label: "Funnel & audit" },
              ]
            : []),
        ]}
        value={tab}
        onChange={handleTabChange}
      />
      <div className="mt-4">
        {tab === "overview" && (
          <div className="grid gap-4 lg:grid-cols-[1fr_20rem]">
            <Card title="Description">
              <p className="whitespace-pre-wrap text-sm text-slate-800">{job.description}</p>
            </Card>
            <Card title="Details">
              <DescriptionList
                columns={1}
                items={[
                  { label: "Openings", value: `${job.placed} placed of ${job.openings}` },
                  { label: "Deadline", value: formatDate(job.deadline_at) },
                  {
                    label: "Required skills",
                    value: (
                      <span className="flex flex-wrap gap-1">
                        {job.required_skills.map((s) => (
                          <Badge key={s}>{s}</Badge>
                        ))}
                      </span>
                    ),
                  },
                  {
                    label: "Visibility",
                    value: job.institution_ids.length
                      ? `${job.institution_ids.length} institution(s) only`
                      : "All students",
                  },
                  { label: "Stages", value: job.steps.map((s) => s.label).join(" → ") },
                ]}
              />
            </Card>
          </div>
        )}
        {tab === "applicants" && <ApplicantsTab jobId={jobId} />}
        {tab === "funnel" && <FunnelTab jobId={jobId} />}
      </div>
    </>
  );
}
