import { baseApi } from "@/core/api/baseApi";
import type { ListResult, PageContext, PageParams } from "@/core/api/types";
import type { ApplicationStatus } from "@/modules/job-portal/common/types";

export interface StudentApplication {
  application_id: string;
  student: { user_id: string; name: string; email: string | null };
  job_id: string;
  job_title: string;
  company_name: string | null;
  drive_id: string | null;
  status: ApplicationStatus;
  applied_at: string;
  status_changed_at: string | null;
  ctc: number | null;
  currency: string | null;
}

export interface InstitutionSummary {
  students_applied: number;
  applications: number;
  by_status: Record<string, number>;
  placed: number;
  placed_students: number;
  employers: number;
}

type Page = { applications: StudentApplication[]; page_context: PageContext };
const toList = (r: Page): ListResult<StudentApplication> => ({ items: r.applications, pageContext: r.page_context });

/** An institution's own students only (the server scopes it); read only. */
export const institutionApi = baseApi.injectEndpoints({
  endpoints: (build) => ({
    getInstitutionSummary: build.query<InstitutionSummary, void>({
      query: () => "/institution/summary",
      providesTags: ["Placements"],
    }),
    listStudentApplications: build.query<ListResult<StudentApplication>, { status?: ApplicationStatus; drive_id?: string } & PageParams>({
      query: (params) => ({ url: "/institution/applications", params }),
      transformResponse: toList,
      providesTags: ["Placements"],
    }),
    listPlacements: build.query<ListResult<StudentApplication>, PageParams>({
      query: (params) => ({ url: "/institution/placements", params }),
      transformResponse: toList,
      providesTags: ["Placements"],
    }),
  }),
});

export const { useGetInstitutionSummaryQuery, useListStudentApplicationsQuery, useListPlacementsQuery } = institutionApi;
