import type { BatchStatus, EnrollmentStatus, ItemType } from "@/modules/learning/common/types";
import type { BadgeTone, IconName } from "@/shared/ui";

export const BATCH_STATUS_LABELS: Record<BatchStatus, string> = {
  active: "Active",
  archived: "Archived",
};

export const BATCH_STATUS_TONES: Record<BatchStatus, BadgeTone> = {
  active: "green",
  archived: "gray",
};

export const ENROLLMENT_STATUS_LABELS: Record<EnrollmentStatus, string> = {
  active: "Active",
  completed: "Completed",
  withdrawn: "Withdrawn",
};

export const ENROLLMENT_STATUS_TONES: Record<EnrollmentStatus, BadgeTone> = {
  active: "green",
  completed: "blue",
  withdrawn: "gray",
};

export const ITEM_TYPE_LABELS: Record<ItemType, string> = {
  video: "Video",
  pdf: "PDF",
  notes: "Notes",
  practice: "Practice",
  quiz: "Quiz",
};

export const ITEM_TYPE_ICONS: Record<ItemType, IconName> = {
  video: "video",
  pdf: "fileText",
  notes: "fileText",
  practice: "terminal",
  quiz: "helpCircle",
};
