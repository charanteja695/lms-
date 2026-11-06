import type { MediaKind, MediaStatus } from "@/modules/media/types";

export const KIND_LABELS: Record<MediaKind, string> = { video: "Video", document: "PDF", image: "Image" };

export const STATUS_LABELS: Record<MediaStatus, string> = {
  uploading: "Uploading", uploaded: "Uploaded", processing: "Processing", ready: "Ready", failed: "Failed", archived: "Archived",
};

export const STATUS_TONES: Record<MediaStatus, "green" | "amber" | "red" | "gray"> = {
  uploading: "amber", uploaded: "amber", processing: "amber", ready: "green", failed: "red", archived: "gray",
};
