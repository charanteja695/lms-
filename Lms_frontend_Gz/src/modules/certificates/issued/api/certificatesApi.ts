import { baseApi } from "@/core/api/baseApi";
import type { ListResult, PageContext, PageParams } from "@/core/api/types";
import type { Certificate, CertificateDetails, CertificateEvent, CertificateFilters } from "@/modules/certificates/issued/types";

export const certificatesApi = baseApi.injectEndpoints({
  endpoints: (build) => ({
    listCertificates: build.query<ListResult<Certificate>, CertificateFilters & PageParams>({
      query: (params) => ({ url: "/certificates", params }),
      transformResponse: (response: { certificates: Certificate[]; page_context: PageContext }) => ({ items: response.certificates, pageContext: response.page_context }),
      providesTags: ["CertificateList"],
    }),
    getCertificate: build.query<Certificate, string>({
      query: (certificateId) => `/certificates/${certificateId}`,
      transformResponse: (response: { certificate: Certificate }) => response.certificate,
      providesTags: (_result, _error, certificateId) => [{ type: "Certificate", id: certificateId }],
    }),
    getCertificateDetails: build.query<CertificateDetails, string>({
      query: (certificateId) => `/certificates/${certificateId}/details`,
      transformResponse: (response: { certificate: CertificateDetails }) => response.certificate,
      providesTags: (_result, _error, certificateId) => [{ type: "Certificate", id: certificateId }],
    }),
    getCertificateEvents: build.query<CertificateEvent[], string>({
      query: (certificateId) => `/certificates/${certificateId}/events`,
      transformResponse: (response: { events: CertificateEvent[] }) => response.events,
      providesTags: (_result, _error, certificateId) => [{ type: "Certificate", id: certificateId }],
    }),
    getCertificateDownload: build.mutation<{ url: string; filename: string; expires_in: number }, string>({
      query: (certificateId) => `/certificates/${certificateId}/download`,
      transformResponse: (response: { download: { url: string; filename: string; expires_in: number } }) => response.download,
    }),
    revokeCertificate: build.mutation<Certificate, { certificateId: string; reason: string }>({
      query: ({ certificateId, reason }) => ({ url: `/certificates/${certificateId}/revoke`, method: "POST", body: { reason } }),
      transformResponse: (response: { certificate: Certificate }) => response.certificate,
      invalidatesTags: (_result, _error, { certificateId }) => [{ type: "Certificate", id: certificateId }, "CertificateList"],
    }),
    regenerateCertificatePdf: build.mutation<Certificate, string>({
      query: (certificateId) => ({ url: `/certificates/${certificateId}/regenerate-pdf`, method: "POST" }),
      transformResponse: (response: { certificate: Certificate }) => response.certificate,
      invalidatesTags: (_result, _error, certificateId) => [{ type: "Certificate", id: certificateId }, "CertificateList"],
    }),
  }),
});

export const {
  useListCertificatesQuery,
  useGetCertificateQuery,
  useGetCertificateDetailsQuery,
  useGetCertificateEventsQuery,
  useGetCertificateDownloadMutation,
  useRevokeCertificateMutation,
  useRegenerateCertificatePdfMutation,
} = certificatesApi;
