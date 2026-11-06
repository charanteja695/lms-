import type { BatchCreateBody } from "@/modules/learning/batches/types";

/** Form state for a new batch. Field names match the API body, except the *_label pairs (display only). */
export interface BatchFormValues {
  course_id: string;
  course_label: string;
  name: string;
  organization_id: string;
  organization_label: string;
}

export function emptyBatchForm(): BatchFormValues {
  return { course_id: "", course_label: "", name: "", organization_id: "", organization_label: "" };
}

export function toBatchCreateBody(values: BatchFormValues): BatchCreateBody {
  return { course_id: values.course_id, name: values.name, organization_id: values.organization_id || null };
}

export function isBatchField(field: string): boolean {
  return /^(course_id|name|organization_id)$/.test(field);
}
