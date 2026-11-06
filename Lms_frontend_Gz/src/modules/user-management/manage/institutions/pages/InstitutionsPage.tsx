import { useState } from "react";

import { useListParams } from "@/core/hooks/useListParams";
import { usePermissions } from "@/modules/user-management/common/permissions/usePermissions";
import type { InstitutionStatus } from "@/modules/user-management/common/types";
import { useListInstitutionsQuery } from "@/modules/user-management/institutions/api/institutionsApi";
import { ManageFilters, type ManageFilterValues } from "@/modules/user-management/manage/common/components/ManageFilters";
import { ManagePage } from "@/modules/user-management/manage/common/components/ManagePage";
import { InstitutionFormModal } from "@/modules/user-management/manage/institutions/components/InstitutionFormModal";
import { useInstitutionColumns } from "@/modules/user-management/manage/institutions/components/useInstitutionColumns";
import { useInstitutionRowActions } from "@/modules/user-management/manage/institutions/hooks/useInstitutionRowActions";
import { ConfirmDialog, DataTable, EmptyState } from "@/shared/ui";

/** Colleges and schools: a table, "Add institution" and the same pop-up form for add and edit. */
export function InstitutionsPage() {
  const { permissions } = usePermissions();
  const { params, update } = useListParams<Record<keyof ManageFilterValues | "add", string | undefined>>({ page: 1, per_page: 20 });
  const { search_text, status, page, per_page, add } = params;
  const { data, isFetching, isError, refetch } = useListInstitutionsQuery({ search_text, status: status as InstitutionStatus | undefined, page, per_page });

  // `?add=1` (from the home page buttons) opens the form straight away
  const [formTarget, setFormTarget] = useState<"new" | string | null>(add ? "new" : null);
  const closeForm = () => {
    setFormTarget(null);
    if (add) update({ add: undefined });
  };
  const actions = useInstitutionRowActions((row) => setFormTarget(row.organization_id));
  const columns = useInstitutionColumns(actions);
  const canAdd = permissions.institutions.create;
  const activeFilters = [search_text, status].filter(Boolean).length;

  return (
    <>
      <ManagePage
        title="Institutions"
        description="Colleges and schools. Each one is owned by an admin."
        pageContext={data?.pageContext}
        addLabel={canAdd ? "Add institution" : undefined}
        onAdd={() => setFormTarget("new")}
        activeFilters={activeFilters}
        isError={isError}
        onRetry={() => void refetch()}
        isFetching={isFetching}
        onPageChange={(next) => update({ page: next })}
        onPerPageChange={(next) => update({ per_page: next })}
        filters={<ManageFilters values={{ search_text, status }} searchPlaceholder="Search by name, code or city" showInstitution={false} update={update} />}
      >
        <DataTable
          columns={columns}
          rows={data?.items ?? []}
          rowKey={(row) => row.organization_id}
          loading={isFetching}
          empty={
            <EmptyState
              icon="building"
              title={activeFilters ? "No institutions match" : "No institutions yet"}
              description={activeFilters ? "Try another search or clear the filters." : canAdd ? "Use “Add institution” to create the first one." : undefined}
            />
          }
        />
      </ManagePage>

      {formTarget !== null && <InstitutionFormModal organizationId={formTarget === "new" ? null : formTarget} onClose={closeForm} />}
      <ConfirmDialog {...actions.confirmDialogProps} />
    </>
  );
}
