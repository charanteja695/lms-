import { baseApi } from "@/core/api/baseApi";
import type { ListResult, PageContext, PageParams } from "@/core/api/types";
import type { CertificateTemplate, TemplateCreateBody, TemplateFilters, TemplateUpdateBody } from "@/modules/certificates/templates/types";

type TemplateResponse = { template: CertificateTemplate };

export const templatesApi = baseApi.injectEndpoints({
  endpoints: (build) => ({
    listTemplates: build.query<ListResult<CertificateTemplate>, TemplateFilters & PageParams>({
      query: (params) => ({ url: "/certificate-templates", params }),
      transformResponse: (response: { templates: CertificateTemplate[]; page_context: PageContext }) => ({ items: response.templates, pageContext: response.page_context }),
      providesTags: ["CertificateTemplateList"],
    }),
    getTemplate: build.query<CertificateTemplate, string>({
      query: (templateId) => `/certificate-templates/${templateId}`,
      transformResponse: (response: TemplateResponse) => response.template,
      providesTags: (_result, _error, templateId) => [{ type: "CertificateTemplate", id: templateId }],
    }),
    createTemplate: build.mutation<CertificateTemplate, TemplateCreateBody>({
      query: (body) => ({ url: "/certificate-templates", method: "POST", body }),
      transformResponse: (response: TemplateResponse) => response.template,
      invalidatesTags: ["CertificateTemplateList"],
    }),
    updateTemplate: build.mutation<CertificateTemplate, { templateId: string; body: TemplateUpdateBody }>({
      query: ({ templateId, body }) => ({ url: `/certificate-templates/${templateId}`, method: "PATCH", body }),
      transformResponse: (response: TemplateResponse) => response.template,
      invalidatesTags: (_result, _error, { templateId }) => [{ type: "CertificateTemplate", id: templateId }, "CertificateTemplateList"],
    }),
    activateTemplate: build.mutation<CertificateTemplate, string>({
      query: (templateId) => ({ url: `/certificate-templates/${templateId}/activate`, method: "POST" }),
      transformResponse: (response: TemplateResponse) => response.template,
      invalidatesTags: ["CertificateTemplate", "CertificateTemplateList"],
    }),
    archiveTemplate: build.mutation<CertificateTemplate, string>({
      query: (templateId) => ({ url: `/certificate-templates/${templateId}/archive`, method: "POST" }),
      transformResponse: (response: TemplateResponse) => response.template,
      invalidatesTags: (_result, _error, templateId) => [{ type: "CertificateTemplate", id: templateId }, "CertificateTemplateList"],
    }),
    /** The sample PDF comes back as bytes (it needs the bearer token, so it can't be a plain link); handed over as an object URL. */
    previewTemplate: build.mutation<string, string>({
      query: (templateId) => ({
        url: `/certificate-templates/${templateId}/preview`,
        responseHandler: async (response) => (response.ok ? URL.createObjectURL(await response.blob()) : response.json()),
      }),
    }),
  }),
});

export const {
  useListTemplatesQuery,
  useGetTemplateQuery,
  useCreateTemplateMutation,
  useUpdateTemplateMutation,
  useActivateTemplateMutation,
  useArchiveTemplateMutation,
  usePreviewTemplateMutation,
} = templatesApi;
