import { store } from "@/app/store";
import { refreshSession } from "@/core/api/baseApi";
import { env } from "@/core/config/env";
import { type ApiError, toApiError } from "@/core/lib/apiError";
import { buildQueryString } from "@/core/lib/query";

/**
 * Authenticated file download (CSV exports, import template, job files). Files are streamed by the
 * browser into a Blob and saved, so tokens never appear in URLs or browser history.
 */
async function fetchFile(path: string, params: Record<string, unknown>): Promise<Response> {
  const url = `${env.apiBaseUrl}${path}${Object.keys(params).length ? `?${buildQueryString(params)}` : ""}`;

  const request = () =>
    fetch(url, {
      headers: { Authorization: `Bearer ${store.getState().auth.accessToken ?? ""}` },
    });

  let response = await request();
  if (response.status === 401) {
    const refreshed = await refreshSession({
      getState: store.getState,
      dispatch: store.dispatch,
      signal: new AbortController().signal,
      abort: () => undefined,
      extra: undefined,
      endpoint: "download",
      type: "mutation",
    });
    if (refreshed) response = await request();
  }

  if (!response.ok) {
    let body: unknown = null;
    try {
      body = await response.json();
    } catch {
      /* not JSON */
    }
    throw toApiError({ status: response.status, data: body }) satisfies ApiError;
  }

  return response;
}

export async function downloadFile(path: string, params: Record<string, unknown> = {}, fallbackName = "download.csv"): Promise<void> {
  const response = await fetchFile(path, params);
  const blob = await response.blob();
  const disposition = response.headers.get("Content-Disposition") ?? "";
  const filename = /filename="?([^";]+)"?/i.exec(disposition)?.[1] ?? fallbackName;
  const objectUrl = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = objectUrl;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  setTimeout(() => URL.revokeObjectURL(objectUrl), 1_000);
}

/** Open an authenticated file (a PDF preview) in a new tab instead of saving it. */
export async function openFile(path: string, params: Record<string, unknown> = {}): Promise<void> {
  const tab = window.open("", "_blank");
  try {
    const blob = await (await fetchFile(path, params)).blob();
    const objectUrl = URL.createObjectURL(blob);
    if (tab) tab.location.href = objectUrl;
    else window.location.assign(objectUrl);
    setTimeout(() => URL.revokeObjectURL(objectUrl), 60_000);
  } catch (error) {
    tab?.close();
    throw error;
  }
}
