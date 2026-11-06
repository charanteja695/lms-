import { baseApi } from "@/core/api/baseApi";
import type { Language, LanguageAdmin, LanguageCreateBody, LanguageUpdateBody } from "@/modules/code-execution/languages/types";

export const languagesApi = baseApi.injectEndpoints({
  endpoints: (build) => ({
    listLanguages: build.query<Language[], void>({
      query: () => "/languages",
      transformResponse: (response: { languages: Language[] }) => response.languages,
      providesTags: ["LanguageList"],
    }),
    listLanguagesAdmin: build.query<LanguageAdmin[], void>({
      query: () => "/languages/all",
      transformResponse: (response: { languages: LanguageAdmin[] }) => response.languages,
      providesTags: ["LanguageList"],
    }),
    createLanguage: build.mutation<LanguageAdmin, LanguageCreateBody>({
      query: (body) => ({ url: "/languages", method: "POST", body }),
      transformResponse: (response: { language: LanguageAdmin }) => response.language,
      invalidatesTags: ["LanguageList"],
    }),
    updateLanguage: build.mutation<LanguageAdmin, { code: string; body: LanguageUpdateBody }>({
      query: ({ code, body }) => ({ url: `/languages/${code}`, method: "PATCH", body }),
      transformResponse: (response: { language: LanguageAdmin }) => response.language,
      invalidatesTags: ["LanguageList"],
    }),
  }),
});

export const { useListLanguagesQuery, useListLanguagesAdminQuery, useCreateLanguageMutation, useUpdateLanguageMutation } = languagesApi;
