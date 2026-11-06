import { compact, diffForUpdate } from "@/core/lib/query";
import type { Course, CourseCreateBody, CourseUpdateBody } from "@/modules/catalog/courses/types";

/** Form state for creating/editing a course. Field names match the API body. */
export interface CourseFormValues {
  title: string;
  slug: string;
  summary: string;
  thumbnail_media_id: string;
}

export function emptyCourseForm(): CourseFormValues {
  return { title: "", slug: "", summary: "", thumbnail_media_id: "" };
}

export function courseToForm(course: Course): CourseFormValues {
  return { title: course.title, slug: course.slug, summary: course.summary, thumbnail_media_id: course.thumbnail_media_id ?? "" };
}

export function toCourseCreateBody(values: CourseFormValues): CourseCreateBody {
  return compact({ title: values.title, slug: values.slug, summary: values.summary, thumbnail_media_id: values.thumbnail_media_id }) as CourseCreateBody;
}

export function toCourseUpdateBody(initial: CourseFormValues, values: CourseFormValues): CourseUpdateBody {
  const shape = (v: CourseFormValues) => ({ title: v.title, summary: v.summary, thumbnail_media_id: v.thumbnail_media_id });
  return (diffForUpdate(shape(initial), shape(values)) ?? {}) as CourseUpdateBody;
}

export function isCourseField(field: string): boolean {
  return /^(title|slug|summary|thumbnail_media_id)$/.test(field);
}
