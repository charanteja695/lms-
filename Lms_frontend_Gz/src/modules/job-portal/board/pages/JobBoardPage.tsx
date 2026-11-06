import { useEffect, useState } from "react";
import { Navigate, useNavigate, useSearchParams } from "react-router-dom";

import { useListParams } from "@/core/hooks/useListParams";
import { useGetJobPreferencesQuery, useListRecommendationsQuery, useSearchJobsQuery } from "@/modules/job-portal/board/api/boardApi";
import { BoardFilters } from "@/modules/job-portal/board/components/BoardFilters";
import { JobListItem } from "@/modules/job-portal/board/components/JobListItem";
import { PreferencesDialog } from "@/modules/job-portal/board/components/PreferencesDialog";
import type { BoardFilters as Filters } from "@/modules/job-portal/board/types";
import { JobTabs } from "@/modules/job-portal/common/components/JobTabs";
import { useJobRights } from "@/modules/job-portal/common/hooks/useJobRights";
import { Alert, Button, Card, EmptyState, PageHeader, Pagination, Spinner, Tabs } from "@/shared/ui";

type Tab = "recommended" | "eligible" | "search";

/** Jobs as a list and the chosen job beside it, applied to in place. On a phone a job opens on its own page. */
export function JobBoardPage() {
  const navigate = useNavigate();
  const rights = useJobRights();

  if (!rights.isStudent) {
    return <Navigate to={rights.isSuperAdmin || rights.isAdmin ? "/jobs/employer" : "/jobs/institution"} replace />;
  }

  const [search] = useSearchParams();
  const [tab, setTab] = useState<Tab>("recommended");
  const [editingPrefs, setEditingPrefs] = useState(false);
  const { params, update, reset } = useListParams<Record<keyof Filters, string | boolean | undefined>>({ page: 1, per_page: 20 });
  const apiParams = params as Filters & { page: number; per_page: number };
  const all = useSearchJobsQuery(apiParams, { skip: tab !== "search" });
  const eligible = useSearchJobsQuery({ ...apiParams, eligible_only: true }, { skip: tab !== "eligible" });
  const recommended = useListRecommendationsQuery({ per_page: 20 }, { skip: tab !== "recommended" });
  const { data: preferences } = useGetJobPreferencesQuery();

  const current = tab === "search" ? all : tab === "eligible" ? eligible : recommended;
  const jobs = current.data?.items ?? [];
  const selectedId = search.get("job") ?? jobs[0]?.job_id ?? "";
  const activeCount = Object.entries(apiParams).filter(([key, value]) => !["page", "per_page"].includes(key) && value !== undefined && value !== "").length;

  // nothing to recommend yet: show every job instead of an empty page
  useEffect(() => {
    if (tab === "recommended" && recommended.isSuccess && recommended.data.items.length === 0) setTab("search");
  }, [tab, recommended.isSuccess, recommended.data]);

  const pick = (jobId: string) => {
    // Always navigate to the dedicated job detail page
    navigate(`/jobs/board/${jobId}`);
  };

  return (
    <>
      <PageHeader
        title="Jobs"
        description="Openings from verified companies. Your match and eligibility are worked out from your verified skills."
        actions={
          <div className="flex items-center gap-2">
            <Button variant="secondary" icon="filter" disabled={!preferences} onClick={() => setEditingPrefs(true)}>
              Job preferences
            </Button>
          </div>
        }
      />
      <JobTabs />
      <div className="mb-4 flex flex-wrap items-center gap-3">
        <Tabs variant="pills" tabs={[{ value: "recommended", label: "Recommended" }, { value: "eligible", label: "Eligible for me" }, { value: "search", label: "All jobs" }]} value={tab} onChange={setTab} />
      </div>
      {tab === "search" && <Card className="mb-4" bodyClassName="p-0"><BoardFilters filters={apiParams} activeCount={activeCount} update={update} reset={reset} /></Card>}
      {tab === "recommended" && preferences && !preferences.open_to_work && (
        <Alert tone="info" className="mb-4" title="You're not open to work">Turn it on in Job preferences to get recommendations.</Alert>
      )}

      {current.isFetching && jobs.length === 0 ? (
        <Spinner />
      ) : current.isError ? (
        <EmptyState icon="alert" title="Could not load jobs" description="Please try again in a moment." />
      ) : jobs.length === 0 ? (
        tab === "eligible" ? (
          <EmptyState
            icon="briefcase"
            title="No eligible jobs right now"
            description="You do not currently meet the CGPA, branch, or course certificate requirements for the open positions. Keep building your skills and coursework to unlock more openings!"
          />
        ) : (
          <EmptyState icon="briefcase" title="No jobs match" description="Try fewer filters, or check back soon — new openings are added often." />
        )
      ) : (
        <div className="grid grid-cols-1 items-start gap-6 lg:grid-cols-[minmax(0,400px)_minmax(0,1fr)] xl:grid-cols-[minmax(0,440px)_minmax(0,1fr)]">
          <div className="min-w-0 space-y-3">
            {jobs.map((job) => (
              <JobListItem
                key={job.job_id}
                job={job}
                selected={job.job_id === selectedId}
                onSelect={() => pick(job.job_id)}
              />
            ))}
            {tab === "search" && (
              <div className="pt-2">
                <Pagination
                  pageContext={all.data?.pageContext}
                  disabled={all.isFetching}
                  onPageChange={(next) => update({ page: next })}
                  onPerPageChange={(next) => update({ per_page: next })}
                />
              </div>
            )}
          </div>

        </div>
      )}
      {editingPrefs && preferences && <PreferencesDialog current={preferences} onClose={() => setEditingPrefs(false)} />}
    </>
  );
}
