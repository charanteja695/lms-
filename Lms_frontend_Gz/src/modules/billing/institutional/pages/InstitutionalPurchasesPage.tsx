import { useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  useGetInstitutionPurchasesQuery,
  useGetInstitutionPurchaseStudentsQuery,
  useRenewPackageMutation,
} from "@/modules/billing/institutional/api/institutionalApi";
import type { StudentSeatUsage } from "@/modules/billing/institutional/types";
import { inr } from "@/modules/billing/common/format";
import { Alert, Badge, Button, Card, EmptyState, Icon, Modal, PageHeader, PageLoader, StatTile } from "@/shared/ui";

export interface InstitutionalPurchasesPageProps {
  embedded?: boolean;
  onNavigateTab?: (tab: string) => void;
}

export function InstitutionalPurchasesPage({ embedded = false, onNavigateTab }: InstitutionalPurchasesPageProps = {}) {
  const navigate = useNavigate();
  const { data: packages, isLoading, isError } = useGetInstitutionPurchasesQuery();
  const [selectedPackageId, setSelectedPackageId] = useState<string | null>(null);
  const [renewPackage, { isLoading: isRenewing }] = useRenewPackageMutation();

  const handleRenew = async (pkgId: string) => {
    try {
      await renewPackage({ id: pkgId, duration_days: 180 }).unwrap();
      alert("Package renewed successfully for an additional 180 days!");
    } catch (err: any) {
      alert("Failed to renew package: " + (err?.data?.message || err.message));
    }
  };

  const handleOpenCalculator = () => {
    if (onNavigateTab) {
      onNavigateTab("calculator");
    } else {
      navigate("/institution/course-requests/new");
    }
  };

  const { data: students, isLoading: isStudentsLoading } = useGetInstitutionPurchaseStudentsQuery(
    selectedPackageId ?? "",
    { skip: !selectedPackageId }
  );

  if (isLoading) return <PageLoader />;

  const packageList = packages ?? [];
  const totalSeatsPurchased = packageList.reduce((acc, p) => acc + p.seats_total, 0);
  const totalSeatsUsed = packageList.reduce((acc, p) => acc + p.seats_used, 0);
  const totalSeatsAvailable = Math.max(0, totalSeatsPurchased - totalSeatsUsed);

  return (
    <div className="mx-auto max-w-6xl py-2 space-y-6">
      {!embedded ? (
        <PageHeader
          title="Institutional Purchases & Seat Usage"
          description="Monitor active course packages, track student seat allocations, and manage license renewals."
          actions={
            <Button variant="primary" onClick={handleOpenCalculator}>
              <Icon name="plus" size={16} />
              Request Courses / Purchase Courses
            </Button>
          }
        />
      ) : (
        <div className="flex flex-wrap items-center justify-between gap-3 bg-white p-4 rounded-2xl border border-slate-200/80 shadow-sm">
          <div>
            <h3 className="text-sm font-bold text-navy-950">Active Packages &amp; Seat Utilization</h3>
            <p className="text-xs text-slate-500">
              Track student seat allocations, expiration dates, and package renewals.
            </p>
          </div>
          <Button variant="primary" onClick={handleOpenCalculator}>
            <Icon name="plus" size={15} />
            Purchase More Seats
          </Button>
        </div>
      )}

      {/* Aggregate Stats */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-4">
        <StatTile icon="award" label="Active Packages" value={packageList.length} />
        <StatTile icon="users" label="Total Seats Purchased" value={totalSeatsPurchased} />
        <StatTile icon="check" label="Seats Utilized" value={totalSeatsUsed} />
        <StatTile icon="clock" label="Available Seats" value={totalSeatsAvailable} />
      </div>

      {isError && (
        <Alert tone="error" title="Could not load purchases">
          Please check your connection and try again.
        </Alert>
      )}

      {packageList.length === 0 ? (
        <EmptyState
          icon="book"
          title="No Active Institutional Packages"
          description="Your institution has not purchased any course packages yet. Submit a purchase request to get customized bulk courses with seat licenses."
          action={
            <Button variant="primary" onClick={() => navigate("/institution/course-requests/new")}>
              Request Courses / Purchase Courses
            </Button>
          }
        />
      ) : (
        <div className="space-y-4">
          {packageList.map((pkg) => {
            const usagePercent = Math.min(100, Math.round((pkg.seats_used / (pkg.seats_total || 1)) * 100));
            const isFull = pkg.seats_available <= 0;

            return (
              <Card key={pkg.request_id} className="overflow-hidden">
                <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between border-b border-slate-100 pb-4">
                  <div>
                    <div className="flex items-center gap-2.5">
                      <h3 className="text-base font-bold text-slate-900">
                        Institutional Package #{pkg.request_id}
                      </h3>
                      <Badge tone={pkg.status === "active" ? "green" : "gray"}>
                        {pkg.status.toUpperCase()}
                      </Badge>
                      {isFull && <Badge tone="amber">Seat Limit Reached</Badge>}
                    </div>
                    <p className="mt-1 text-xs text-slate-500">
                      Purchased on {pkg.starts_at ? new Date(pkg.starts_at).toLocaleDateString() : "Recent"} · Valid until{" "}
                      <span className="font-semibold text-slate-700">
                        {pkg.ends_at ? new Date(pkg.ends_at).toLocaleDateString() : "Active Term"}
                      </span>
                    </p>
                  </div>

                  <div className="flex items-center gap-2">
                    <Button
                      size="sm"
                      variant="secondary"
                      onClick={() => setSelectedPackageId(pkg.request_id)}
                    >
                      <Icon name="users" size={14} />
                      View Student Usage ({pkg.seats_used})
                    </Button>
                    <Button
                      size="sm"
                      variant="primary"
                      disabled={isRenewing}
                      onClick={() => handleRenew(pkg.request_id)}
                    >
                      <Icon name="refresh" size={14} />
                      Renew (180 Days)
                    </Button>
                    <Button
                      size="sm"
                      variant="secondary"
                      onClick={() => navigate("/institution/course-requests/new")}
                    >
                      <Icon name="plus" size={14} />
                      Add More Courses
                    </Button>
                  </div>
                </div>

                {/* Seat Capacity Progress */}
                <div className="my-4">
                  <div className="flex items-center justify-between text-xs font-semibold text-slate-700 mb-1.5">
                    <span>Seat Allocation & Usage:</span>
                    <span>
                      {pkg.seats_used} used of {pkg.seats_total} seats ({pkg.seats_available} available)
                    </span>
                  </div>
                  <div className="w-full h-2.5 bg-slate-100 rounded-full overflow-hidden">
                    <div
                      className={`h-full rounded-full transition-all duration-500 ${
                        isFull ? "bg-amber-500" : usagePercent > 80 ? "bg-blue-600" : "bg-emerald-500"
                      }`}
                      style={{ width: `${usagePercent}%` }}
                    />
                  </div>
                </div>

                {/* Courses included in this package */}
                <div>
                  <p className="text-xs font-semibold uppercase text-slate-400 mb-2">
                    Included Courses ({pkg.courses.length}):
                  </p>
                  <div className="flex flex-wrap gap-2">
                    {pkg.courses.map((c, idx) => (
                      <span
                        key={idx}
                        className="inline-flex items-center gap-1.5 px-3 py-1 bg-slate-100 hover:bg-slate-200 text-slate-800 text-xs font-medium rounded-lg"
                      >
                        <Icon name="book" size={13} className="text-blue-600" />
                        {c.course_title}
                      </span>
                    ))}
                  </div>
                </div>

                {/* Footer notes */}
                <div className="mt-4 pt-3 border-t border-slate-100 flex items-center justify-between text-xs text-slate-500">
                  <span>Paid Amount: {inr(pkg.total_paid_paise)}</span>
                  <span>Students belonging to {pkg.institution_name} receive automatic access up to {pkg.seats_total} seats.</span>
                </div>
              </Card>
            );
          })}
        </div>
      )}

      {/* Modal: Student Usage List */}
      <Modal
        open={Boolean(selectedPackageId)}
        onClose={() => setSelectedPackageId(null)}
        title={`Students Using Package #${selectedPackageId}`}
      >
        <div className="space-y-4">
          <p className="text-xs text-slate-500">
            Below is the list of active students from your institution currently utilizing seats under this package.
          </p>

          {isStudentsLoading ? (
            <p className="text-sm text-slate-500 py-4 text-center">Loading student usage data...</p>
          ) : !students || students.length === 0 ? (
            <p className="text-sm text-slate-500 py-4 text-center">
              No students have accessed this course package yet. As students start learning, they will appear here.
            </p>
          ) : (
            <div className="overflow-x-auto max-h-96">
              <table className="w-full text-left text-xs text-slate-700">
                <thead className="bg-slate-50 uppercase text-[11px] text-slate-500 font-semibold border-b">
                  <tr>
                    <th className="px-3 py-2">Student Name</th>
                    <th className="px-3 py-2">Email</th>
                    <th className="px-3 py-2">Course Enrolled</th>
                    <th className="px-3 py-2">Enrolled Date</th>
                    <th className="px-3 py-2">Status</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {students.map((st: StudentSeatUsage, i: number) => (
                    <tr key={i} className="hover:bg-slate-50">
                      <td className="px-3 py-2.5 font-medium text-slate-900">{st.full_name}</td>
                      <td className="px-3 py-2.5 text-slate-600">{st.email}</td>
                      <td className="px-3 py-2.5 text-slate-800">{st.course_title}</td>
                      <td className="px-3 py-2.5 text-slate-500">
                        {new Date(st.enrolled_at).toLocaleDateString()}
                      </td>
                      <td className="px-3 py-2.5">
                        <Badge tone="green">Active</Badge>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          <div className="flex justify-end pt-2">
            <Button variant="secondary" onClick={() => setSelectedPackageId(null)}>
              Close
            </Button>
          </div>
        </div>
      </Modal>
    </div>
  );
}
export default InstitutionalPurchasesPage;
