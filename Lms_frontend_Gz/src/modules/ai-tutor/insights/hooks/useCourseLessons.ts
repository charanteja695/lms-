import { useGetCourseQuery, useGetVersionQuery } from "@/modules/catalog/courses/api/coursesApi";

export interface LessonOption {
  item_id: string;
  title: string;
  path: string;
}

/**
 * The lessons of a course's latest published version, for naming the expected answers of an evaluation case.
 * ai-tutor indexes catalog's topic_item_id as the lesson id, so these are the ids it expects.
 */
export function useCourseLessons(courseId: string) {
  const { data: course, isError: courseError } = useGetCourseQuery(courseId, { skip: !courseId });
  const published = (course?.versions ?? []).filter((version) => version.status === "published").sort((a, b) => b.version_number - a.version_number)[0];
  const { data: version, isFetching, isError } = useGetVersionQuery({ courseId, versionId: published?.version_id ?? "" }, { skip: !published });
  const lessons: LessonOption[] = (version?.modules ?? []).flatMap((module) =>
    module.topics.flatMap((topic) => topic.items.map((item) => ({ item_id: item.topic_item_id, title: item.title, path: `${module.title} › ${topic.title}` }))),
  );
  return { lessons, isFetching, unavailable: courseError || isError || (course != null && !published) };
}
