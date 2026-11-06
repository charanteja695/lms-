import { useCourseTitle } from "@/modules/catalog/common/hooks/useCourseTitle";

/** See CourseTitleCell's sibling, user-management/common/components/InstitutionNameCell.tsx, for why this is a real component and plain text, not a link. */
export function CourseTitleCell({ courseId }: { courseId: string }) {
  const { title, isFetching } = useCourseTitle(courseId);
  if (isFetching && !title) return <span className="text-slate-400">Loading…</span>;
  return <span className="text-slate-900">{title ?? courseId}</span>;
}
