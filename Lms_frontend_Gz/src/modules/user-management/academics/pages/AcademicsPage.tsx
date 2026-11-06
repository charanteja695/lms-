import { useState } from "react";
import { useSearchParams } from "react-router-dom";

import { useGetAcademicsQuery } from "@/modules/user-management/academics/api/academicsApi";
import { DepartmentCard } from "@/modules/user-management/academics/components/DepartmentCard";
import { SectionRoster } from "@/modules/user-management/academics/components/SectionRoster";
import { StructureItemDialog, type StructureTarget } from "@/modules/user-management/academics/components/StructureItemDialog";
import type { ClassSection } from "@/modules/user-management/academics/types";
import { useAuth } from "@/modules/user-management/auth/hooks/useAuth";
import { useInstitutionOptions } from "@/modules/user-management/common/hooks/useEntityOptions";
import { Button, Card, EmptyState, EntityPicker, PageHeader, PageLoader, StatTile } from "@/shared/ui";

/**
 * Departments -> programs -> sections of one institution. A head, staff member or student's institution is their own;
 * the super admin and admins pick one (it stays in the address, so the page can be linked from an institution).
 */
export function AcademicsPage() {
  const { user } = useAuth();
  const [params, setParams] = useSearchParams();
  const own = user?.institution?.organization_id;
  const organizationId = own ?? params.get("organization_id") ?? "";
  const organizationLabel = params.get("organization_label") ?? undefined;
  const { data, isLoading, isError, refetch } = useGetAcademicsQuery(organizationId, { skip: !organizationId });
  const [editing, setEditing] = useState<StructureTarget | null>(null);
  const [open, setOpen] = useState<ClassSection | null>(null);

  const picker = !own && (
    <Card className="mb-6">
      <EntityPicker
        label="Institution"
        value={organizationId}
        selectedLabel={organizationLabel}
        useOptions={useInstitutionOptions}
        onChange={(id, label) => setParams(id ? { organization_id: id, organization_label: label } : {})}
      />
    </Card>
  );
  const header = (
    <PageHeader
      title="Academic structure"
      description="Departments, their programs, and each year's sections. Place students in their section."
      actions={data?.rights.create ? <Button icon="plus" onClick={() => setEditing({ kind: "departments" })}>New department</Button> : undefined}
    />
  );

  if (!organizationId) {
    return (
      <>
        {header}
        {picker}
        <EmptyState icon="building" title="Choose an institution" description="Pick the institution whose departments and sections you want to see." />
      </>
    );
  }
  if (isLoading) return <PageLoader />;
  if (isError || !data) {
    return (
      <>
        {header}
        {picker}
        <EmptyState icon="alert" title="Could not load the academic structure" action={<Button variant="secondary" onClick={() => void refetch()}>Try again</Button>} />
      </>
    );
  }

  return (
    <>
      {header}
      {picker}
      <div className="mb-6 grid grid-cols-2 gap-4 lg:grid-cols-4">
        <StatTile icon="building" label="Departments" value={data.totals.departments} />
        <StatTile icon="layers" label="Programs" value={data.totals.programs} />
        <StatTile icon="users" label="Sections" value={data.totals.sections} />
        <StatTile icon="graduation" label="Students placed" value={data.totals.placed_students} />
      </div>
      {data.departments.length === 0 ? (
        <Card>
          <EmptyState
            icon="building"
            title="Start with a department"
            description={data.rights.create ? "For example Computer Science and Engineering. Then add its programs and each year's sections." : "The institute head has not set this up yet."}
            action={data.rights.create ? <Button icon="plus" onClick={() => setEditing({ kind: "departments" })}>Add the first department</Button> : undefined}
          />
        </Card>
      ) : (
        <div className="grid items-start gap-5 xl:grid-cols-2">
          {data.departments.map((department) => (
            <DepartmentCard
              key={department.department_id}
              organizationId={organizationId}
              department={department}
              rights={data.rights}
              onEdit={setEditing}
              onOpenSection={setOpen}
            />
          ))}
        </div>
      )}
      {editing && <StructureItemDialog organizationId={organizationId} target={editing} onClose={() => setEditing(null)} />}
      {open && !editing && (
        <SectionRoster
          organizationId={organizationId}
          section={open}
          rights={data.rights}
          onClose={() => setOpen(null)}
          onEdit={() => {
            const program = data.departments.flatMap((d) => d.programs).find((p) => p.program_id === open.program_id);
            if (program) setEditing({ kind: "sections", item: open, parent: program });
          }}
        />
      )}
    </>
  );
}
