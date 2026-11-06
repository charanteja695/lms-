import { baseApi } from "@/core/api/baseApi";
import type { ResumeDocument } from "@/modules/career/common/types";

/** `GET /public/resumes/{token}` — no token needed; the document is the shared version's frozen snapshot. */
export const publicResumeApi = baseApi.injectEndpoints({
  endpoints: (build) => ({
    getPublicResume: build.query<{ document: ResumeDocument; version_no: number }, string>({
      query: (token) => `/public/resumes/${encodeURIComponent(token)}`,
    }),
  }),
});

export const { useGetPublicResumeQuery } = publicResumeApi;
