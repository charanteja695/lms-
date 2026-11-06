import { baseApi } from "@/core/api/baseApi";
import type { Checkout, CourseAccess, CoursePurchase, StoreOffer } from "@/modules/store/types";

/** The learner store: offers and purchases (billing-service), and what each purchase opened (subscription-service). */
export const storeApi = baseApi.injectEndpoints({
  endpoints: (build) => ({
    getStoreOffers: build.query<{ offers: StoreOffer[]; payments_available: boolean }, void>({
      query: () => "/store/offers",
      transformResponse: (r: { offers: StoreOffer[]; payments_available: boolean }) => ({ offers: r.offers, payments_available: r.payments_available }),
      providesTags: ["Store"],
    }),
    getMyPurchases: build.query<CoursePurchase[], void>({
      query: () => "/store/purchases",
      transformResponse: (r: { purchases: CoursePurchase[] }) => r.purchases,
      providesTags: ["Store"],
    }),
    getMyCourseAccess: build.query<CourseAccess[], void>({
      query: () => "/me/course-access",
      transformResponse: (r: { course_access: CourseAccess[] }) => r.course_access,
      providesTags: ["Store"],
    }),
    buyCourse: build.mutation<{ purchase: CoursePurchase; checkout: Checkout }, { courseId: string; name: string; email?: string | null }>({
      query: ({ courseId, ...body }) => ({ url: `/store/courses/${courseId}/buy`, method: "POST", body }),
      transformResponse: (r: { purchase: CoursePurchase; checkout: Checkout }) => ({ purchase: r.purchase, checkout: r.checkout }),
    }),
    confirmPurchase: build.mutation<CoursePurchase, { purchaseId: string; razorpay_order_id: string; razorpay_payment_id: string; razorpay_signature: string }>({
      query: ({ purchaseId, ...body }) => ({ url: `/store/purchases/${purchaseId}/confirm`, method: "POST", body }),
      transformResponse: (r: { purchase: CoursePurchase }) => r.purchase,
      invalidatesTags: ["Store", "Enrollment", "EnrollmentList"],
    }),
  }),
});

export const { useGetStoreOffersQuery, useGetMyPurchasesQuery, useGetMyCourseAccessQuery, useBuyCourseMutation, useConfirmPurchaseMutation } = storeApi;
