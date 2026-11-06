import type { CourseRequestCreateBody } from "@/modules/subscriptions/course-requests/types";

/** Form state for a new course request. Field names match the API body, except course_label (display only). */
export interface CourseRequestFormValues {
  course_id: string;
  course_label: string;
  requested_seats: string;
  requested_term_days: string;
}

export function emptyCourseRequestForm(): CourseRequestFormValues {
  return { course_id: "", course_label: "", requested_seats: "50", requested_term_days: "365" };
}

export function toCourseRequestCreateBody(values: CourseRequestFormValues): CourseRequestCreateBody {
  return { course_id: values.course_id, requested_seats: Number(values.requested_seats), requested_term_days: Number(values.requested_term_days) };
}

export function isCourseRequestField(field: string): boolean {
  return /^(course_id|requested_seats|requested_term_days)$/.test(field);
}
