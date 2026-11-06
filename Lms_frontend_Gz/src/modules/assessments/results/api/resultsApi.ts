import { baseApi } from "@/core/api/baseApi";
import type { Id, IsoDateTime } from "@/core/api/types";

export interface ResultsTest {
  test_id: Id;
  title: string;
  kind: string;
  pass_mark_percent: number;
}

export interface ResultsRow {
  user_id: Id;
  test_id: Id;
  attempts: number;
  best_percent: number | null;
  best_score: number | null;
  max_score: number | null;
  passed: boolean;
  last_submitted_at: IsoDateTime | null;
}

/** Marks and results of a group of students (e.g. a section), per test, from assessment-service. */
export const resultsApi = baseApi.injectEndpoints({
  endpoints: (build) => ({
    getResultsSummary: build.query<{ tests: ResultsTest[]; rows: ResultsRow[] }, { user_ids: string[]; test_id?: string }>({
      query: (body) => ({ url: "/results/summary", method: "POST", body }),
      providesTags: ["AttemptList"],
    }),
  }),
});

export const { useGetResultsSummaryQuery } = resultsApi;
