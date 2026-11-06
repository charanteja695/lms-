import { useParams } from "react-router-dom";

import { useGetCaseQuery } from "@/modules/proctoring/cases/api/casesApi";
import { CaseDecisionActions } from "@/modules/proctoring/cases/components/detail/CaseDecisionActions";
import { CaseOverviewCard } from "@/modules/proctoring/cases/components/detail/CaseOverviewCard";
import { CaseReportCard } from "@/modules/proctoring/cases/components/detail/CaseReportCard";
import { CaseSnapshotsCard } from "@/modules/proctoring/cases/components/detail/CaseSnapshotsCard";
import { CaseTimelineCard } from "@/modules/proctoring/cases/components/detail/CaseTimelineCard";
import { EmptyState, PageHeader, PageLoader } from "@/shared/ui";

export function CaseDetailPage() {
  const { caseId = "" } = useParams();
  const { data: proctorCase, isLoading, isError } = useGetCaseQuery(caseId, { skip: !caseId });

  if (isLoading) return <PageLoader />;
  if (isError || !proctorCase) return <EmptyState icon="alert" title="Case not found" />;

  return (
    <>
      <PageHeader title={proctorCase.test_title ? `Integrity case · ${proctorCase.test_title}` : "Integrity case"} description="Integrity review for a proctored attempt." actions={<CaseDecisionActions proctorCase={proctorCase} />} />
      <div className="space-y-4">
        <CaseOverviewCard proctorCase={proctorCase} />
        <CaseReportCard report={proctorCase.report} />
        <CaseTimelineCard timeline={proctorCase.report.timeline} />
        <CaseSnapshotsCard caseId={proctorCase.case_id} snapshots={proctorCase.snapshots} />
      </div>
    </>
  );
}
