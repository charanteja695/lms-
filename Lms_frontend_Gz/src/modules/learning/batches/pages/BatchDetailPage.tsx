import { useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

import { InstitutionNameCell } from "@/modules/user-management/common/components/InstitutionNameCell";
import {
  useGetBatchQuery,
  useUpdateBatchMutation,
  useDeleteBatchMutation,
} from "@/modules/learning/batches/api/batchesApi";
import { BatchStatusBadge } from "@/modules/learning/common/components/BatchStatusBadge";
import { EnrollmentsCard } from "@/modules/learning/enrollments/components/EnrollmentsCard";
import {
  Button,
  Card,
  ConfirmDialog,
  EmptyState,
  Field,
  Icon,
  Input,
  Modal,
  PageHeader,
  PageLoader,
} from "@/shared/ui";
import { useCan } from "@/modules/user-management/common/permissions/useCan";
import { useConfirmAction } from "@/core/hooks/useConfirmAction";
import { formatDate } from "@/core/lib/format";
import { useNotify } from "@/core/hooks/useNotify";

export function BatchDetailPage() {
  const { can, acts } = useCan();
  const { batchId = "" } = useParams();
  const navigate = useNavigate();
  const notify = useNotify();
  const confirm = useConfirmAction();

  const manager = can("accounts.manage");
  const canManageBatch = manager || acts("batches.create", "learning.batches.manage");
  const canEnroll = manager || acts("batches.create", "learning.batches.manage");
  const canWithdraw = manager || acts("batches.revoke", "learning.batches.manage");

  const { data: batch, isLoading, isError } = useGetBatchQuery(batchId, { skip: !batchId });
  const [updateBatch, { isLoading: isUpdating }] = useUpdateBatchMutation();
  const [deleteBatch, { isLoading: isDeleting }] = useDeleteBatchMutation();

  // State for Edit Batch Modal
  const [editOpen, setEditOpen] = useState(false);
  const [newName, setNewName] = useState("");

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

  const handleOpenEdit = () => {
    setNewName(batch.name);
    setEditOpen(true);
  };

  const handleSaveEdit = async () => {
    if (!newName.trim()) return;
    try {
      await updateBatch({ id: batchId, name: newName.trim() }).unwrap();
      notify.success("Batch updated", `Cohort renamed to "${newName.trim()}"`);
      setEditOpen(false);
    } catch (err: any) {
      notify.error("Update failed", err?.data?.message || err.message || "Failed to update batch");
    }
  };

  const handleToggleStatus = async () => {
    const nextStatus = batch.status === "active" ? "archived" : "active";
    try {
      await updateBatch({ id: batchId, status: nextStatus }).unwrap();
      notify.success("Status updated", `Batch status changed to ${nextStatus}.`);
    } catch (err: any) {
      notify.error("Failed to update status", err?.data?.message || err.message);
    }
  };

  const handleConfirmArchive = () => {
    confirm.ask(
      {
        title: `Archive batch "${batch.name}"?`,
        description: "Active students will no longer see this batch cohort.",
        confirmLabel: "Archive Batch",
      },
      async () => {
        try {
          await deleteBatch(batchId).unwrap();
          notify.success("Batch archived", "Batch cohort has been archived successfully.");
          navigate("/batches");
        } catch (err: any) {
          notify.error("Archive failed", err?.data?.message || err.message);
        }
      }
    );
  };

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
          <div className="flex flex-wrap items-center gap-2">
            <Link to={`/courses/${batch.course_id}`}>
              <Button variant="secondary" icon="graduation">
                View Course
              </Button>
            </Link>
            {canManageBatch && (
              <>
                <Button variant="secondary" icon="edit" onClick={handleOpenEdit}>
                  Edit Name
                </Button>
                <Button
                  variant="secondary"
                  onClick={handleToggleStatus}
                  disabled={isUpdating}
                >
                  {batch.status === "active" ? "Archive" : "Activate"}
                </Button>
                <Button
                  variant="danger"
                  icon="trash"
                  onClick={handleConfirmArchive}
                  disabled={isDeleting}
                >
                  Delete
                </Button>
              </>
            )}
          </div>
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
        <EnrollmentsCard
          batchId={batch.batch_id}
          organizationId={batch.organization_id}
          canEnroll={canEnroll}
          canWithdraw={canWithdraw}
        />
      </div>

      {/* Edit Batch Name Modal */}
      {editOpen && (
        <Modal
          open={editOpen}
          onClose={() => setEditOpen(false)}
          title="Edit Batch Name"
        >
          <div className="space-y-4 pt-2">
            <Field label="Batch Name" required>
              {(props) => (
                <Input
                  {...props}
                  value={newName}
                  onChange={(e) => setNewName(e.target.value)}
                  placeholder="e.g. 2026 CS Batch A"
                  autoFocus
                />
              )}
            </Field>

            <div className="flex justify-end gap-2 pt-2">
              <Button variant="secondary" onClick={() => setEditOpen(false)}>
                Cancel
              </Button>
              <Button
                variant="primary"
                onClick={handleSaveEdit}
                disabled={!newName.trim() || isUpdating}
              >
                Save Changes
              </Button>
            </div>
          </div>
        </Modal>
      )}

      {/* Confirm Action Dialog */}
      <ConfirmDialog {...confirm.dialogProps} />
    </>
  );
}
