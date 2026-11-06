import { baseApi } from "@/core/api/baseApi";

export interface AssessmentLanguage {
  code: string;
  name: string;
  version: string;
}

/**
 * The same `GET /languages` code-execution-service exposes (coding/SQL questions reference its
 * language codes directly — see questions/bodyTypes.ts's CodingBody). A separate endpoint
 * definition in this module's own `api/`, rather than importing code-execution's, per rule 2
 * ("API calls only through api/") and rule 5 (no cross-module component imports); RTK Query
 * caches it under the same "LanguageList" tag either way.
 */
export const assessmentLanguagesApi = baseApi.injectEndpoints({
  endpoints: (build) => ({
    listAssessmentLanguages: build.query<AssessmentLanguage[], void>({
      query: () => "/languages",
      transformResponse: (response: { languages: AssessmentLanguage[] }) => response.languages,
      providesTags: ["LanguageList"],
    }),
  }),
});

export const { useListAssessmentLanguagesQuery } = assessmentLanguagesApi;
