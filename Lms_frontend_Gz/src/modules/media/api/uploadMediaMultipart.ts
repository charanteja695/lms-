import { env } from "@/core/config/env";
import { store } from "@/app/store";
import { credentialsReceived } from "@/modules/user-management/auth/store/authSlice";

export interface UploadMediaOptions {
  file: File;
  kind: "video" | "pdf" | "image";
  title?: string;
  description?: string;
  courseId?: string;
  moduleId?: string;
  topicId?: string;
  token?: string | null;
  onProgress?: (percent: number) => void;
}

export interface UploadMediaResult {
  asset_id: string;
  url: string;
  public_id: string;
  duration_seconds: number;
  original_filename: string;
  byte_size: number;
}

/**
 * Direct multipart/form-data upload to media-service via API Gateway.
 * Supports large video files up to 5 GB without buffering everything into RAM,
 * with real-time percentage progress and exact backend error extraction.
 */
export async function uploadMediaMultipart(
  options: UploadMediaOptions,
  onAbortHandle?: (abortFn: () => void) => void
): Promise<UploadMediaResult> {
  // Resolve or refresh token if needed
  let authToken = options.token || store.getState().auth.accessToken;
  if (!authToken) {
    try {
      const refreshRes = await fetch(`${env.apiBaseUrl}/auth/refresh-token`, {
        method: "POST",
        headers: {
          Accept: "application/json",
          "X-Session-Transport": "cookie",
        },
        credentials: "include",
      });
      if (refreshRes.ok) {
        const refreshData = await refreshRes.json();
        if (refreshData?.token?.access_token) {
          authToken = refreshData.token.access_token;
          store.dispatch(credentialsReceived({ token: refreshData.token, user: refreshData.user }));
        }
      }
    } catch {
      // Continue and let backend respond if session is missing
    }
  }

  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    if (onAbortHandle) {
      onAbortHandle(() => xhr.abort());
    }

    const endpoint = options.kind === "video" ? "/media/videos" : (options.kind === "image" ? "/media/images" : "/media/documents");
    const url = `${env.apiBaseUrl}${endpoint}`;

    const formData = new FormData();
    formData.append("file", options.file);
    if (options.title) formData.append("title", options.title);
    if (options.description) formData.append("description", options.description);
    if (options.courseId) formData.append("course_id", options.courseId);
    if (options.moduleId) formData.append("module_id", options.moduleId);
    if (options.topicId) {
      formData.append("topic_id", options.topicId);
      formData.append("context_id", options.topicId);
    }
    formData.append("context_type", "topic");

    xhr.upload.onprogress = (event) => {
      if (event.lengthComputable && options.onProgress) {
        const percent = Math.min(99, Math.round((event.loaded / event.total) * 100));
        options.onProgress(percent);
      }
    };

    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        try {
          const res = JSON.parse(xhr.responseText);
          const asset = res.asset || res;
          resolve({
            asset_id: String(asset.asset_id || res.public_id || ""),
            url: res.url || asset.playback_url || "",
            public_id: String(res.public_id || asset.public_id || ""),
            duration_seconds: Number(res.duration_seconds || asset.duration_seconds || 0),
            original_filename: asset.original_filename || options.file.name,
            byte_size: asset.byte_size || options.file.size,
          });
        } catch {
          reject(new Error("Failed to parse media upload response from server."));
        }
      } else {
        let errorDetail = `Upload failed with HTTP ${xhr.status}`;
        try {
          const parsed = JSON.parse(xhr.responseText);
          errorDetail =
            parsed.message ||
            parsed.detail ||
            (parsed.details && parsed.details[0]?.message) ||
            parsed.error ||
            errorDetail;
        } catch {
          if (xhr.statusText) errorDetail = `${errorDetail}: ${xhr.statusText}`;
        }
        reject(new Error(errorDetail));
      }
    };

    xhr.onerror = () => {
      reject(new Error("Network error during file upload. Please verify the gateway connection."));
    };

    xhr.onabort = () => {
      const abortErr = new DOMException("Upload cancelled by user", "AbortError");
      reject(abortErr);
    };

    xhr.open("POST", url, true);
    xhr.withCredentials = true;
    if (authToken) {
      xhr.setRequestHeader("Authorization", `Bearer ${authToken}`);
    }
    // Note: Do NOT set Content-Type header. The browser automatically sets
    // multipart/form-data with the correct boundary parameter.
    xhr.send(formData);
  });
}
