import { useNavigate, useParams } from "react-router-dom";

import { toApiError } from "@/core/lib/apiError";
import { useGetStudentPaymentStatusQuery } from "@/modules/store/api/studentSubscriptionsApi";
import { PaymentStateCard } from "@/modules/store/components/PaymentStateCard";
import { Button, EmptyState, Spinner } from "@/shared/ui";

export function PaymentStatusPage() {
  const { txId = "" } = useParams<{ txId: string }>();
  const navigate = useNavigate();
  const { data, isLoading, isFetching, error, refetch } = useGetStudentPaymentStatusQuery(txId, { skip: !txId });

  if (isLoading) {
    return (
      <div className="flex min-h-[300px] items-center justify-center">
        <Spinner />
      </div>
    );
  }

  if (error || !data) {
    return (
      <EmptyState
        icon="alert"
        title="Payment record not found"
        description={toApiError(error).message}
        action={<Button onClick={() => navigate("/payment-history")}>Payment History</Button>}
      />
    );
  }

  return (
    <PaymentStateCard
      transaction={data.transaction}
      busy={isFetching}
      onRefresh={() => refetch()}
      onRetry={() =>
        navigate(
          `/checkout?planId=${encodeURIComponent(data.transaction.plan_id)}&courseId=${encodeURIComponent(
            data.transaction.course_id ?? "",
          )}&action=${data.transaction.action_type}`,
        )
      }
    />
  );
}
