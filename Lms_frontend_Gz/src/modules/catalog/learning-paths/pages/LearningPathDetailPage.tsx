import { useNavigate, useParams } from "react-router-dom";

import { useGetLearningPathQuery } from "@/modules/catalog/learning-paths/api/learningPathsApi";
import { LearningPathItemsCard } from "@/modules/catalog/learning-paths/components/detail/LearningPathItemsCard";
import { LearningPathLifecycleActions } from "@/modules/catalog/learning-paths/components/detail/LearningPathLifecycleActions";
import { ContentStatusBadge } from "@/modules/catalog/common/components/ContentStatusBadge";
import { useCan } from "@/modules/user-management/common/permissions/useCan";
import { Button, DescriptionList, EmptyState, PageHeader, PageLoader } from "@/shared/ui";

export function LearningPathDetailPage() {
  const { learningPathId = "" } = useParams();
  const navigate = useNavigate();
  const { can } = useCan();
  const canAuthor = can("content.author");
  const { data: path, isLoading, isError } = useGetLearningPathQuery(learningPathId, { skip: !learningPathId });

  if (isLoading) return <PageLoader />;
  if (isError || !path) {
    return <EmptyState icon="alert" title="Learning path not found" action={<Button onClick={() => navigate("/learning-paths")}>Back to learning paths</Button>} />;
  }

  const editable = canAuthor && path.status === "draft";

  return (
    <>
      <PageHeader
        backTo="/learning-paths"
        backLabel="Learning paths"
        title={
          <span className="flex flex-wrap items-center gap-3">
            {path.title}
            <ContentStatusBadge status={path.status} />
          </span>
        }
        description={path.slug}
        actions={
          <>
            {editable && (
              <Button variant="secondary" icon="edit" onClick={() => navigate(`/learning-paths/${learningPathId}/edit`)}>
                Edit
              </Button>
            )}
            <LearningPathLifecycleActions path={path} canAuthor={canAuthor} />
          </>
        }
      />

      <DescriptionList items={[{ label: "Description", value: path.description, span: 2 }]} />

      <div className="mt-6">
        <LearningPathItemsCard path={path} editable={editable} />
      </div>
    </>
  );
}
