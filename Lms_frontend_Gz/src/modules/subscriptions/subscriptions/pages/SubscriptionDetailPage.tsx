import { useState } from "react";
import { useNavigate, useParams } from "react-router-dom";

import { formatDate, formatDateTime } from "@/core/lib/format";
import { CourseTitleCell } from "@/modules/catalog/common/components/CourseTitleCell";
import { InstitutionNameCell } from "@/modules/user-management/common/components/InstitutionNameCell";
import { useGetSubscriptionQuery } from "@/modules/subscriptions/subscriptions/api/subscriptionsApi";
import { CancelDialog } from "@/modules/subscriptions/subscriptions/components/detail/CancelDialog";
import { SubscriptionStatusBadge } from "@/modules/subscriptions/common/components/SubscriptionStatusBadge";
import { Alert, Button, DescriptionList, EmptyState, PageHeader, PageLoader, StatTile } from "@/shared/ui";
import { useCan } from "@/modules/user-management/common/permissions/useCan";

export function SubscriptionDetailPage() {
  const { can } = useCan();
  const { subscriptionId = "" } = useParams();
  const navigate = useNavigate();
  const canCancel = can("accounts.manage");
  const { data: subscription, isLoading, isError } = useGetSubscriptionQuery(subscriptionId, { skip: !subscriptionId });
  const [cancelling, setCancelling] = useState(false);

  if (isLoading) return <PageLoader />;
  if (isError || !subscription) {
    return <EmptyState icon="alert" title="Subscription not found" action={<Button onClick={() => navigate("/subscriptions")}>Back to subscriptions</Button>} />;
  }

  return (
    <>
      <PageHeader
        backTo="/subscriptions"
        backLabel="Subscriptions"
        title={
          <span className="flex flex-wrap items-center gap-3">
            <CourseTitleCell courseId={subscription.course_id} />
            <SubscriptionStatusBadge status={subscription.status} />
          </span>
        }
        actions={
          canCancel &&
          subscription.status === "active" && (
            <Button variant="danger" icon="ban" onClick={() => setCancelling(true)}>
              Cancel subscription
            </Button>
          )
        }
      />

      {subscription.status === "cancelled" && subscription.cancelled_reason && (
        <Alert tone="warning" title={`Cancelled ${formatDate(subscription.cancelled_at?.slice(0, 10))}`} className="mb-6">
          {subscription.cancelled_reason}
        </Alert>
      )}

      <div className="mb-6 grid gap-4 sm:grid-cols-2">
        <StatTile icon="users" label="Seats used" value={`${subscription.seats_used} / ${subscription.seats_total}`} />
        <StatTile icon="clock" label="Seats available" value={subscription.seats_total - subscription.seats_used} />
      </div>

      <DescriptionList
        items={[
          { label: "Institution", value: <InstitutionNameCell organizationId={subscription.organization_id} /> },
          { label: "Starts", value: formatDate(subscription.starts_at.slice(0, 10)) },
          { label: "Ends", value: formatDate(subscription.ends_at.slice(0, 10)) },
          { label: "Created", value: formatDateTime(subscription.created_at) },
        ]}
      />

      {cancelling && <CancelDialog open={cancelling} onClose={() => setCancelling(false)} subscriptionId={subscription.subscription_id} />}
    </>
  );
}
