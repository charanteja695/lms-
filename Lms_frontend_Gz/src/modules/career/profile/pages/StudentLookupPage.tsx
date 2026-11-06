import { useNavigate } from "react-router-dom";

import { useStudentOptions } from "@/modules/user-management/common/hooks/useEntityOptions";
import { Card, EntityPicker, PageHeader } from "@/shared/ui";

/** Staff (their institution's students) and careers managers (any) open a student's skill profile, read only. */
export function StudentLookupPage() {
  const navigate = useNavigate();
  return (
    <>
      <PageHeader title="Student profiles" description="Look up a student's skill profile — what their resumes are built from." />
      <Card>
        <div className="max-w-md">
          <EntityPicker label="Student" value="" useOptions={useStudentOptions} placeholder="Search by name or email…" onChange={(userId) => userId && navigate(`/career/students/${userId}`)} />
        </div>
      </Card>
    </>
  );
}
