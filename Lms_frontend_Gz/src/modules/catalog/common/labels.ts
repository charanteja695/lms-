import type { ContentStatus, ItemType, UnlockMode } from "@/modules/catalog/common/types";
import type { BadgeTone, IconName } from "@/shared/ui";

export const CONTENT_STATUS_LABELS: Record<ContentStatus, string> = {
  draft: "Draft",
  in_review: "In review",
  published: "Published",
  archived: "Archived",
};

export const CONTENT_STATUS_TONES: Record<ContentStatus, BadgeTone> = {
  draft: "gray",
  in_review: "amber",
  published: "green",
  archived: "red",
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

export const UNLOCK_MODE_LABELS: Record<UnlockMode, string> = {
  sequential: "Sequential — finish one topic to unlock the next",
  drip: "Drip — released on the batch's own schedule",
};
