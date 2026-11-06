import { useListCoursesQuery } from "@/modules/catalog/courses/api/coursesApi";
import type { OptionsHook } from "@/shared/ui";

/** Courses to start a batch on. Only a published course can start one (the server's local course cache only syncs on `course.published`); this narrows the picker to match, as a convenience — the server still validates. */
export const usePublishedCourseOptions: OptionsHook = (search, enabled) => {
  const { data, isFetching } = useListCoursesQuery({ search_text: search || undefined, per_page: 20 }, { skip: !enabled });
  const published = (data?.items ?? []).filter((course) => course.versions.some((version) => version.status === "published"));
  return { isFetching, options: published.map((course) => ({ value: course.course_id, label: course.title, description: course.slug })) };
};
