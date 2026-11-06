import { Link, useNavigate, useParams } from "react-router-dom";

import { InstitutionNameCell } from "@/modules/user-management/common/components/InstitutionNameCell";
import { useGetBatchQuery } from "@/modules/learning/batches/api/batchesApi";
import { BatchStatusBadge } from "@/modules/learning/common/components/BatchStatusBadge";
import { EnrollmentsCard } from "@/modules/learning/enrollments/components/EnrollmentsCard";
import { Button, Card, EmptyState, Icon, PageHeader, PageLoader } from "@/shared/ui";
import { useCan } from "@/modules/user-management/common/permissions/useCan";
import { formatDate } from "@/core/lib/format";

export function BatchDetailPage() {
  const { can, acts } = useCan();
  const { batchId = "" } = useParams();
  const navigate = useNavigate();
  const manager = can("accounts.manage");
  const canEnroll = manager || acts("batches.create", "learning.batches.manage");
  const canWithdraw = manager || acts("batches.revoke", "learning.batches.manage");
  const { data: batch, isLoading, isError } = useGetBatchQuery(batchId, { skip: !batchId });

  if (isLoading) return <PageLoader />;
  if (isError || !batch) {
    return (
      <EmptyState
        icon="alert"
        title="Batch not found"
        action={<Button onClick={() => navigate("/batches")}>Back to batches</Button>}
      />
    );
  }

  return (
    <>
      <PageHeader
        backTo="/batches"
        backLabel="Batches"
        title={
          <span className="flex flex-wrap items-center gap-3">
            {batch.name}
            <BatchStatusBadge status={batch.status} />
          </span>
        }
        description={batch.title}
        actions={
          <Link to={`/courses/${batch.course_id}`}>
            <Button variant="secondary" icon="graduation">
              View Course
            </Button>
          </Link>
        }
      />

      {/* Cohort Overview Cards */}
      <div className="mb-6 grid gap-4 sm:grid-cols-3">
        <Card>
          <p className="text-xs font-bold uppercase tracking-wider text-slate-400">Assigned Course</p>
          <p className="mt-1 font-bold text-navy-950 sm:text-base line-clamp-1">{batch.title}</p>
          <Link
            to={`/courses/${batch.course_id}`}
            className="mt-1 inline-flex items-center gap-1 text-xs font-semibold text-brand-700 hover:underline"
          >
            Open curriculum <Icon name="chevronRight" size={12} />
          </Link>
        </Card>

        <Card>
          <p className="text-xs font-bold uppercase tracking-wider text-slate-400">Institution</p>
          <div className="mt-1 font-bold text-navy-950 sm:text-base">
            <InstitutionNameCell organizationId={batch.organization_id} />
          </div>
          <p className="mt-1 text-xs text-slate-500">Student cohort owner</p>
        </Card>

        <Card>
          <p className="text-xs font-bold uppercase tracking-wider text-slate-400">Cohort Created</p>
          <p className="mt-1 font-bold text-navy-950 sm:text-base">
            {formatDate(batch.created_at.slice(0, 10))}
          </p>
          <p className="mt-1 text-xs text-slate-500">Status: {batch.status}</p>
        </Card>
      </div>

      <div className="mt-6">
        <EnrollmentsCard batchId={batch.batch_id} organizationId={batch.organization_id} canEnroll={canEnroll} canWithdraw={canWithdraw} />
      </div>
    </>
  );
}
