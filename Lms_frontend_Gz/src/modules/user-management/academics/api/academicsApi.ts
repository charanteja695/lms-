import { baseApi } from "@/core/api/baseApi";
import type { AcademicStructure, ClassSection, DepartmentBody, ProgramBody, SectionBody, SectionStudent } from "@/modules/user-management/academics/types";

type Structure = { academics: AcademicStructure };
type Kind = "departments" | "programs" | "sections";
const structure = (response: Structure) => response.academics;

/** One institution's departments -> programs -> sections. Every change returns the whole structure again. */
export const academicsApi = baseApi.injectEndpoints({
  endpoints: (build) => ({
    getAcademics: build.query<AcademicStructure, string>({
      query: (organizationId) => `/institutions/${organizationId}/academics`,
      transformResponse: structure,
      providesTags: (_result, _error, id) => [{ type: "Academics", id }],
    }),
    createAcademicItem: build.mutation<AcademicStructure, { organizationId: string; kind: Kind; body: DepartmentBody | ProgramBody | SectionBody }>({
      query: ({ organizationId, kind, body }) => ({ url: `/institutions/${organizationId}/${kind}`, method: "POST", body }),
      transformResponse: structure,
      invalidatesTags: (_result, _error, { organizationId }) => [{ type: "Academics", id: organizationId }],
    }),
    updateAcademicItem: build.mutation<AcademicStructure, { organizationId: string; kind: Kind; id: string; body: DepartmentBody | ProgramBody | SectionBody }>({
      query: ({ organizationId, kind, id, body }) => ({ url: `/institutions/${organizationId}/${kind}/${id}`, method: "PATCH", body }),
      transformResponse: structure,
      invalidatesTags: (_result, _error, { organizationId }) => [{ type: "Academics", id: organizationId }, "UserList", "User"],
    }),
    deleteAcademicItem: build.mutation<AcademicStructure, { organizationId: string; kind: Kind; id: string }>({
      query: ({ organizationId, kind, id }) => ({ url: `/institutions/${organizationId}/${kind}/${id}`, method: "DELETE" }),
      transformResponse: structure,
      invalidatesTags: (_result, _error, { organizationId }) => [{ type: "Academics", id: organizationId }],
    }),
    getSectionStudents: build.query<{ section: ClassSection; students: SectionStudent[] }, { organizationId: string; sectionId: string }>({
      query: ({ organizationId, sectionId }) => `/institutions/${organizationId}/sections/${sectionId}/students`,
      providesTags: (_result, _error, { sectionId }) => [{ type: "SectionStudents", id: sectionId }],
    }),
    placeStudents: build.mutation<{ changed: number }, { organizationId: string; sectionId: string; add?: string[]; remove?: string[] }>({
      query: ({ organizationId, sectionId, add = [], remove = [] }) => ({ url: `/institutions/${organizationId}/sections/${sectionId}/students`, method: "PUT", body: { add, remove } }),
      invalidatesTags: (_result, _error, { organizationId }) => [{ type: "Academics", id: organizationId }, "SectionStudents", "UserList", "User"],
    }),
  }),
});

export const {
  useGetAcademicsQuery,
  useCreateAcademicItemMutation,
  useUpdateAcademicItemMutation,
  useDeleteAcademicItemMutation,
  useGetSectionStudentsQuery,
  usePlaceStudentsMutation,
} = academicsApi;
