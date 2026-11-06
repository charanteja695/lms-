/** Mirrors notification-service's shapes (see its README). */
export type Category = "enrollment" | "learning" | "subscription";

export interface Notification {
  notification_id: string;
  type: string;
  category: Category;
  title: string;
  body: string;
  /** Public ids of what it is about, e.g. enrollment_id. */
  data: Record<string, unknown>;
  read_at: string | null;
  created_at: string;
}

export interface Preference {
  category: Category;
  label: string;
  email_enabled: boolean;
  /** False: always emailed (operational notices); the user cannot turn it off. */
  email_editable: boolean;
}

export interface Template {
  type: string;
  category: Category;
  channel: "in_app" | "email";
  subject: string;
  body: string;
  default_subject: string;
  default_body: string;
  variables: string[];
  is_customised: boolean;
  updated_at: string | null;
}

export type DeliveryStatus = "pending" | "sent" | "failed";

export interface Delivery {
  delivery_id: string;
  notification_id: string;
  recipient_user_id: string;
  channel: string;
  status: DeliveryStatus;
  attempts: number;
  last_error: string | null;
  next_attempt_at: string;
  sent_at: string | null;
  created_at: string;
}
