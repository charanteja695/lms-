import { useMemo, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

import { toApiError } from "@/core/lib/apiError";
import { useNotify } from "@/core/hooks/useNotify";
import { BuilderHeader } from "@/modules/catalog/builder/components/BuilderHeader";
import { BuildStats } from "@/modules/catalog/builder/components/PublishPanel";
import { buildIssues } from "@/modules/catalog/builder/hooks/useBuildIssues";
import { useCourseTests } from "@/modules/catalog/builder/hooks/useCourseTests";
import { useApproveVersionMutation, useGetCourseQuery, useGetVersionQuery, useSubmitVersionMutation } from "@/modules/catalog/courses/api/coursesApi";
import { useCan } from "@/modules/user-management/common/permissions/useCan";
import { Alert, Button, EmptyState, Icon, PageLoader } from "@/shared/ui";

/** The last step: what is left (with a link to each), then publish. Super admins approve their own course here. */
export function PublishPage() {
  const { courseId = "", versionId = "" } = useParams();
  const navigate = useNavigate();
  const notify = useNotify();
  const { can } = useCan();
  const { data: course } = useGetCourseQuery(courseId, { skip: !courseId });
  const { data: version, isLoading } = useGetVersionQuery({ courseId, versionId }, { skip: !courseId || !versionId });
  const tests = useCourseTests(courseId, version);
  const [submit] = useSubmitVersionMutation();
  const [approve] = useApproveVersionMutation();
  const [publishing, setPublishing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const issues = useMemo(() => (version ? buildIssues(version, tests.topicTest, tests.finalTest) : []), [version, tests]);

  if (isLoading) return <PageLoader />;
  if (!version) return <EmptyState icon="alert" title="Course version not found" />;

  const base = `/courses/${courseId}/versions/${versionId}`;
  const canReview = can("content.review");
  const ref = { courseId, versionId };
  const live = version.status === "published";
  const publish = async () => {
    setPublishing(true);
    setError(null);
    try {
      if (version.status === "draft") await submit(ref).unwrap();
      if (canReview) {
        await approve(ref).unwrap();
        notify.success("Course published", "It can now be assigned to batches.");
      } else notify.success("Sent for review", "A reviewer publishes it.");
      navigate(`/courses/${courseId}`);
    } catch (caught) {
      setError(toApiError(caught).message);
    } finally {
      setPublishing(false);
    }
  };

  return (
    <>
      <BuilderHeader courseId={courseId} versionId={versionId} title={course?.title ?? "Course"} status={version.status} step="publish" done={{ details: true, curriculum: !issues.some((i) => !i.final), final: !issues.some((i) => i.final), publish: live }} />
      <div className="grid items-start gap-6 lg:grid-cols-[minmax(0,1fr)_360px]">
        <div className="space-y-4">
          <div>
            <h2 className="text-2xl font-extrabold text-navy-950">{live ? "This course is live" : issues.length ? `${issues.length} ${issues.length === 1 ? "thing" : "things"} left before publishing` : "Ready to publish"}</h2>
            <p className="text-[15px] text-slate-600">{issues.length ? "Fix each one, then publish." : "Every topic has its lessons and test, and the final test is complete."}</p>
          </div>
          {issues.length === 0 ? (
            <div className="flex items-center gap-3 rounded-2xl bg-brand-50 p-5 text-brand-900 ring-1 ring-brand-200">
              <Icon name="check" size={22} />
              <span className="font-semibold">Nothing left to fix.</span>
            </div>
          ) : (
            <ul className="space-y-2">
              {issues.map((issue) => (
                <li key={issue.key} className="flex flex-wrap items-center gap-3 rounded-2xl bg-white p-4 shadow-card ring-1 ring-amber-200">
                  <span className="flex h-7 w-7 items-center justify-center rounded-full bg-amber-100 text-sm font-extrabold text-amber-800">!</span>
                  <span className="min-w-0 flex-1">
                    <span className="block font-semibold text-slate-900">{issue.title}</span>
                    <span className="block text-sm text-slate-600">{issue.text}</span>
                  </span>
                  <Link to={issue.kind === "final" ? `${base}/final-test` : issue.kind === "test" ? `${base}/topics/${issue.topicId}/test` : base} className="text-sm font-bold text-amber-800 hover:text-amber-900">
                    Fix
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </div>
        <aside className="space-y-4">
          <BuildStats version={version} />
          <section className="space-y-3 rounded-2xl bg-white p-5 shadow-card ring-1 ring-slate-200/60">
            <h3 className="text-[15px] font-bold text-navy-950">Publish</h3>
            <p className="text-sm text-slate-600">Published courses can be assigned to batches. Later changes go into a new version, so learners already in the course aren&apos;t disrupted.</p>
            {error && <Alert tone="error">{error}</Alert>}
            {!live && (
              <Button fullWidth size="lg" loading={publishing} disabled={issues.length > 0 || version.status === "in_review" && !canReview} onClick={() => void publish()}>
                {canReview ? "Publish course" : "Send for review"}
              </Button>
            )}
            {issues.length > 0 && !live && <p className="text-[13px] text-amber-800">Fix the items on the left first.</p>}
            {version.status === "in_review" && !canReview && <p className="text-[13px] text-slate-600">Waiting for a reviewer.</p>}
          </section>
        </aside>
      </div>
    </>
  );
}
