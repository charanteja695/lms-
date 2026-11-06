import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Icon, Badge, ConfirmDialog } from "@/shared/ui";
import type { Course } from "@/modules/catalog/courses/types";
import {
  usePublishCourseMutation,
  useUnpublishCourseMutation,
  useDeleteCourseMutation,
  useGetVersionQuery,
} from "@/modules/catalog/courses/api/coursesApi";
import { useListTestsQuery } from "@/modules/assessments/tests/api/testsApi";

interface CourseRowProps {
  course: Course;
  canAuthor: boolean;
  selected: boolean;
  onSelect: (selected: boolean) => void;
  onDuplicate?: (course: Course) => void;
  onArchiveToggle?: (course: Course) => void;
}

export function CourseRow({
  course,
  canAuthor,
  selected,
  onSelect,
  onDuplicate,
  onArchiveToggle,
}: CourseRowProps) {
  const navigate = useNavigate();

  const [menuOpen, setMenuOpen] = useState(false);
  const [unpublishConfirmOpen, setUnpublishConfirmOpen] = useState(false);
  const [deleteConfirmOpen, setDeleteConfirmOpen] = useState(false);

  const [publishCourse] = usePublishCourseMutation();
  const [unpublishCourse, { isLoading: isUnpublishing }] = useUnpublishCourseMutation();
  const [deleteCourse, { isLoading: isDeleting }] = useDeleteCourseMutation();

  const versions = course.versions || [];
  const publishedVersion = versions.find((v) => v.status === "published");
  const draftVersion = versions.find((v) => v.status === "draft" || v.status === "in_review");
  const isPublished = !!publishedVersion;
  const hasDraftChanges = isPublished && !!draftVersion;
  const activeVersion = draftVersion ?? publishedVersion ?? versions[0];

  const { data: versionDetail } = useGetVersionQuery(
    { courseId: course.course_id, versionId: activeVersion?.version_id ?? "" },
    { skip: !activeVersion }
  );

  const { data: testsData } = useListTestsQuery(
    { target_id: course.course_id },
    { skip: !course.course_id }
  );

  const moduleCount = versionDetail?.modules?.length ?? 0;
  const testCount = testsData?.items?.length ?? 0;
  const learnersCount = (course as any).learners_count ?? 0;
  const completionRate = (course as any).completion_rate ?? 0;

  const categoryMatch = course.summary?.match(/^\[(.*?)\]\s*(.*)$/);
  const category = categoryMatch ? categoryMatch[1] : null;

  const formatRelativeDate = (dateStr?: string | null) => {
    if (!dateStr) return "Recently";
    try {
      const date = new Date(dateStr);
      const now = new Date();
      const diffDays = Math.floor((now.getTime() - date.getTime()) / (1000 * 60 * 60 * 24));
      if (diffDays === 0) return "Today";
      if (diffDays === 1) return "Yesterday";
      if (diffDays < 30) return `${diffDays}d ago`;
      return date.toLocaleDateString(undefined, { month: "short", day: "numeric" });
    } catch {
      return "Recently";
    }
  };

  const initials = course.title
    .split(" ")
    .slice(0, 2)
    .map((w) => w[0])
    .join("")
    .toUpperCase();

  return (
    <>
      <tr
        onClick={() => navigate(`/courses/${course.course_id}/edit`)}
        className="group hover:bg-slate-50/80 transition-colors cursor-pointer border-b border-slate-100"
      >
        {/* Checkbox */}
        <td className="py-3.5 pl-4 pr-3 text-center" onClick={(e) => e.stopPropagation()}>
          <input
            type="checkbox"
            checked={selected}
            onChange={(e) => onSelect(e.target.checked)}
            className="h-4 w-4 rounded border-slate-300 text-brand-600 focus:ring-brand-500 cursor-pointer"
          />
        </td>

        {/* Thumbnail + Title + Category */}
        <td className="py-3.5 px-3 min-w-[280px]">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-14 shrink-0 items-center justify-center rounded-lg bg-gradient-to-br from-emerald-600 to-teal-800 text-xs font-bold text-white shadow-2xs">
              {initials}
            </div>
            <div className="min-w-0">
              <span className="font-bold text-xs text-slate-900 group-hover:text-brand-600 transition-colors line-clamp-1">
                {course.title}
              </span>
              {category && (
                <span className="inline-block mt-0.5 rounded bg-slate-100 px-1.5 py-0.2 text-[9px] font-semibold text-slate-600">
                  {category}
                </span>
              )}
            </div>
          </div>
        </td>

        {/* Status */}
        <td className="py-3.5 px-3 whitespace-nowrap">
          {course.archived_at ? (
            <Badge tone="gray">Archived</Badge>
          ) : hasDraftChanges ? (
            <Badge tone="green">Published + Draft</Badge>
          ) : isPublished ? (
            <Badge tone="green">Published</Badge>
          ) : (
            <Badge tone="amber">Draft</Badge>
          )}
        </td>

        {/* Modules / Tests */}
        <td className="py-3.5 px-3 whitespace-nowrap text-xs text-slate-700">
          <span className="font-semibold">{moduleCount}</span> mods ·{" "}
          <span className="font-semibold">{testCount}</span> tests
        </td>

        {/* Learners */}
        <td className="py-3.5 px-3 whitespace-nowrap text-xs font-semibold text-slate-700">
          {learnersCount}
        </td>

        {/* Completion Rate */}
        <td className="py-3.5 px-3 whitespace-nowrap">
          <div className="flex items-center gap-2">
            <div className="h-1.5 w-16 bg-slate-100 rounded-full overflow-hidden">
              <div
                className="h-full bg-emerald-600 rounded-full"
                style={{ width: `${completionRate}%` }}
              />
            </div>
            <span className="text-[11px] font-semibold text-slate-600">{completionRate}%</span>
          </div>
        </td>

        {/* Last Updated */}
        <td className="py-3.5 px-3 whitespace-nowrap text-xs text-slate-500">
          {formatRelativeDate(course.updated_at)}
        </td>

        {/* Actions */}
        <td className="py-3.5 pl-3 pr-4 text-right whitespace-nowrap" onClick={(e) => e.stopPropagation()}>
          <div className="flex items-center justify-end gap-2">
            <button
              type="button"
              onClick={() => navigate(`/courses/${course.course_id}/edit`)}
              className="inline-flex items-center gap-1 rounded-md bg-brand-50 hover:bg-brand-100 text-brand-700 px-2.5 py-1 text-xs font-bold transition-colors"
            >
              <Icon name="edit" className="h-3 w-3" />
              Edit
            </button>

            {canAuthor && (
              <div className="relative">
                <button
                  type="button"
                  onClick={() => setMenuOpen(!menuOpen)}
                  className="flex h-7 w-7 items-center justify-center rounded-lg hover:bg-slate-100 text-slate-500"
                >
                  <Icon name="more" className="h-4 w-4" />
                </button>

                {menuOpen && (
                  <div
                    onClick={(e) => e.stopPropagation()}
                    className="absolute right-0 mt-1 w-48 rounded-xl bg-white p-1 shadow-xl ring-1 ring-slate-900/10 z-30 text-xs font-semibold text-slate-700 text-left"
                  >
                                        <button
                      type="button"
                      onClick={() => {
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
                      className="flex w-full items-center gap-2 rounded-lg px-2.5 py-1.5 hover:bg-slate-50"
                    >
                      <Icon name="eye" className="h-3.5 w-3.5 text-slate-400" />
                      Preview as learner
                    </button>

                    {onDuplicate && (
                      <button
                        type="button"
                        onClick={() => {
                          setMenuOpen(false);
                          onDuplicate(course);
                        }}
                        className="flex w-full items-center gap-2 rounded-lg px-2.5 py-1.5 hover:bg-slate-50"
                      >
                        <Icon name="layers" className="h-3.5 w-3.5 text-slate-400" />
                        Duplicate
                      </button>
                    )}

                    <button
                      type="button"
                      onClick={() => {
                        setMenuOpen(false);
                        if (isPublished) setUnpublishConfirmOpen(true);
                        else publishCourse(course.course_id);
                      }}
                      className="flex w-full items-center gap-2 rounded-lg px-2.5 py-1.5 hover:bg-slate-50"
                    >
                      <Icon name="check" className="h-3.5 w-3.5 text-slate-400" />
                      {isPublished ? "Unpublish" : "Publish"}
                    </button>

                    <div className="my-1 border-t border-slate-100" />

                    {onArchiveToggle && (
                      <button
                        type="button"
                        onClick={() => {
                          setMenuOpen(false);
                          onArchiveToggle(course);
                        }}
                        className="flex w-full items-center gap-2 rounded-lg px-2.5 py-1.5 hover:bg-slate-50"
                      >
                        <Icon name="archive" className="h-3.5 w-3.5 text-slate-400" />
                        {course.archived_at ? "Restore" : "Archive"}
                      </button>
                    )}

                    <button
                      type="button"
                      onClick={() => {
                        setMenuOpen(false);
                        setDeleteConfirmOpen(true);
                      }}
                      className="flex w-full items-center gap-2 rounded-lg px-2.5 py-1.5 hover:bg-rose-50 text-rose-600 font-bold"
                    >
                      <Icon name="trash" className="h-3.5 w-3.5 text-rose-600" />
                      Delete
                    </button>
                  </div>
                )}
              </div>
            )}
          </div>
        </td>
      </tr>

      <ConfirmDialog
        open={unpublishConfirmOpen}
        onCancel={() => setUnpublishConfirmOpen(false)}
        onConfirm={async () => {
          await unpublishCourse(course.course_id).unwrap();
          setUnpublishConfirmOpen(false);
        }}
        options={{
          title: "Unpublish Course?",
          description: "Reverting this course to draft will suspend learner access until republished.",
          confirmLabel: "Unpublish",
          tone: "danger",
        }}
        loading={isUnpublishing}
      />

      <ConfirmDialog
        open={deleteConfirmOpen}
        onCancel={() => setDeleteConfirmOpen(false)}
        onConfirm={async () => {
          await deleteCourse(course.course_id).unwrap();
          setDeleteConfirmOpen(false);
        }}
        options={{
          title: "Delete Course?",
          description: `Are you sure you want to delete "${course.title}"?`,
          confirmLabel: "Delete Course",
          tone: "danger",
        }}
        loading={isDeleting}
      />
    </>
  );
}
