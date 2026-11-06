import { baseApi } from "@/core/api/baseApi";
import type { ListResult, PageContext, PageParams } from "@/core/api/types";
import type { Invoice, InvoiceDetail, InvoiceStatus } from "@/modules/billing/common/types";

const detail = (r: { invoice: InvoiceDetail }) => r.invoice;
const tags = (id: string) => [{ type: "Invoices" as const, id }, "Invoices" as const];

export interface GatewayOrder {
  payment_id: string;
  order_id: string;
  amount: number;
  currency: string;
}

/** Contacts see their organisation's issued invoices and pay online; billing managers also edit drafts, issue, void, record payments and credit. */
export const invoicesApi = baseApi.injectEndpoints({
  endpoints: (build) => ({
    listInvoices: build.query<ListResult<Invoice>, { status?: InvoiceStatus; organization_id?: string } & PageParams>({
      query: (params) => ({ url: "/invoices", params }),
      transformResponse: (r: { invoices: Invoice[]; page_context: PageContext }) => ({ items: r.invoices, pageContext: r.page_context }),
      providesTags: ["Invoices"],
    }),
    getInvoice: build.query<InvoiceDetail, string>({ query: (id) => `/invoices/${id}`, transformResponse: detail, providesTags: (_r, _e, id) => [{ type: "Invoices", id }] }),
    payOnline: build.mutation<GatewayOrder, { id: string; amount?: number }>({
      query: ({ id, ...body }) => ({ url: `/invoices/${id}/payments/gateway`, method: "POST", body }),
      transformResponse: (r: { gateway_payment: GatewayOrder }) => r.gateway_payment,
      invalidatesTags: (_r, _e, { id }) => tags(id),
    }),
    editDraft: build.mutation<InvoiceDetail, { id: string; lines: { description: string; quantity: number; unit_amount: number }[]; discount: number; note?: string }>({
      query: ({ id, ...body }) => ({ url: `/admin/invoices/${id}`, method: "PUT", body }),
      transformResponse: detail,
      invalidatesTags: (_r, _e, { id }) => tags(id),
    }),
    issueInvoice: build.mutation<InvoiceDetail, string>({ query: (id) => ({ url: `/admin/invoices/${id}/issue`, method: "POST" }), transformResponse: detail, invalidatesTags: (_r, _e, id) => tags(id) }),
    voidInvoice: build.mutation<InvoiceDetail, { id: string; reason: string }>({
      query: ({ id, ...body }) => ({ url: `/admin/invoices/${id}/void`, method: "POST", body }),
      transformResponse: detail,
      invalidatesTags: (_r, _e, { id }) => [...tags(id), "EmployerPlans"],
    }),
    recordPayment: build.mutation<unknown, { id: string; amount: number; reference: string; method?: string }>({
      query: ({ id, ...body }) => ({ url: `/admin/invoices/${id}/payments/manual`, method: "POST", body }),
      invalidatesTags: (_r, _e, { id }) => [...tags(id), "EmployerPlans"],
    }),
    issueCreditNote: build.mutation<unknown, { id: string; taxable_amount: number; reason: string }>({
      query: ({ id, ...body }) => ({ url: `/admin/invoices/${id}/credit-notes`, method: "POST", body }),
      invalidatesTags: (_r, _e, { id }) => tags(id),
    }),
  }),
});

export const {
  useListInvoicesQuery,
  useGetInvoiceQuery,
  usePayOnlineMutation,
  useEditDraftMutation,
  useIssueInvoiceMutation,
  useVoidInvoiceMutation,
  useRecordPaymentMutation,
  useIssueCreditNoteMutation,
} = invoicesApi;
