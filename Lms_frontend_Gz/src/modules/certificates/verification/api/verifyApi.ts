import { baseApi } from "@/core/api/baseApi";
import type { IsoDateTime } from "@/core/api/types";

export interface Verification {
  valid: boolean;
  status: string;
  certificate_id: string;
  student_name: string | null;
  course_title: string | null;
  institution_name: string | null;
  issuer: string;
  completion_date: IsoDateTime;
  grade: string | null;
  score_percent: number;
  issued_at: IsoDateTime;
  revoked_at: IsoDateTime | null;
}

/** Public: no sign-in needed (`GET /public/verify/{code}`, rate-limited per IP). */
export const verifyApi = baseApi.injectEndpoints({
  endpoints: (build) => ({
    verifyCertificate: build.query<{ message: string; verification: Verification }, string>({
      query: (code) => `/public/verify/${encodeURIComponent(code)}`,
    }),
  }),
});

export const { useVerifyCertificateQuery } = verifyApi;
