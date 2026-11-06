import type { Id, IsoDateTime } from "@/core/api/types";

export interface StoreOffer {
  course_id: Id;
  name: string;
  /** paise, before GST */
  price: number;
  gst: number;
  /** what the learner pays, paise */
  total: number;
  valid_days: number;
}

export interface Checkout {
  provider: string;
  key_id: string | null;
  order_id: string;
  amount: number;
  currency: string;
  seller_name: string;
}

export interface CoursePurchase {
  purchase_id: Id;
  course_id: Id;
  course_name: string;
  valid_days: number;
  amount: number;
  status: "pending" | "paid" | "cancelled";
  paid_at: IsoDateTime | null;
  created_at: IsoDateTime;
  invoice_number: string | null;
}

export interface CourseAccess {
  access_id: Id;
  course_id: Id;
  starts_at: IsoDateTime;
  ends_at: IsoDateTime;
  status: "active" | "expired";
}
