import { baseApi } from "@/core/api/baseApi";
import type { ListResult, PageContext, PageParams } from "@/core/api/types";
import type { ResumeDocument } from "@/modules/career/common/types";
import type { Resume, ResumeCreateBody, ResumeDetail, ResumeOptions, ResumeTemplate, ResumeUpdateBody, ResumeVersion } from "@/modules/career/resumes/types";

const resumeTags = (resumeId: string) => [{ type: "Resume" as const, id: resumeId }, "ResumeList" as const];

export const resumesApi = baseApi.injectEndpoints({
  endpoints: (build) => ({
    getResumeOptions: build.query<ResumeOptions, void>({
      query: () => "/resume-options",
      providesTags: ["CareerProfile"],
    }),
    listResumeTemplates: build.query<ResumeTemplate[], void>({
      query: () => "/resume-templates",
      transformResponse: (response: { templates: ResumeTemplate[] }) => response.templates,
    }),
    listResumes: build.query<ListResult<Resume>, PageParams>({
      query: (params) => ({ url: "/resumes", params }),
      transformResponse: (response: { resumes: Resume[]; page_context: PageContext }) => ({ items: response.resumes, pageContext: response.page_context }),
      providesTags: ["ResumeList"],
    }),
    getResume: build.query<ResumeDetail, string>({
      query: (resumeId) => `/resumes/${resumeId}`,
      providesTags: (_result, _error, resumeId) => [{ type: "Resume", id: resumeId }, "Resume"],
    }),
    createResume: build.mutation<Resume, ResumeCreateBody>({
      query: (body) => ({ url: "/resumes", method: "POST", body }),
      transformResponse: (response: { resume: Resume }) => response.resume,
      invalidatesTags: ["ResumeList"],
    }),
    updateResume: build.mutation<Resume, { resumeId: string; body: ResumeUpdateBody }>({
      query: ({ resumeId, body }) => ({ url: `/resumes/${resumeId}`, method: "PATCH", body }),
      transformResponse: (response: { resume: Resume }) => response.resume,
      invalidatesTags: (_result, _error, { resumeId }) => resumeTags(resumeId),
    }),
    duplicateResume: build.mutation<Resume, string>({
      query: (resumeId) => ({ url: `/resumes/${resumeId}/duplicate`, method: "POST" }),
      transformResponse: (response: { resume: Resume }) => response.resume,
      invalidatesTags: ["ResumeList"],
    }),
    deleteResume: build.mutation<void, string>({
      query: (resumeId) => ({ url: `/resumes/${resumeId}`, method: "DELETE" }),
      invalidatesTags: ["ResumeList"],
    }),
    listResumeVersions: build.query<ResumeVersion[], string>({
      query: (resumeId) => `/resumes/${resumeId}/versions`,
      transformResponse: (response: { versions: ResumeVersion[] }) => response.versions,
      providesTags: (_result, _error, resumeId) => [{ type: "ResumeVersions", id: resumeId }],
    }),
    getResumeVersion: build.query<{ version: ResumeVersion; document: ResumeDocument }, { resumeId: string; versionNo: number }>({
      query: ({ resumeId, versionNo }) => `/resumes/${resumeId}/versions/${versionNo}`,
    }),
    saveResumeVersion: build.mutation<ResumeVersion, { resumeId: string; label?: string; note?: string }>({
      query: ({ resumeId, ...body }) => ({ url: `/resumes/${resumeId}/versions`, method: "POST", body }),
      transformResponse: (response: { version: ResumeVersion }) => response.version,
      invalidatesTags: (_result, _error, { resumeId }) => [{ type: "ResumeVersions", id: resumeId }, ...resumeTags(resumeId)],
    }),
    restoreResumeVersion: build.mutation<void, { resumeId: string; versionNo: number }>({
      query: ({ resumeId, versionNo }) => ({ url: `/resumes/${resumeId}/versions/${versionNo}/restore`, method: "POST" }),
      invalidatesTags: (_result, _error, { resumeId }) => [{ type: "ResumeVersions", id: resumeId }, ...resumeTags(resumeId)],
    }),
  }),
});

export const {
  useGetResumeOptionsQuery,
  useListResumeTemplatesQuery,
  useListResumesQuery,
  useGetResumeQuery,
  useCreateResumeMutation,
  useUpdateResumeMutation,
  useDuplicateResumeMutation,
  useDeleteResumeMutation,
  useListResumeVersionsQuery,
  useGetResumeVersionQuery,
  useSaveResumeVersionMutation,
  useRestoreResumeVersionMutation,
} = resumesApi;
