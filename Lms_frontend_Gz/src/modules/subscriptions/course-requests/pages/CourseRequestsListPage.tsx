import { useNavigate } from "react-router-dom";

import { useListParams } from "@/core/hooks/useListParams";
import { inr } from "@/modules/billing/common/format";
import {
  useGetInstitutionRequestsQuery,
  useGetAdminInstitutionalRequestsQuery,
} from "@/modules/billing/institutional/api/institutionalApi";
import { useListCourseRequestsQuery } from "@/modules/subscriptions/course-requests/api/courseRequestsApi";
import { CourseRequestFilters } from "@/modules/subscriptions/course-requests/components/list/CourseRequestFilters";
import { useCourseRequestColumns } from "@/modules/subscriptions/course-requests/components/list/useCourseRequestColumns";
import type { CourseRequestFilters as Filters } from "@/modules/subscriptions/course-requests/types";
import { Badge, Button, Card, DataTable, EmptyState, Icon, PageHeader, Pagination } from "@/shared/ui";
import { useCan } from "@/modules/user-management/common/permissions/useCan";

export interface CourseRequestsListPageProps {
  embedded?: boolean;
  onNavigateTab?: (tab: string) => void;
}

export function CourseRequestsListPage({ embedded = false, onNavigateTab }: CourseRequestsListPageProps = {}) {
  const { holds, can } = useCan();
  const navigate = useNavigate();
  const isInstitutionHead = holds("subscriptions.request");
  const isAdmin = can("accounts.manage") || holds("billing.manage");

  // Institutional Bulk Purchase Requests queries
  const { data: instRequests } = useGetInstitutionRequestsQuery(undefined, {
    skip: !isInstitutionHead,
  });
  const { data: adminInstRequests } = useGetAdminInstitutionalRequestsQuery(
    undefined,
    { skip: !isAdmin }
  );

  const { params, update, reset } = useListParams<Record<keyof Filters, string | undefined>>({ page: 1, per_page: 20 });
  const apiParams = params as Filters & { page: number; per_page: number };
  const { data, isFetching, isError, refetch } = useListCourseRequestsQuery(apiParams);
  const columns = useCourseRequestColumns();
  const activeCount = apiParams.status ? 1 : 0;

  const displayInstReqs = isInstitutionHead ? (instRequests ?? []) : (adminInstRequests ?? []);

  const handleOpenCalculator = () => {
    if (onNavigateTab) {
      onNavigateTab("calculator");
    } else {
      navigate("/institution/course-requests/new");
    }
  };

  const handleOpenPurchases = () => {
    if (onNavigateTab) {
      onNavigateTab("purchases");
    } else {
      navigate("/institution/purchases");
    }
  };

  return (
    <div className="space-y-6">
      {!embedded ? (
        <PageHeader
          title="Institutional Bulk Course Purchasing & Requests"
          description={
            isInstitutionHead
              ? "Request bulk course packages for your students, review quotations, complete payments, and monitor seat allocations."
              : "Review bulk course purchasing requests from colleges, prepare quotations, verify payments, and manage course pricing."
          }
          actions={
            <div className="flex flex-wrap items-center gap-2">
              {isInstitutionHead && (
                <>
                  <Button
                    variant="primary"
                    className="font-bold bg-blue-600 hover:bg-blue-700"
                    onClick={handleOpenCalculator}
                  >
                    <Icon name="plus" size={16} />
                    Request Courses / Purchase Courses
                  </Button>
                  <Button
                    variant="secondary"
                    onClick={handleOpenPurchases}
                  >
                    <Icon name="users" size={16} />
                    Purchased Packages &amp; Seats
                  </Button>
                </>
              )}

              {isAdmin && (
                <>
                  <Button
                    variant="primary"
                    className="font-bold bg-blue-600 hover:bg-blue-700"
                    onClick={() => navigate("/admin/institutional-requests")}
                  >
                    <Icon name="fileText" size={16} />
                    Admin Request Dashboard
                  </Button>
                  <Button
                    variant="secondary"
                    onClick={() => navigate("/admin/course-pricing")}
                  >
                    <Icon name="creditCard" size={16} />
                    Course Pricing Rules
                  </Button>
                </>
              )}
            </div>
          }
        />
      ) : (
        <div className="flex flex-wrap items-center justify-between gap-3 bg-white p-4 rounded-2xl border border-slate-200/80 shadow-sm">
          <div>
            <h3 className="text-sm font-bold text-navy-950">Active Quotations &amp; Course Requests</h3>
            <p className="text-xs text-slate-500">
              {isInstitutionHead
                ? "Review quotations and payment statuses submitted by your institution."
                : "Manage institutional course purchase requests from colleges."}
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            {isInstitutionHead && (
              <Button
                variant="primary"
                className="font-semibold"
                onClick={handleOpenCalculator}
              >
                <Icon name="plus" size={15} />
                New Bulk Course Request
              </Button>
            )}
            {isAdmin && (
              <Button
                variant="secondary"
                onClick={() => navigate("/admin/course-pricing")}
              >
                <Icon name="creditCard" size={15} />
                Course Pricing Rules
              </Button>
            )}
          </div>
        </div>
      )}

      {/* Model B: Institutional Purchase Requests & Quotations Section */}
      <Card
        title="Institutional Bulk Course Packages & Quotations"
        description={
          isInstitutionHead
            ? "Track your submitted bulk package requests, review custom quotations prepared by Admin, and proceed to payment."
            : "College and institution requests requiring quotation preparation or purchase approval."
        }
        bodyClassName="p-0 overflow-hidden"
      >
        {displayInstReqs.length === 0 ? (
          <div className="p-8 text-center text-sm text-slate-500">
            {isInstitutionHead
              ? "No bulk course requests submitted yet. Click 'Request Courses / Purchase Courses' to submit your first request."
              : "No institutional requests found."}
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs text-slate-700">
              <thead className="bg-slate-50 uppercase text-[11px] text-slate-500 font-semibold border-b">
                <tr>
                  <th className="px-4 py-3">Request ID</th>
                  <th className="px-4 py-3">{isAdmin ? "Institution" : "Contact"}</th>
                  <th className="px-4 py-3">Courses</th>
                  <th className="px-4 py-3">Student Seats</th>
                  <th className="px-4 py-3">Duration</th>
                  <th className="px-4 py-3">Quoted Amount</th>
                  <th className="px-4 py-3">Status</th>
                  <th className="px-4 py-3 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {displayInstReqs.map((req) => (
                  <tr key={req.public_id} className="hover:bg-slate-50/60 transition">
                    <td className="px-4 py-3.5 font-bold text-slate-900">#{req.public_id}</td>
                    <td className="px-4 py-3.5">
                      <p className="font-semibold text-slate-800">{isAdmin ? req.institution_name : req.contact_person}</p>
                      <p className="text-[11px] text-slate-500">{req.contact_email}</p>
                    </td>
                    <td className="px-4 py-3.5">
                      <span className="font-semibold text-slate-800">
                        {req.requested_courses.length} Courses:
                      </span>{" "}
                      <span className="text-slate-600 line-clamp-1">
                        {req.requested_courses.map((c) => c.course_title).join(", ")}
                      </span>
                    </td>
                    <td className="px-4 py-3.5 font-medium text-slate-700">
                      {req.quotation?.approved_seats || req.seats_requested} Seats
                    </td>
                    <td className="px-4 py-3.5 font-medium text-slate-700">
                      {req.quotation?.approved_duration_days || req.duration_days_requested} Days
                    </td>
                    <td className="px-4 py-3.5 font-bold text-slate-900">
                      {req.quotation ? inr(req.quotation.total_paise) : <span className="text-slate-400 font-normal">Pending Quote</span>}
                    </td>
                    <td className="px-4 py-3.5">
                      <Badge
                        tone={
                          req.status === "approved"
                            ? "green"
                            : req.status === "paid" || req.status === "accepted"
                            ? "blue"
                            : req.status === "quoted"
                            ? "amber"
                            : "gray"
                        }
                      >
                        {req.status.replace("_", " ").toUpperCase()}
                      </Badge>
                    </td>
                    <td className="px-4 py-3.5 text-right space-x-2">
                      {isInstitutionHead ? (
                        <Button
                          size="sm"
                          variant="primary"
                          onClick={() => navigate(`/institution/course-requests/${req.public_id}`)}
                        >
                          {req.status === "quoted"
                            ? "Review Quote & Pay"
                            : req.status === "accepted"
                            ? "Proceed to Payment"
                            : "View Details"}
                        </Button>
                      ) : (
                        <Button
                          size="sm"
                          variant="primary"
                          onClick={() => navigate("/admin/institutional-requests")}
                        >
                          Manage in Admin
                        </Button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      {/* Legacy / Simple Course Requests fallback */}
      <Card title="Individual Academic Course Requests" bodyClassName="p-0">
        <CourseRequestFilters filters={apiParams} activeCount={activeCount} update={update} reset={reset} />
        {isError ? (
          <EmptyState icon="alert" title="Could not load course requests" action={<Button variant="secondary" onClick={() => void refetch()}>Try again</Button>} />
        ) : (
          <>
            <DataTable
              columns={columns}
              rows={data?.items ?? []}
              rowKey={(item) => item.course_request_id}
              loading={isFetching}
              onRowClick={(item) => navigate(`/course-requests/${item.course_request_id}`)}
              empty={<EmptyState icon="graduation" title={activeCount ? "No matches" : "No course requests yet"} description={activeCount ? "Clear a filter to see more." : "Ask for a course to get it for your institution."} />}
            />
            <Pagination pageContext={data?.pageContext} disabled={isFetching} onPageChange={(next) => update({ page: next })} onPerPageChange={(next) => update({ per_page: next })} />
          </>
        )}
      </Card>
    </div>
  );
}
