import { useListCoursesQuery } from "@/modules/catalog/courses/api/coursesApi";
import type { OptionsHook } from "@/shared/ui";

/**
 * Courses to request seats on. Only courses with a published version can actually be requested
 * (the server's local course cache only syncs on `course.published`); this narrows the picker to
 * match, as a convenience — the server is still what validates the request.
 */
export const usePublishedCourseOptions: OptionsHook = (search, enabled) => {
  const { data, isFetching } = useListCoursesQuery({ search_text: search || undefined, per_page: 20 }, { skip: !enabled });
  const published = (data?.items ?? []).filter((course) => course.versions.some((version) => version.status === "published"));
  return { isFetching, options: published.map((course) => ({ value: course.course_id, label: course.title, description: course.slug })) };
};
