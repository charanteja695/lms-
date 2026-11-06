/** Serialise query params, skipping empty values so the backend never receives `?role=`. */
export function buildQueryString(params: Record<string, unknown>): string {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value === undefined || value === null || value === "") continue;
    if (Array.isArray(value)) value.forEach((item) => search.append(key, String(item)));  // ?status=a&status=b, as FastAPI reads lists
    else search.set(key, String(value));
  }
  return search.toString();
}

/** Remove undefined/empty values (used for request bodies of create forms). */
export function compact<T>(value: T): T {
  if (Array.isArray(value)) return value.map(compact) as T;
  if (value && typeof value === "object") {
    const result: Record<string, unknown> = {};
    for (const [key, item] of Object.entries(value)) {
      const cleaned = compact(item);
      if (cleaned === undefined || cleaned === "") continue;
      if (cleaned && typeof cleaned === "object" && !Array.isArray(cleaned) && Object.keys(cleaned).length === 0) continue;
      result[key] = cleaned;
    }
    return result as T;
  }
  return value;
}

/**
 * Build a partial-update body: only fields whose value changed. Empty strings become null (clear the value).
 * Arrays are compared as a whole and sent whole when changed (e.g. guardians).
 */
export function diffForUpdate(initial: unknown, current: unknown): unknown {
  const normalise = (value: unknown) => (value === "" ? null : value);
  if (Array.isArray(current) || Array.isArray(initial)) {
    return JSON.stringify(compact(initial)) === JSON.stringify(compact(current)) ? undefined : compact(current);
  }
  if (current && typeof current === "object") {
    const before = (initial && typeof initial === "object" ? initial : {}) as Record<string, unknown>;
    const result: Record<string, unknown> = {};
    for (const [key, value] of Object.entries(current)) {
      const changed = diffForUpdate(before[key], value);
      if (changed !== undefined) result[key] = changed;
    }
    return Object.keys(result).length ? result : undefined;
  }
  return normalise(initial ?? null) === normalise(current ?? null) ? undefined : normalise(current);
}
