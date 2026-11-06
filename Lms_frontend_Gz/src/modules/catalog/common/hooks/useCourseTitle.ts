import { useGetCourseQuery } from "@/modules/catalog/courses/api/coursesApi";

/** See user-management/common/hooks/useInstitutionName.ts for why this cross-module read exists. */
export function useCourseTitle(courseId: string) {
  const { data, isFetching } = useGetCourseQuery(courseId, { skip: !courseId });
  return { title: data?.title, slug: data?.slug, isFetching };
}
