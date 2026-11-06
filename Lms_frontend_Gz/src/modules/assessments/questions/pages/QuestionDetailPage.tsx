import { useNavigate, useParams } from "react-router-dom";

import { BLOOM_LABELS, QUESTION_TYPE_LABELS } from "@/modules/assessments/common/labels";
import { VersionStatusBadge } from "@/modules/assessments/common/components/VersionStatusBadge";
import { useGetQuestionQuery } from "@/modules/assessments/questions/api/questionsApi";
import { QuestionLifecycleActions } from "@/modules/assessments/questions/components/detail/QuestionLifecycleActions";
import { QuestionStatsCard } from "@/modules/assessments/questions/components/detail/QuestionStatsCard";
import { QuestionVersionsCard } from "@/modules/assessments/questions/components/detail/QuestionVersionsCard";
import { useCan } from "@/modules/user-management/common/permissions/useCan";
import { Badge, Button, Card, DescriptionList, EmptyState, PageHeader, PageLoader } from "@/shared/ui";

export function QuestionDetailPage() {
  const { questionId = "" } = useParams();
  const navigate = useNavigate();
  const { can, holds, isSuperAdmin } = useCan();
  const canAuthor = can("content.author") || isSuperAdmin || holds("assessments.author");
  const canReview = canAuthor || can("content.review") || can("exams.manage");
  const { data: question, isLoading, isError } = useGetQuestionQuery(questionId, { skip: !questionId });

  if (isLoading) return <PageLoader />;
  if (isError || !question) {
    return <EmptyState icon="alert" title="Question not found" action={<Button onClick={() => navigate("/questions")}>Back to question bank</Button>} />;
  }

  const shown = question.working ?? question.current;

  return (
    <>
      <PageHeader
        backTo="/questions"
        backLabel="Question bank"
        title={
          <span className="flex flex-wrap items-center gap-3">
            {QUESTION_TYPE_LABELS[question.question_type]}
            {shown && <VersionStatusBadge status={shown.status} />}
            {question.status === "retired" && <Badge tone="red">Retired</Badge>}
          </span>
        }
        actions={<QuestionLifecycleActions question={question} canAuthor={canAuthor} canReview={canReview} />}
      />

      {shown && (
        <div className="space-y-6">
          <Card>
            <p className="whitespace-pre-wrap text-sm text-slate-700">{shown.text}</p>
          </Card>
          <DescriptionList
            items={[
              { label: "Marks", value: shown.default_marks },
              { label: "Difficulty", value: `${shown.difficulty}/5` },
              { label: "Bloom level", value: shown.bloom ? BLOOM_LABELS[shown.bloom] : null },
              { label: "Skills", value: shown.skills.join(", ") },
              { label: "Topics", value: shown.topics.join(", ") },
              { label: "Tags", value: shown.tags.join(", ") },
              { label: "Explanation", value: shown.explanation, span: 2 },
            ]}
          />
          {shown.review_note && (
            <Card title="Review note">
              <p className="text-sm text-slate-600">{shown.review_note}</p>
            </Card>
          )}
          <QuestionStatsCard questionId={questionId} stats={question.stats} />
          <QuestionVersionsCard questionId={questionId} />
        </div>
      )}
    </>
  );
}
