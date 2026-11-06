import { useNavigate } from "react-router-dom";

import { useListParams } from "@/core/hooks/useListParams";
import { useListSubscriptionsQuery } from "@/modules/subscriptions/subscriptions/api/subscriptionsApi";
import { SubscriptionFilters } from "@/modules/subscriptions/subscriptions/components/list/SubscriptionFilters";
import { useSubscriptionColumns } from "@/modules/subscriptions/subscriptions/components/list/useSubscriptionColumns";
import type { SubscriptionFilters as Filters } from "@/modules/subscriptions/subscriptions/types";
import { Button, Card, DataTable, EmptyState, PageHeader, Pagination } from "@/shared/ui";

export function SubscriptionsListPage() {
  const navigate = useNavigate();
  const { params, update, reset } = useListParams<Record<keyof Filters, string | undefined>>({ page: 1, per_page: 20 });
  const apiParams = params as Filters & { page: number; per_page: number };
  const { data, isFetching, isError, refetch } = useListSubscriptionsQuery(apiParams);
  const columns = useSubscriptionColumns();
  const activeCount = apiParams.status ? 1 : 0;

  return (
    <>
      <PageHeader title="Subscriptions" description="Active, expired and cancelled course subscriptions." />
      <Card bodyClassName="p-0">
        <SubscriptionFilters filters={apiParams} activeCount={activeCount} update={update} reset={reset} />
        {isError ? (
          <EmptyState icon="alert" title="Could not load subscriptions" action={<Button variant="secondary" onClick={() => void refetch()}>Try again</Button>} />
        ) : (
          <>
            <DataTable
              columns={columns}
              rows={data?.items ?? []}
              rowKey={(item) => item.subscription_id}
              loading={isFetching}
              onRowClick={(item) => navigate(`/subscriptions/${item.subscription_id}`)}
              empty={<EmptyState icon="graduation" title={activeCount ? "No matches" : "No subscriptions yet"} description={activeCount ? "Clear a filter to see more." : "Courses your institution has appear here once approved."} />}
            />
            <Pagination pageContext={data?.pageContext} disabled={isFetching} onPageChange={(next) => update({ page: next })} onPerPageChange={(next) => update({ per_page: next })} />
          </>
        )}
      </Card>
    </>
  );
}
