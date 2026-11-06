import { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";

import { BuilderHeader } from "@/modules/catalog/builder/components/BuilderHeader";
import { ModuleSection, type OpenState } from "@/modules/catalog/builder/components/ModuleSection";
import { BuildStats, PublishPanel } from "@/modules/catalog/builder/components/PublishPanel";
import { TestGate } from "@/modules/catalog/builder/components/TestGate";
import { type BuildIssue, buildIssues } from "@/modules/catalog/builder/hooks/useBuildIssues";
import { useCourseTests } from "@/modules/catalog/builder/hooks/useCourseTests";
import { useCurriculumActions } from "@/modules/catalog/builder/hooks/useCurriculumActions";
import { useGetCourseQuery, useGetVersionQuery } from "@/modules/catalog/courses/api/coursesApi";
import type { CourseVersionDetail } from "@/modules/catalog/courses/curriculumTypes";
import { useCan } from "@/modules/user-management/common/permissions/useCan";
import { Alert, Button, EmptyState, PageLoader } from "@/shared/ui";

/** First visit: open the first module and its first topic; everything else starts folded. */
function initialOpen(version: CourseVersionDetail): OpenState {
  const first = version.modules[0];
  return { modules: first ? { [first.module_id]: true } : {}, topics: first?.topics[0] ? { [first.topics[0].topic_id]: true } : {} };
}

/** The course builder: the whole curriculum on one page, each topic closed by its test, and what is left to publish. */
export function BuilderPage() {
  const { courseId = "", versionId = "" } = useParams();
  const navigate = useNavigate();
  const { can } = useCan();
  const { data: course } = useGetCourseQuery(courseId, { skip: !courseId });
  const { data: version, isLoading, isError } = useGetVersionQuery({ courseId, versionId }, { skip: !courseId || !versionId });
  const tests = useCourseTests(courseId, version);
  const { actions, dialogs } = useCurriculumActions(courseId, versionId, version);
  const [open, setOpen] = useState<OpenState | null>(null);
  const [highlight, setHighlight] = useState<string | null>(null);

  // modules and topics added while on the page open straight away, so their next step is in view
  const seen = useRef<Set<string> | null>(null);
  useEffect(() => {
    if (!version) return;
    const ids = version.modules.flatMap((module) => [module.module_id, ...module.topics.map((topic) => topic.topic_id)]);
    if (!seen.current) {
      seen.current = new Set(ids);
      setOpen(initialOpen(version));
      return;
    }
    const added = ids.filter((id) => !seen.current?.has(id));
    if (!added.length) return;
    added.forEach((id) => seen.current?.add(id));
    const moduleIds = new Set(version.modules.map((module) => module.module_id));
    setOpen((current) => {
      const next: OpenState = { modules: { ...current?.modules }, topics: { ...current?.topics } };
      for (const id of added) (moduleIds.has(id) ? next.modules : next.topics)[id] = true;
      // a new topic's module opens too
      for (const module of version.modules) if (module.topics.some((topic) => added.includes(topic.topic_id))) next.modules[module.module_id] = true;
      return next;
    });
  }, [version]);

  const issues = useMemo(() => (version ? buildIssues(version, tests.topicTest, tests.finalTest) : []), [version, tests]);

  if (isLoading || !open) return <PageLoader />;
  if (isError || !version) return <EmptyState icon="alert" title="Course version not found" action={<Button onClick={() => navigate("/courses")}>Back to courses</Button>} />;

  const editable = can("content.author") && version.status === "draft";
  const base = `/courses/${courseId}/versions/${versionId}`;
  const setAll = (value: boolean) =>
    setOpen({
      modules: Object.fromEntries(version.modules.map((module) => [module.module_id, value])),
      topics: Object.fromEntries(version.modules.flatMap((module) => module.topics.map((topic) => [topic.topic_id, value]))),
    });
  const goTo = (issue: BuildIssue) => {
    if (issue.final) return navigate(`${base}/final-test`);
    if (!issue.topicId) return;
    const module = version.modules.find((m) => m.topics.some((t) => t.topic_id === issue.topicId));
    if (!module) return;
    setOpen((current) => ({ modules: { ...current?.modules, [module.module_id]: true }, topics: { ...current?.topics, [issue.topicId as string]: true } }));
    setHighlight(issue.topicId);
    window.setTimeout(() => document.getElementById(`topic-${issue.topicId}`)?.scrollIntoView({ behavior: "smooth", block: "center" }), 60);
  };
  const curriculumDone = !issues.some((issue) => !issue.final);

  return (
    <>
      <BuilderHeader courseId={courseId} versionId={versionId} title={course?.title ?? "Course"} status={version.status} step="curriculum" done={{ details: true, curriculum: curriculumDone, final: !issues.some((issue) => issue.final) }} />

      {version.reject_reason && version.status === "draft" && (
        <Alert tone="warning" title="Changes requested" className="mb-6">{version.reject_reason}</Alert>
      )}

      <div className="grid items-start gap-6 lg:grid-cols-[minmax(0,1fr)_340px]">
        <div className="min-w-0 space-y-4">
          <div className="flex flex-wrap items-end justify-between gap-3">
            <div>
              <h2 className="text-xl font-extrabold text-navy-950">Curriculum</h2>
              <p className="text-sm text-slate-500">Learners go top to bottom. Each topic ends with its test; passing it unlocks the next topic.</p>
            </div>
            <div className="flex gap-1">
              <Button variant="ghost" size="sm" onClick={() => setAll(true)}>Expand all</Button>
              <Button variant="ghost" size="sm" onClick={() => setAll(false)}>Collapse all</Button>
            </div>
          </div>

          {version.modules.length === 0 && (
            <EmptyState icon="layers" title="No modules yet" description="A course is modules, each made of topics. Start with the first module." action={editable ? <Button icon="plus" onClick={actions.addModule}>Add module</Button> : undefined} />
          )}
          {version.modules.map((module, index) => (
            <ModuleSection
              key={module.module_id}
              module={module}
              number={index + 1}
              count={version.modules.length}
              open={open}
              highlightTopic={highlight}
              editable={editable}
              actions={actions}
              topicTest={tests.topicTest}
              testPath={(topicId) => `${base}/topics/${topicId}/test`}
              onToggleModule={() => setOpen({ ...open, modules: { ...open.modules, [module.module_id]: !open.modules[module.module_id] } })}
              onToggleTopic={(topicId) => setOpen({ ...open, topics: { ...open.topics, [topicId]: !open.topics[topicId] } })}
            />
          ))}
          {editable && version.modules.length > 0 && (
            <button type="button" onClick={actions.addModule} className="flex h-14 w-full items-center justify-center rounded-2xl border-2 border-dashed border-slate-300 text-[15px] font-bold text-slate-700 transition-colors hover:border-brand-500 hover:text-brand-800">
              + Add module
            </button>
          )}

          <div className="rounded-2xl bg-ink-950 p-1">
            <TestGate test={tests.finalTest} to={`${base}/final-test`} label="Final course test · after every module · passing earns the certificate" needMcq={10} needPrograms={2} editable={editable} dark />
          </div>
        </div>

        <aside className="space-y-4 lg:sticky lg:top-6">
          <PublishPanel issues={issues} loading={tests.isLoading} onGo={goTo} />
          <BuildStats version={version} />
          <p className="rounded-2xl bg-navy-50 p-4 text-[13px] leading-relaxed text-navy-900">
            <strong>Every topic test needs</strong> at least 5 multiple-choice questions and 1 program. The final test needs 10 and 2.
          </p>
          {editable && <Button fullWidth onClick={() => navigate(`${base}/publish`)}>Review &amp; publish</Button>}
        </aside>
      </div>
      {dialogs}
    </>
  );
}
