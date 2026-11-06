import { useNavigate } from "react-router-dom";

import { useListParams } from "@/core/hooks/useListParams";
import { useListCourseRequestsQuery } from "@/modules/subscriptions/course-requests/api/courseRequestsApi";
import { CourseRequestFilters } from "@/modules/subscriptions/course-requests/components/list/CourseRequestFilters";
import { useCourseRequestColumns } from "@/modules/subscriptions/course-requests/components/list/useCourseRequestColumns";
import type { CourseRequestFilters as Filters } from "@/modules/subscriptions/course-requests/types";
import { Button, Card, DataTable, EmptyState, PageHeader, Pagination } from "@/shared/ui";
import { useCan } from "@/modules/user-management/common/permissions/useCan";

export function CourseRequestsListPage() {
  const { holds, acts } = useCan();
  const navigate = useNavigate();
  const { params, update, reset } = useListParams<Record<keyof Filters, string | undefined>>({ page: 1, per_page: 20 });
  const apiParams = params as Filters & { page: number; per_page: number };
  const { data, isFetching, isError, refetch } = useListCourseRequestsQuery(apiParams);
  const columns = useCourseRequestColumns();
  const activeCount = apiParams.status ? 1 : 0;

  return (
    <>
      <PageHeader
        title="Course requests"
        description={holds("subscriptions.request") ? "Requests you've submitted for your institution." : "Every institution's course requests."}
        actions={
          acts("course_requests.create", "subscriptions.request") && (
            <Button icon="plus" onClick={() => navigate("/course-requests/new")}>
              New request
            </Button>
          )
        }
      />
      <Card bodyClassName="p-0">
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
    </>
  );
}
