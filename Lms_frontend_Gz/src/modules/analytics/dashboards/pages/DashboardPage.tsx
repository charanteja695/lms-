import { useState } from "react";
import { Navigate, useNavigate, useParams } from "react-router-dom";

import { formatDate } from "@/core/lib/format";
import { DASHBOARD_BY_KEY } from "@/modules/analytics/common/dashboards";
import { useAnalyticsRights } from "@/modules/analytics/common/hooks/useAnalyticsRights";
import type { DashboardKey } from "@/modules/analytics/common/types";
import { useGetDashboardQuery } from "@/modules/analytics/dashboards/api/dashboardsApi";
import { BreakdownBars } from "@/modules/analytics/dashboards/components/BreakdownBars";
import { DashboardFiltersBar, type FilterState } from "@/modules/analytics/dashboards/components/DashboardFiltersBar";
import { metricValue } from "@/modules/analytics/dashboards/components/metricValue";
import { Button, Card, EmptyState, PageHeader, Spinner, StatTile, Tabs } from "@/shared/ui";

export function DashboardPage() {
  const { dashboard = "" } = useParams();
  const navigate = useNavigate();
  const { dashboards } = useAnalyticsRights();
  const [filters, setFilters] = useState<FilterState>({ days: 7 });
  const access = dashboards.find((d) => d.key === dashboard);
  const spec = access ? DASHBOARD_BY_KEY[access.key] : undefined;
  const needsOrg = Boolean(access?.platform && access.key === "institution" && !filters.organization_id);
  const params = access?.platform ? { organization_id: filters.organization_id, employer_id: access.key === "hiring" ? filters.employer_id : undefined } : access?.fixed;
  const { data, isFetching, isError } = useGetDashboardQuery({ key: access?.key ?? "content", days: filters.days, ...params }, { skip: !access || needsOrg });

  if (dashboards.length === 0) return <EmptyState icon="dashboard" title="No dashboards for your role" description="Ask a super admin if you need access to analytics." />;
  if (!access || !spec) return <Navigate to={`/analytics/${dashboards[0]?.key}`} replace />;

  return (
    <>
      <PageHeader title="Analytics" description={spec.description} actions={<Button variant="secondary" icon="clock" onClick={() => navigate("/analytics/reports")}>Scheduled reports</Button>} />
      {dashboards.length > 1 && (
        <div className="mb-4 overflow-x-auto">
          <Tabs<DashboardKey> tabs={dashboards.map((d) => ({ value: d.key, label: DASHBOARD_BY_KEY[d.key].label }))} value={access.key} onChange={(k) => navigate(`/analytics/${k}`)} />
        </div>
      )}
      <Card className="mb-4"><DashboardFiltersBar dashboard={access.key} platform={access.platform} value={filters} onChange={setFilters} /></Card>
      {needsOrg ? (
        <EmptyState icon="building" title="Choose an institution" description="This dashboard shows one institution at a time." />
      ) : isError ? (
        <EmptyState icon="alert" title="This dashboard isn't available to you" description="Pick another dashboard above, or ask a super admin for access." />
      ) : !data ? (
        <Spinner />
      ) : (
        <div className={isFetching ? "opacity-60 transition-opacity" : undefined}>
          <p className="mb-3 text-xs text-slate-500">{formatDate(data.since)} – {formatDate(data.until)}</p>
          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            {spec.metrics.map((m) => <StatTile key={m.key} icon={m.icon} label={m.label} value={metricValue(data[m.key], m.format)} />)}
          </div>
          {spec.breakdowns.length > 0 && (
            <div className="mt-4 grid gap-4 lg:grid-cols-2">
              {spec.breakdowns.map((b) => <BreakdownBars key={b.key} title={b.label} counts={(data[b.key] as Record<string, number> | undefined) ?? {}} />)}
            </div>
          )}
        </div>
      )}
    </>
  );
}
