import type { FetchBaseQueryError } from "@reduxjs/toolkit/query";
import type { FieldValues, Path, UseFormSetError } from "react-hook-form";

import type { ApiErrorBody, ErrorDetail } from "@/core/api/types";

export interface ApiError {
  httpStatus: number | null;
  code: string;
  message: string;
  details: ErrorDetail[];
  requestId: string | null;
}

function isErrorBody(value: unknown): value is ApiErrorBody {
  return typeof value === "object" && value !== null && (value as ApiErrorBody).status === "error";
}

/** Normalise any RTK Query / fetch failure into the backend's error shape. */
export function toApiError(error: unknown): ApiError {
  const fetchError = error as FetchBaseQueryError | undefined;
  if (fetchError && typeof fetchError === "object" && "status" in fetchError) {
    const httpStatus = typeof fetchError.status === "number" ? fetchError.status : null;
    if ("data" in fetchError && isErrorBody(fetchError.data)) {
      const body = fetchError.data;
      return { httpStatus, code: body.code, message: body.message, details: body.details ?? [], requestId: body.request_id };
    }
    if (fetchError.status === "FETCH_ERROR") {
      return { httpStatus: null, code: "NETWORK_ERROR", message: "Cannot reach the server. Check your connection and try again.", details: [], requestId: null };
    }
    if (httpStatus === 429) {
      return { httpStatus, code: "TOO_MANY_REQUESTS", message: "Too many requests. Please wait a moment and try again.", details: [], requestId: null };
    }
  }
  return { httpStatus: null, code: "UNKNOWN_ERROR", message: "Something went wrong. Please try again.", details: [], requestId: null };
}

/**
 * Put field errors from the API onto the matching form fields. Form values use the same nested shape as
 * the request body, so `personal_info.phone` maps directly. Returns details that matched no field.
 */
export function applyServerErrors<T extends FieldValues>(
  error: ApiError,
  setError: UseFormSetError<T>,
  knownFields: (field: string) => boolean,
): ErrorDetail[] {
  const unmatched: ErrorDetail[] = [];
  let focused = false;
  for (const detail of error.details) {
    const field = detail.field;
    if (field && knownFields(field)) {
      // focus (and so scroll to) the first field with a problem, not the last one
      setError(field as Path<T>, { type: "server", message: detail.message }, { shouldFocus: !focused });
      focused = true;
    } else {
      unmatched.push(detail);
    }
  }
  return unmatched;
}
