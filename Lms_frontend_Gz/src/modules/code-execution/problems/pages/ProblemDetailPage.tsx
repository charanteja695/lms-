import { useState } from "react";
import { useNavigate, useParams } from "react-router-dom";

import { useGetProblemAuthorQuery, useGetProblemQuery } from "@/modules/code-execution/problems/api/problemsApi";
import { DifficultyBadge } from "@/modules/code-execution/common/components/DifficultyBadge";
import { ProblemStatusBadge } from "@/modules/code-execution/common/components/ProblemStatusBadge";
import { PROBLEM_TYPE_LABELS } from "@/modules/code-execution/common/labels";
import { ProblemLifecycleActions } from "@/modules/code-execution/problems/components/detail/ProblemLifecycleActions";
import { ProblemStatement } from "@/modules/code-execution/problems/components/detail/ProblemStatement";
import { ProblemStatsCard } from "@/modules/code-execution/problems/components/detail/ProblemStatsCard";
import { TestCasesCard } from "@/modules/code-execution/problems/components/detail/TestCasesCard";
import { ProblemWorkspace } from "@/modules/code-execution/problems/components/workspace/ProblemWorkspace";
import type { Problem, ProblemAuthor } from "@/modules/code-execution/problems/types";
import { SubmissionHistoryCard } from "@/modules/code-execution/submissions/components/SubmissionHistoryCard";
import { useCan } from "@/modules/user-management/common/permissions/useCan";
import { Badge, Button, EmptyState, PageHeader, PageLoader, Tabs } from "@/shared/ui";

function isProblemAuthor(problem: Problem | ProblemAuthor): problem is ProblemAuthor {
  return "test_case_count" in problem;
}

export function ProblemDetailPage() {
  const { problemId = "" } = useParams();
  const navigate = useNavigate();
  const { can, isSuperAdmin } = useCan();
  const canAuthor = can("content.author") || isSuperAdmin;
  const canReview = canAuthor || can("content.review") || can("exams.manage");
  const [tab, setTab] = useState<"solve" | "test-cases" | "stats">("solve");

  const plain = useGetProblemQuery(problemId, { skip: !problemId || canAuthor });
  const authored = useGetProblemAuthorQuery(problemId, { skip: !problemId || !canAuthor });
  const { data: problem, isLoading, isError } = canAuthor ? authored : plain;

  if (isLoading) return <PageLoader />;
  if (isError || !problem) {
    return <EmptyState icon="alert" title="Problem not found" action={<Button onClick={() => navigate("/problems")}>Back to problems</Button>} />;
  }

  const tabs = [
    { value: "solve" as const, label: "Solve" },
    ...(canAuthor ? [{ value: "test-cases" as const, label: "Test cases" }] : []),
    ...(canReview ? [{ value: "stats" as const, label: "Stats" }] : []),
  ];

  return (
    <>
      <PageHeader
        backTo="/problems"
        backLabel="Problems"
        title={
          <span className="flex flex-wrap items-center gap-3">
            {problem.title}
            <DifficultyBadge difficulty={problem.difficulty} />
            {canAuthor && <ProblemStatusBadge status={problem.status} />}
          </span>
        }
        description={
          <span className="flex flex-wrap items-center gap-2">
            {PROBLEM_TYPE_LABELS[problem.problem_type]}
            {problem.tags.map((tag) => (
              <Badge key={tag} tone="gray">
                {tag}
              </Badge>
            ))}
          </span>
        }
        actions={canAuthor && isProblemAuthor(problem) ? <ProblemLifecycleActions problem={problem} /> : undefined}
      />

      {tabs.length > 1 && <div className="mb-6"><Tabs tabs={tabs} value={tab} onChange={setTab} /></div>}

      {tab === "solve" && (
        <div className="grid gap-6 lg:grid-cols-2">
          <div className="space-y-4">
            <ProblemStatement problem={problem} />
            <SubmissionHistoryCard problemId={problemId} />
          </div>
          <ProblemWorkspace problem={problem} />
        </div>
      )}
      {tab === "test-cases" && canAuthor && <TestCasesCard problemId={problemId} editable={problem.status === "draft"} />}
      {tab === "stats" && canReview && <ProblemStatsCard problemId={problemId} />}
    </>
  );
}
