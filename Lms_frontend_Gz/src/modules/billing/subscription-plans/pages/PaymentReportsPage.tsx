import { BillingTabs } from "@/modules/billing/common/components/BillingTabs";
import { inr } from "@/modules/billing/common/format";
import { useAdminGetPaymentReportsQuery } from "@/modules/billing/subscription-plans/api/studentPlansAdminApi";
import { Card, EmptyState, PageHeader, Spinner, StatTile } from "@/shared/ui";

export function PaymentReportsPage() {
  const { data, isLoading } = useAdminGetPaymentReportsQuery();

  return (
    <>
      <PageHeader title="Payment Reports" description="Revenue summary and subscription adoption across Base, Silver, and Gold plans." />
      <BillingTabs />
      {isLoading || !data ? (
        <div className="flex min-h-[260px] items-center justify-center">
          <Spinner />
        </div>
      ) : (
        <div className="space-y-6">
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <StatTile icon="creditCard" label="Total Revenue" value={inr(data.total_revenue_paise)} />
            <StatTile icon="user" label="Independent Student Revenue" value={inr(data.independent_revenue_paise)} />
            <StatTile icon="building" label="Institution Revenue" value={inr(data.institution_revenue_paise)} />
            <StatTile icon="clock" label="Pending Requests / Failed" value={`${data.pending_requests_count} req / ${data.failed_count} failed`} />
          </div>

          <div className="grid gap-6 lg:grid-cols-2">
            <Card title="Institution-wise Revenue" bodyClassName="p-0">
              {data.institution_revenue.length === 0 ? (
                <div className="p-6">
                  <EmptyState icon="building" title="No institution payments yet" description="Payments completed by Institution Heads will appear here." />
                </div>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full text-left text-sm">
                    <thead className="border-b border-slate-100 bg-slate-50/70 text-xs font-semibold text-slate-500">
                      <tr>
                        <th className="px-4 py-3">Institution</th>
                        <th className="px-4 py-3">Students</th>
                        <th className="px-4 py-3">Txns</th>
                        <th className="px-4 py-3 text-right">Revenue</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100">
                      {data.institution_revenue.map((row) => (
                        <tr key={row.organization_id}>
                          <td className="px-4 py-3 font-medium text-navy-950">{row.organization_name}</td>
                          <td className="px-4 py-3 text-slate-700">{row.students_covered}</td>
                          <td className="px-4 py-3 text-slate-700">{row.transactions}</td>
                          <td className="px-4 py-3 text-right font-semibold text-navy-950">{inr(row.revenue_paise)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </Card>

            <Card title="Course-wise Revenue" bodyClassName="p-0">
              {data.course_revenue.length === 0 ? (
                <div className="p-6">
                  <EmptyState icon="book" title="No course-level payments yet" description="Course-tagged payment totals will appear here." />
                </div>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full text-left text-sm">
                    <thead className="border-b border-slate-100 bg-slate-50/70 text-xs font-semibold text-slate-500">
                      <tr>
                        <th className="px-4 py-3">Course</th>
                        <th className="px-4 py-3">Txns</th>
                        <th className="px-4 py-3 text-right">Revenue</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100">
                      {data.course_revenue.map((row) => (
                        <tr key={row.course_id}>
                          <td className="px-4 py-3 font-medium text-navy-950">{row.course_title}</td>
                          <td className="px-4 py-3 text-slate-700">{row.transactions}</td>
                          <td className="px-4 py-3 text-right font-semibold text-navy-950">{inr(row.revenue_paise)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </Card>
          </div>

          <Card title="Revenue Breakdown by Plan" bodyClassName="p-0">
            {data.plan_breakdown.length === 0 ? (
              <div className="p-6">
                <EmptyState icon="chart" title="No captured payments yet" description="Plan-level revenue totals appear after successful student checkouts." />
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-left text-sm">
                  <thead className="border-b border-slate-100 bg-slate-50/70 text-xs font-semibold text-slate-500">
                    <tr>
                      <th className="px-4 py-3">Plan Name</th>
                      <th className="px-4 py-3">Plan Code</th>
                      <th className="px-4 py-3">Transactions</th>
                      <th className="px-4 py-3 text-right">Revenue</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {data.plan_breakdown.map((row) => (
                      <tr key={row.plan_code}>
                        <td className="px-4 py-3 font-medium text-navy-950">{row.plan_name}</td>
                        <td className="px-4 py-3 font-mono text-xs text-slate-600">{row.plan_code}</td>
                        <td className="px-4 py-3 text-slate-700">{row.transactions}</td>
                        <td className="px-4 py-3 text-right font-semibold text-navy-950">{inr(row.revenue_paise)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </Card>
        </div>
      )}
    </>
  );
}
