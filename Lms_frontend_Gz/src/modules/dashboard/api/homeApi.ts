import { baseApi } from "@/core/api/baseApi";

export interface ReadyTest {
  test_id: string;
  title: string;
  can_start: boolean;
  open_attempt_id: string | null;
  opens_at: string | null;
  duration_minutes: number | null;
}

/** What the home page shows a student right now: tests they can start or resume, and tests opening soon. */
export const homeApi = baseApi.injectEndpoints({
  endpoints: (build) => ({
    listHomeTests: build.query<ReadyTest[], void>({
      query: () => "/my/tests",
      transformResponse: (r: { tests: ReadyTest[] }) => r.tests.filter((t) => t.can_start || t.open_attempt_id || t.opens_at),
      providesTags: ["MyTestList"],
    }),
  }),
});

export const { useListHomeTestsQuery } = homeApi;
