import { useMemo } from "react";

import { useCourseOptions } from "@/modules/catalog/common/hooks/useCourseOptions";
import { useCourseTitle } from "@/modules/catalog/common/hooks/useCourseTitle";
import { CERTIFICATE_STATUS_LABELS, PDF_STATUS_LABELS } from "@/modules/certificates/common/labels";
import type { CertificateFilters as Filters } from "@/modules/certificates/issued/types";
import { useStudentOptions } from "@/modules/learning/enrollments/hooks/useStudentOptions";
import { useAuth } from "@/modules/user-management/auth/hooks/useAuth";
import { Button, EntityPicker, FilterRow, FilterSelect } from "@/shared/ui";

const STATUS_OPTIONS = Object.entries(CERTIFICATE_STATUS_LABELS).map(([value, label]) => ({ value, label }));
const PDF_OPTIONS = Object.entries(PDF_STATUS_LABELS).map(([value, label]) => ({ value, label }));
const SORT_OPTIONS = [
  { value: "desc", label: "Newest" },
  { value: "asc", label: "Oldest" },
];

/** Staff pick a course and (in their organisation) a student by name; a student's own list only needs status and order. */
export function CertificateFilters({ filters, activeCount, showStaffFilters, update, reset }: {
  filters: Filters;
  activeCount: number;
  /** A student's list is already just their own; filtering by course or student only makes sense for staff. */
  showStaffFilters: boolean;
  update(changes: Record<string, string | boolean | undefined>): void;
  reset(): void;
}) {
  const { user } = useAuth();
  const orgId = user?.institution?.organization_id ?? "";
  const { title: courseTitle } = useCourseTitle(filters.course_id ?? "");
  const studentOptions = useMemo(() => useStudentOptions(orgId), [orgId]);
  return (
    <FilterRow activeCount={activeCount}>
      {showStaffFilters && (
        <div className="w-full sm:w-64">
          <EntityPicker label="Course" value={filters.course_id ?? ""} selectedLabel={courseTitle ?? undefined} emptyLabel="All courses" useOptions={useCourseOptions} onChange={(value) => update({ course_id: value || undefined })} />
        </div>
      )}
      {showStaffFilters && orgId && (
        <div className="w-full sm:w-64">
          <EntityPicker label="Student" value={filters.user_id ?? ""} emptyLabel="All students" useOptions={studentOptions} onChange={(value) => update({ user_id: value || undefined })} />
        </div>
      )}
      <FilterSelect label="Status" value={filters.status} options={STATUS_OPTIONS} onChange={(value) => update({ status: value })} />
      {showStaffFilters && <FilterSelect label="PDF" value={filters.pdf_status} options={PDF_OPTIONS} onChange={(value) => update({ pdf_status: value })} />}
      <FilterSelect label="Order" value={filters.sort_order} options={SORT_OPTIONS} placeholder="Newest" onChange={(value) => update({ sort_order: value })} />
      {activeCount > 0 && (
        <Button variant="ghost" onClick={reset}>
          Clear ({activeCount})
        </Button>
      )}
    </FilterRow>
  );
}
