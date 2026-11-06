import { useListCoursesQuery } from "@/modules/catalog/courses/api/coursesApi";
import type { OptionsHook } from "@/shared/ui";

/** Courses for an EntityPicker, searched by title. Shared like user-management/common's useEntityOptions: a read-only picker over catalog's own data. */
export const useCourseOptions: OptionsHook = (search, enabled) => {
  const { data, isFetching } = useListCoursesQuery({ search_text: search || undefined, per_page: 20 }, { skip: !enabled });
  return {
    isFetching,
    options: (data?.items ?? []).map((course) => ({ value: course.course_id, label: course.title, description: course.slug })),
  };
};
