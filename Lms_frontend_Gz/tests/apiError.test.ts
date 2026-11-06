import { describe, expect, it } from "vitest";

import { toApiError } from "./apiError";

describe("toApiError", () => {
  it("normalizes standard backend error body", () => {
    const error = {
      status: 422,
      data: {
        status: "error",
        code: "VALIDATION_FAILED",
        message: "Title is required",
        details: [{ field: "title", code: "REQUIRED", message: "Title is required" }],
        request_id: "req_123",
      },
    };
    const res = toApiError(error);
    expect(res.httpStatus).toBe(422);
    expect(res.code).toBe("VALIDATION_FAILED");
    expect(res.message).toBe("Title is required");
    expect(res.details).toHaveLength(1);
    expect(res.details?.[0]?.field).toBe("title");
  });

  it("handles FastAPI string detail errors (e.g. 405 Method Not Allowed)", () => {
    const error = {
      status: 405,
      data: { detail: "Method Not Allowed" },
    };
    const res = toApiError(error);
    expect(res.httpStatus).toBe(405);
    expect(res.message).toBe("Method Not Allowed");
  });

  it("handles FastAPI array validation error details", () => {
    const error = {
      status: 422,
      data: {
        detail: [
          { loc: ["body", "title"], msg: "String should have at least 3 characters", type: "string_too_short" },
        ],
      },
    };
    const res = toApiError(error);
    expect(res.httpStatus).toBe(422);
    expect(res.code).toBe("VALIDATION_FAILED");
    expect(res.details).toHaveLength(1);
    expect(res.details?.[0]?.field).toBe("title");
    expect(res.details?.[0]?.message).toBe("String should have at least 3 characters");
  });

  it("handles HTTP status codes with empty data", () => {
    const error = {
      status: 403,
      data: {},
    };
    const res = toApiError(error);
    expect(res.httpStatus).toBe(403);
    expect(res.message).toBe("You do not have permission to perform this action.");
  });

  it("handles fetch network error", () => {
    const error = {
      status: "FETCH_ERROR",
      error: "TypeError: Failed to fetch",
    };
    const res = toApiError(error);
    expect(res.code).toBe("NETWORK_ERROR");
  });
});
