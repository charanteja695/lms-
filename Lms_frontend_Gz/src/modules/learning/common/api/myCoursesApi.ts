import { baseApi } from "@/core/api/baseApi";

export interface MyCourse {
  course_id: string;
  title: string;
  batch_id?: string;
  enrollment_id?: string;
}

interface EnrollmentRow {
  enrollment_id: string;
  batch_id: string;
}

/**
 * The courses the signed-in student is actively enrolled in (their enrolments' batches' courses), for other
 * modules' course pickers (the AI tutor, support tickets). Read-only and owned here, like the other
 * common/ resolvers in rule 5 of src/modules/README.md.
 */
export const myCoursesApi = baseApi.injectEndpoints({
  endpoints: (build) => ({
    listMyCourses: build.query<MyCourse[], void>({
      async queryFn(_arg, _api, _extra, baseQuery) {
        const enrollments = await baseQuery({ url: "/enrollments", params: { status: "active", per_page: 100 } });
        if (enrollments.error) return { error: enrollments.error };
        const enrollmentsList = ((enrollments.data as { enrollments?: EnrollmentRow[] }).enrollments ?? []);
        const batchIds = [...new Set(enrollmentsList.map((row) => row.batch_id))];
        const batches = await Promise.all(batchIds.map((batchId) => baseQuery(`/batches/${batchId}`)));
        const courses = new Map<string, MyCourse>();
        for (const result of batches) {
          const batch = (result.data as { batch?: { batch_id: string; course_id: string; title: string } } | undefined)?.batch;
          if (batch) {
            const matchingEnrollment = enrollmentsList.find((e) => String(e.batch_id) === String(batch.batch_id));
            courses.set(batch.course_id, {
              course_id: batch.course_id,
              title: batch.title,
              batch_id: batch.batch_id,
              enrollment_id: matchingEnrollment?.enrollment_id,
            });
          }
        }
        return { data: [...courses.values()] };
      },
      providesTags: ["EnrollmentList"],
    }),
  }),
});

export const { useListMyCoursesQuery } = myCoursesApi;
