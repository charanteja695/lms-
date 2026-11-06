import { useSearchParams } from "react-router-dom";

import { TutorTabs } from "@/modules/ai-tutor/common/components/TutorTabs";
import { useCourseOptions } from "@/modules/catalog/common/hooks/useCourseOptions";
import { useCourseTitle } from "@/modules/catalog/common/hooks/useCourseTitle";
import { useTutorRights } from "@/modules/ai-tutor/common/hooks/useTutorRights";
import { EvalSetsPanel } from "@/modules/ai-tutor/insights/components/EvalSetsPanel";
import { FeedbackPanel } from "@/modules/ai-tutor/insights/components/FeedbackPanel";
import { IndexPanel } from "@/modules/ai-tutor/insights/components/IndexPanel";
import { Card, EmptyState, EntityPicker, PageHeader, Tabs } from "@/shared/ui";

type Tab = "feedback" | "evaluation" | "index";

/** Per-course tutor quality: student feedback, offline retrieval evaluation, and the search index. Course and tab live in the URL. */
export function CourseInsightsPage() {
  const [search, setSearch] = useSearchParams();
  const rights = useTutorRights();
  const courseId = search.get("course") ?? "";
  const { title } = useCourseTitle(courseId);
  const tabs = [
    ...(rights.canSeeInsights ? [{ value: "feedback" as const, label: "Feedback" }, { value: "evaluation" as const, label: "Evaluation" }] : []),
    { value: "index" as const, label: "Index" },
  ];
  const requested = search.get("tab") as Tab | null;
  const tab: Tab = tabs.some((item) => item.value === requested) ? (requested as Tab) : tabs[0]!.value;

  const update = (changes: Record<string, string>) => {
    const next = new URLSearchParams(search);
    Object.entries(changes).forEach(([key, value]) => (value ? next.set(key, value) : next.delete(key)));
    setSearch(next, { replace: true });
  };

  return (
    <>
      <PageHeader title="AI tutor" description="How well the tutor answers each course, and what students ask it." />
      <TutorTabs />
      <Card className="mb-4">
        <div className="max-w-md">
          <EntityPicker label="Course" value={courseId} selectedLabel={title ?? courseId} useOptions={useCourseOptions} onChange={(value) => update({ course: value })} />
        </div>
      </Card>
      {!courseId ? (
        <EmptyState icon="layers" title="Choose a course" description="Pick a course above to see how well the tutor answers it." />
      ) : (
        <div className="space-y-4">
          <Tabs tabs={tabs} value={tab} onChange={(value) => update({ tab: value })} />
          {tab === "feedback" && <FeedbackPanel courseId={courseId} />}
          {tab === "evaluation" && <EvalSetsPanel courseId={courseId} />}
          {tab === "index" && <IndexPanel courseId={courseId} canReindex={rights.canReindex} />}
        </div>
      )}
    </>
  );
}
