import { useState } from "react";
import { useNavigate, useParams, useSearchParams } from "react-router-dom";

import { safeInternalPath } from "@/core/lib/safePath";
import { PROCTORING_LEVEL_LABELS, TEST_KIND_LABELS } from "@/modules/assessments/common/labels";
import { TestStatusBadge } from "@/modules/assessments/common/components/TestStatusBadge";
import { useGetTestQuery } from "@/modules/assessments/tests/api/testsApi";
import { AnalyticsCard } from "@/modules/assessments/tests/components/detail/AnalyticsCard";
import { PlagiarismCard } from "@/modules/assessments/tests/components/detail/PlagiarismCard";
import { ResultsCard } from "@/modules/assessments/tests/components/detail/ResultsCard";
import { SchedulesCard } from "@/modules/assessments/tests/components/detail/SchedulesCard";
import { TestLifecycleActions } from "@/modules/assessments/tests/components/detail/TestLifecycleActions";
import { ValidationCard } from "@/modules/assessments/tests/components/detail/ValidationCard";
import { SectionsEditor } from "@/modules/assessments/tests/components/sections/SectionsEditor";
import { useCan } from "@/modules/user-management/common/permissions/useCan";
import { Button, DescriptionList, EmptyState, PageHeader, PageLoader, Tabs } from "@/shared/ui";

export function TestDetailPage() {
  const { testId = "" } = useParams();
  const backTo = safeInternalPath(useSearchParams()[0].get("from"));
  const navigate = useNavigate();
  const { can, holds, isSuperAdmin } = useCan();
  const canAuthor = can("content.author") || isSuperAdmin || holds("assessments.author");
  const canReview = canAuthor || can("content.review") || can("exams.manage");
  const canSchedule = can("exams.manage") || isSuperAdmin;
  const [tab, setTab] = useState<"overview" | "schedules" | "results" | "analytics" | "plagiarism">("overview");
  const { data: test, isLoading, isError } = useGetTestQuery(testId, { skip: !testId });

  if (isLoading) return <PageLoader />;
  if (isError || !test) {
    return <EmptyState icon="alert" title="Test not found" action={<Button onClick={() => navigate("/tests")}>Back to tests</Button>} />;
  }

  const tabs = [
    { value: "overview" as const, label: "Overview" },
    ...(canSchedule && test.requires_schedule ? [{ value: "schedules" as const, label: "Exam windows" }] : []),
    ...(canReview ? [{ value: "results" as const, label: "Results" }, { value: "analytics" as const, label: "Analytics" }, { value: "plagiarism" as const, label: "Plagiarism" }] : []),
  ];

  return (
    <>
      <PageHeader
        backTo={backTo ?? "/tests"}
        backLabel={backTo ? "Back to the course" : "Tests"}
        title={
          <span className="flex flex-wrap items-center gap-3">
            {test.title}
            <TestStatusBadge status={test.status} />
          </span>
        }
        description={`${TEST_KIND_LABELS[test.kind]} · ${PROCTORING_LEVEL_LABELS[test.proctoring_level]} proctoring`}
        actions={<TestLifecycleActions test={test} canAuthor={canAuthor} canReview={canReview} />}
      />

      <div className="mb-6">
        <Tabs tabs={tabs} value={tab} onChange={setTab} />
      </div>

      {tab === "overview" && (
        <div className="space-y-6">
          <DescriptionList
            items={[
              { label: "Pass mark", value: `${test.pass_mark_percent}%` },
              { label: "Max attempts", value: test.max_attempts || "Unlimited" },
              { label: "Questions", value: test.question_count ?? "Not yet validated" },
              { label: "Total marks", value: test.total_marks ?? "Not yet validated" },
              { label: "Description", value: test.description, span: 2 },
            ]}
          />
          {test.status === "draft" && <ValidationCard testId={testId} />}
          <SectionsEditor test={test} editable={canAuthor && test.status === "draft"} />
        </div>
      )}
      {tab === "schedules" && canSchedule && <SchedulesCard testId={testId} canManage={canSchedule} />}
      {tab === "results" && canReview && <ResultsCard testId={testId} canManage={can("exams.manage") || isSuperAdmin} />}
      {tab === "analytics" && canReview && <AnalyticsCard testId={testId} />}
      {tab === "plagiarism" && canReview && <PlagiarismCard testId={testId} />}
    </>
  );
}
