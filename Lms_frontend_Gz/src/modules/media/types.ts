import type { Id, IsoDateTime } from "@/core/api/types";

export type MediaKind = "video" | "image" | "document";
export type MediaStatus = "uploading" | "uploaded" | "processing" | "ready" | "failed" | "archived";

export interface MediaAsset {
  asset_id: Id;
  kind: MediaKind;
  original_filename: string;
  content_type: string;
  byte_size: number | null;
  status: MediaStatus;
  duration_seconds: number | null;
  failed_reason: string | null;
  context_type: string | null;
  archived_at: IsoDateTime | null;
  created_at: IsoDateTime;
}

export interface MediaSummary {
  kinds: { kind: MediaKind; count: number; byte_size: number }[];
  failed: number;
  archived: number;
}

export interface MediaFilters {
  kind?: MediaKind;
  status?: MediaStatus;
  search?: string;
  archived?: boolean;
  page: number;
  per_page: number;
}

export interface UploadTarget {
  url: string;
  fields: Record<string, string>;
  expires_at: IsoDateTime;
}

export interface UploadRequestBody {
  original_filename: string;
  content_type: string;
  byte_size: number;
  context_type?: string;
  context_id?: string;
}

export interface Playback {
  token: string;
  expires_at: IsoDateTime;
  /** Relative to the API base, e.g. "/playback/<token>". */
  playback_url: string;
}
