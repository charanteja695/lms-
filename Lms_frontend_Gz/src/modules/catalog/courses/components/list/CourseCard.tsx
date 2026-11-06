import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Icon, Badge, ConfirmDialog } from "@/shared/ui";
import { cn } from "@/core/lib/cn";
import { useNotify } from "@/core/hooks/useNotify";
import type { Course } from "@/modules/catalog/courses/types";
import {
  usePublishCourseMutation,
  useUnpublishCourseMutation,
  useDeleteCourseMutation,
  useGetVersionQuery,
} from "@/modules/catalog/courses/api/coursesApi";
import { useListTestsQuery } from "@/modules/assessments/tests/api/testsApi";

interface CourseCardProps {
  course: Course;
  canAuthor: boolean;
  onDuplicate?: (course: Course) => void;
  onArchiveToggle?: (course: Course) => void;
}

export function CourseCard({ course, canAuthor, onDuplicate, onArchiveToggle }: CourseCardProps) {
  const navigate = useNavigate();
  const notify = useNotify();

  // Dialog & Menu states
  const [menuOpen, setMenuOpen] = useState(false);
  const [unpublishConfirmOpen, setUnpublishConfirmOpen] = useState(false);
  const [deleteConfirmOpen, setDeleteConfirmOpen] = useState(false);

  const [publishCourse] = usePublishCourseMutation();
  const [unpublishCourse, { isLoading: isUnpublishing }] = useUnpublishCourseMutation();
  const [deleteCourse, { isLoading: isDeleting }] = useDeleteCourseMutation();

  // Version status computation
  const versions = course.versions || [];
  const publishedVersion = versions.find((v) => v.status === "published");
  const draftVersion = versions.find((v) => v.status === "draft" || v.status === "in_review");
  const isPublished = !!publishedVersion;
  const hasDraftChanges = isPublished && !!draftVersion;

  const activeVersion = draftVersion ?? publishedVersion ?? versions[0];

  // Live Curriculum Metrics
  const { data: versionDetail } = useGetVersionQuery(
    { courseId: course.course_id, versionId: activeVersion?.version_id ?? "" },
    { skip: !activeVersion }
  );

  // Live Test Metrics
  const { data: testsData } = useListTestsQuery(
    { target_id: course.course_id },
    { skip: !course.course_id }
  );

  const moduleCount = versionDetail?.modules?.length ?? 0;
  const chapterCount = versionDetail?.modules?.reduce((acc, m) => acc + (m.topics?.length ?? 0), 0) ?? 0;
  const testCount = testsData?.items?.length ?? 0;
  const learnersCount = (course as any).learners_count ?? 0;

  // Category & Description
  const categoryMatch = course.summary?.match(/^\[(.*?)\]\s*(.*)$/);
  const category = categoryMatch ? categoryMatch[1] : null;
  const rawSummary = (categoryMatch ? categoryMatch[2] : course.summary)?.trim() || "";
  const isBoilerplate =
    rawSummary.endsWith("- comprehensive course modules.") ||
    rawSummary.endsWith("- comprehensive curriculum, modules, and assessments.") ||
    rawSummary === "No description provided.";
  const displaySummary = isBoilerplate ? "" : rawSummary;

  // Setup Progress (e.g. 8 of 10 steps ready)
  let stepsDone = 0;
  const totalSteps = 4;
  if (course.title) stepsDone++;
  if (moduleCount > 0) stepsDone++;
  if (chapterCount > 0) stepsDone++;
  if (testCount > 0) stepsDone++;
  const setupPercent = Math.round((stepsDone / totalSteps) * 100);

  // Relative Date
  const formatRelativeDate = (dateStr?: string | null) => {
    if (!dateStr) return "Recently";
    try {
      const date = new Date(dateStr);
      const now = new Date();
      const diffMs = now.getTime() - date.getTime();
      const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));
      if (diffDays === 0) return "Today";
      if (diffDays === 1) return "Yesterday";
      if (diffDays < 30) return `${diffDays} days ago`;
      return date.toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" });
    } catch {
      return "Recently";
    }
  };

  // Color generator for thumbnail placeholder
  const getGradientForTitle = (str: string) => {
    const charCode = str.charCodeAt(0) || 65;
    const gradients = [
      "from-emerald-600 to-teal-800",
      "from-teal-600 to-cyan-800",
      "from-emerald-700 to-green-900",
      "from-green-600 to-emerald-800",
    ];
    return gradients[charCode % gradients.length];
  };

  const initials = course.title
    .split(" ")
    .slice(0, 2)
    .map((w) => w[0])
    .join("")
    .toUpperCase();

  const handleEditClick = (e: React.MouseEvent) => {
    e.stopPropagation();
    navigate(`/courses/${course.course_id}/edit`);
  };

  const handleViewClick = (e: React.MouseEvent) => {
    e.stopPropagation();
    navigate(`/courses/${course.course_id}`);
  };

  const handleTogglePublish = async () => {
    try {
      if (isPublished) {
        setUnpublishConfirmOpen(true);
      } else {
        await publishCourse(course.course_id).unwrap();
        notify.success("Course published successfully.");
      }
    } catch (e) {
      notify.apiError(e);
    }
  };

  const handleConfirmUnpublish = async () => {
    try {
      await unpublishCourse(course.course_id).unwrap();
      notify.success("Course reverted to draft.");
      setUnpublishConfirmOpen(false);
    } catch (e) {
      notify.apiError(e);
    }
  };

  const handleConfirmDelete = async () => {
    try {
      await deleteCourse(course.course_id).unwrap();
      notify.success("Course deleted successfully.");
      setDeleteConfirmOpen(false);
    } catch (e) {
      notify.apiError(e);
    }
  };

  return (
    <>
      <article
        onClick={() => navigate(`/courses/${course.course_id}/edit`)}
        className="group relative flex flex-col overflow-hidden rounded-xl bg-white border border-slate-200/90 shadow-2xs transition-all duration-200 hover:-translate-y-0.5 hover:border-brand-500 hover:shadow-sm cursor-pointer"
      >
        {/* Top 16:9 Thumbnail Area */}
        <div className="relative aspect-video w-full overflow-hidden bg-slate-900">
          <div
            className={cn(
              "flex h-full w-full items-center justify-center bg-gradient-to-br font-bold text-white text-3xl tracking-wider select-none",
              getGradientForTitle(course.title)
            )}
          >
            {initials}
          </div>

          {/* Status Badge Overlay */}
          <div className="absolute top-2.5 left-2.5 z-10">
            {course.archived_at ? (
              <Badge tone="gray">Archived</Badge>
            ) : hasDraftChanges ? (
              <span className="inline-flex items-center gap-1.5 rounded-md bg-emerald-700/95 px-2 py-0.5 text-[11px] font-bold text-white shadow-2xs backdrop-blur-xs">
                <span className="h-1.5 w-1.5 rounded-full bg-amber-400" />
                Published + Draft changes
              </span>
            ) : isPublished ? (
              <Badge tone="green">Published</Badge>
            ) : (
              <Badge tone="amber">Draft</Badge>
            )}
          </div>

          {/* Overflow Menu Button */}
          {canAuthor && (
            <div className="absolute top-2.5 right-2.5 z-10">
              <button
                type="button"
                onClick={(e) => {
                  e.stopPropagation();
                  setMenuOpen(!menuOpen);
                }}
                className="flex h-7 w-7 items-center justify-center rounded-lg bg-black/40 hover:bg-black/60 text-white backdrop-blur-xs transition-colors"
                title="Course Actions"
              >
                <Icon name="more" className="h-4 w-4" />
              </button>

              {menuOpen && (
                <div
                  onClick={(e) => e.stopPropagation()}
                  className="absolute right-0 mt-1 w-52 rounded-xl bg-white p-1 shadow-xl ring-1 ring-slate-900/10 z-30 text-xs font-semibold text-slate-700 animate-in fade-in"
                >
                                      <button
                      type="button"
                      onClick={(e) => {
                        e.stopPropagation();
                        setMenuOpen(false);
                        navigate(`/courses/${course.course_id}/edit`);
                      }}
                      className="flex w-full items-center gap-2 rounded-lg px-2.5 py-1.5 hover:bg-slate-50 text-slate-800 font-semibold"
                    >
                      <Icon name="edit" className="h-3.5 w-3.5 text-slate-500" />
                      Edit course
                    </button>

<button
                    type="button"
                    onClick={() => {
                      setMenuOpen(false);
                      navigate(`/courses/${course.course_id}`);
                    }}
                    className="flex w-full items-center gap-2 rounded-lg px-2.5 py-1.5 hover:bg-slate-50 text-left"
                  >
                    <Icon name="eye" className="h-3.5 w-3.5 text-slate-400" />
                    Preview as learner
                  </button>

                  <button
                    type="button"
                    onClick={() => {
                      setMenuOpen(false);
                      navigate(`/courses/${course.course_id}/edit?tab=settings`);
                    }}
                    className="flex w-full items-center gap-2 rounded-lg px-2.5 py-1.5 hover:bg-slate-50 text-left"
                  >
                    <Icon name="edit" className="h-3.5 w-3.5 text-slate-400" />
                    Edit details & settings
                  </button>

                  {onDuplicate && (
                    <button
                      type="button"
                      onClick={() => {
                        setMenuOpen(false);
                        onDuplicate(course);
                      }}
                      className="flex w-full items-center gap-2 rounded-lg px-2.5 py-1.5 hover:bg-slate-50 text-left"
                    >
                      <Icon name="layers" className="h-3.5 w-3.5 text-slate-400" />
                      Duplicate course
                    </button>
                  )}

                  <button
                    type="button"
                    onClick={() => {
                      setMenuOpen(false);
                      handleTogglePublish();
                    }}
                    className="flex w-full items-center gap-2 rounded-lg px-2.5 py-1.5 hover:bg-slate-50 text-left"
                  >
                    <Icon name="check" className="h-3.5 w-3.5 text-slate-400" />
                    {isPublished ? "Unpublish course" : "Publish course"}
                  </button>

                  <div className="my-1 border-t border-slate-100" />

                  {onArchiveToggle && (
                    <button
                      type="button"
                      onClick={() => {
                        setMenuOpen(false);
                        onArchiveToggle(course);
                      }}
                      className="flex w-full items-center gap-2 rounded-lg px-2.5 py-1.5 hover:bg-slate-50 text-left text-slate-700"
                    >
                      <Icon name="archive" className="h-3.5 w-3.5 text-slate-400" />
                      {course.archived_at ? "Restore course" : "Archive course"}
                    </button>
                  )}

                  <button
                    type="button"
                    onClick={() => {
                      setMenuOpen(false);
                      setDeleteConfirmOpen(true);
                    }}
                    className="flex w-full items-center gap-2 rounded-lg px-2.5 py-1.5 hover:bg-rose-50 text-left text-rose-600 font-bold"
                  >
                    <Icon name="trash" className="h-3.5 w-3.5 text-rose-600" />
                    Delete course
                  </button>
                </div>
              )}
            </div>
          )}
        </div>

        {/* Card Content */}
        <div className="flex flex-1 flex-col justify-between p-4 bg-white">
          <div className="space-y-2">
            {/* Category tag */}
            {category && (
              <span className="inline-block rounded-md bg-slate-100 px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider text-slate-600">
                {category}
              </span>
            )}

            {/* Course Title */}
            <h3
              title={course.title}
              className="line-clamp-2 text-sm font-bold text-slate-900 group-hover:text-brand-600 transition-colors"
            >
              {course.title}
            </h3>

            {/* Description */}
            {displaySummary && (
              <p className="line-clamp-2 text-xs text-slate-500 leading-relaxed">
                {displaySummary}
              </p>
            )}

            {/* Stats row with small icons */}
            <div className="flex items-center gap-4 py-2 text-[11px] text-slate-600 border-t border-slate-100">
              <span className="flex items-center gap-1 font-semibold" title="Modules">
                <Icon name="layers" className="h-3.5 w-3.5 text-slate-400" />
                {moduleCount} {moduleCount === 1 ? "Mod" : "Mods"}
              </span>

              <span className="flex items-center gap-1 font-semibold" title="Chapters">
                <Icon name="fileText" className="h-3.5 w-3.5 text-slate-400" />
                {chapterCount} Ch
              </span>

              <span className="flex items-center gap-1 font-semibold" title="Assessments">
                <Icon name="clipboardCheck" className="h-3.5 w-3.5 text-slate-400" />
                {testCount} Tests
              </span>

              <span className="flex items-center gap-1 font-semibold ml-auto" title="Enrolled Learners">
                <Icon name="briefcase" className="h-3.5 w-3.5 text-slate-400" />
                {learnersCount}
              </span>
            </div>

            {/* Setup progress bar (hide when 100%) */}
            {setupPercent < 100 && (
              <div className="space-y-1 pt-1 pb-1">
                <div className="flex items-center justify-between text-[11px]">
                  <span className="font-semibold text-slate-500">Setup progress</span>
                  <span className="font-bold text-brand-700">{stepsDone} of {totalSteps} steps ready</span>
                </div>
                <div className="h-1.5 w-full rounded-full bg-slate-100 overflow-hidden">
                  <div
                    className="h-full bg-brand-600 rounded-full transition-all duration-300"
                    style={{ width: `${setupPercent}%` }}
                  />
                </div>
              </div>
            )}
          </div>

          {/* Footer Actions */}
          <div className="pt-3 mt-3 border-t border-slate-100 space-y-2">
            <div className="flex items-center justify-between text-[11px] text-slate-400">
              <span>Updated {formatRelativeDate(course.updated_at)}</span>
            </div>

            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={handleEditClick}
                className="flex-1 flex items-center justify-center gap-1.5 rounded-lg bg-brand-600 hover:bg-brand-700 py-2 text-xs font-bold text-white shadow-2xs transition-colors"
              >
                <Icon name="edit" className="h-3.5 w-3.5" />
                Edit Course
              </button>

              <button
                type="button"
                onClick={handleViewClick}
                className="flex items-center justify-center gap-1 rounded-lg border border-slate-200 bg-white hover:bg-slate-50 px-3 py-2 text-xs font-semibold text-slate-700 transition-colors"
              >
                <Icon name="eye" className="h-3.5 w-3.5 text-slate-400" />
                View
              </button>
            </div>
          </div>
        </div>
      </article>

      {/* Confirmation Dialogs */}
      <ConfirmDialog
        open={unpublishConfirmOpen}
        onCancel={() => setUnpublishConfirmOpen(false)}
        onConfirm={handleConfirmUnpublish}
        options={{
          title: "Unpublish Course?",
          description:
            learnersCount > 0
              ? `${learnersCount} learners are currently enrolled. Reverting to draft will suspend learner access until republished.`
              : "Reverting this course to draft will hide it from the catalogue and prevent new enrollments.",
          confirmLabel: "Unpublish",
          tone: "danger",
        }}
        loading={isUnpublishing}
      />

      <ConfirmDialog
        open={deleteConfirmOpen}
        onCancel={() => setDeleteConfirmOpen(false)}
        onConfirm={handleConfirmDelete}
        options={{
          title: "Delete Course?",
          description:
            learnersCount > 0
              ? `Warning: ${learnersCount} learners have enrolled or completed this course. Deleting will permanently erase all curriculum data.`
              : `Are you sure you want to permanently delete "${course.title}"? This action cannot be undone.`,
          confirmLabel: "Delete Course",
          tone: "danger",
        }}
        loading={isDeleting}
      />
    </>
  );
}
