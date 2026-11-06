import { useState } from "react";
import { useNavigate } from "react-router-dom";

import { useListParams } from "@/core/hooks/useListParams";
import { ProctoringTabs } from "@/modules/proctoring/common/components/ProctoringTabs";
import { useListMonitorSessionsQuery } from "@/modules/proctoring/monitor/api/monitorApi";
import { MonitorFilters } from "@/modules/proctoring/monitor/components/list/MonitorFilters";
import { useMonitorColumns } from "@/modules/proctoring/monitor/components/list/useMonitorColumns";
import { StudentProgressDashboard } from "@/modules/proctoring/monitor/components/StudentProgressDashboard";
import type { MonitorFilters as Filters } from "@/modules/proctoring/monitor/types";
import { Button, Card, DataTable, EmptyState, PageHeader, Pagination, Tabs } from "@/shared/ui";

type ViewMode = "progress" | "live_exams";

/** Combined Progress of Student dashboard and live exam proctoring monitor. */
export function MonitorListPage() {
  const navigate = useNavigate();
  const [activeView, setActiveView] = useState<ViewMode>("progress");

  // State for live exams
  const { params, update, reset } = useListParams<Record<keyof Filters, string | boolean | undefined>>({ page: 1, per_page: 50 });
  const apiParams = params as Filters & { page: number; per_page: number };
  const { data, isFetching, isError, refetch } = useListMonitorSessionsQuery(apiParams);
  const columns = useMonitorColumns();
  const activeCount = Object.entries(apiParams).filter(([key, value]) => !["page", "per_page"].includes(key) && value !== undefined && value !== "").length;

  const viewTabs: Array<{ value: ViewMode; label: string }> = [
    { value: "progress", label: "Student Progress Dashboard" },
    { value: "live_exams", label: "Live Exam Proctoring" },
  ];

  return (
    <>
      <PageHeader
        title="Progress of Student"
        description="Comprehensive tracking of student learning progress, module completions, assessment attempts, and live examinations."
      />

      <ProctoringTabs />

      {/* View Switcher: Student Progress vs Live Exam Proctoring */}
      <div className="mb-6">
        <Tabs<ViewMode>
          variant="pills"
          tabs={viewTabs}
          value={activeView}
          onChange={setActiveView}
        />
      </div>

      {activeView === "progress" ? (
        <StudentProgressDashboard />
      ) : (
        <Card bodyClassName="p-0">
          <div className="p-4 border-b border-slate-100 flex items-center justify-between">
            <div>
              <h3 className="text-sm font-bold text-navy-950">Active Exam Proctoring Sessions</h3>
              <p className="text-xs text-slate-500">Live test attempts with automated proctoring telemetry.</p>
            </div>
          </div>
          <MonitorFilters filters={apiParams} activeCount={activeCount} update={update} reset={reset} />
          {isError ? (
            <EmptyState
              icon="alert"
              title="Could not load sessions"
              action={
                <Button variant="secondary" onClick={() => void refetch()}>
                  Try again
                </Button>
              }
            />
          ) : (
            <>
              <DataTable
                columns={columns}
                rows={data?.items ?? []}
                rowKey={(item) => item.session_id}
                loading={isFetching}
                onRowClick={(item) => navigate(`/proctoring/monitor/${item.session_id}`)}
                empty={
                  <EmptyState
                    icon="eye"
                    title={activeCount ? "No matches" : "No sessions running"}
                    description={
                      activeCount
                        ? "Clear a filter to see more."
                        : "Live proctored exams appear here while students take them."
                    }
                  />
                }
              />
              <Pagination
                pageContext={data?.pageContext}
                disabled={isFetching}
                onPageChange={(next) => update({ page: next })}
                onPerPageChange={(next) => update({ per_page: next })}
              />
            </>
          )}
        </Card>
      )}
    </>
  );
}
