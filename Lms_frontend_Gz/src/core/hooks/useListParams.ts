import { useCallback, useMemo } from "react";
import { useSearchParams } from "react-router-dom";

/**
 * List state (filters, sorting, page) lives in the URL: shareable links, working back button, and a
 * request only when a value actually changes.
 */
export function useListParams<T extends Record<string, string | number | boolean | undefined>>(defaults: { page: number; per_page: number } & Partial<T>) {
  const [searchParams, setSearchParams] = useSearchParams();

  const params = useMemo(() => {
    const result: Record<string, string | number | boolean | undefined> = { ...defaults };
    searchParams.forEach((value, key) => {
      if (key === "page" || key === "per_page") result[key] = Math.max(1, Number(value) || defaults[key]);
      else if (value === "true" || value === "false") result[key] = value === "true";
      else result[key] = value;
    });
    return result as { page: number; per_page: number } & Partial<T>;
  }, [searchParams]);

  const update = useCallback(
    (changes: Partial<T> & { page?: number; per_page?: number }) => {
      setSearchParams(
        (current) => {
          const next = new URLSearchParams(current);
          for (const [key, value] of Object.entries(changes)) {
            if (value === undefined || value === "" || value === null) next.delete(key);
            else next.set(key, String(value));
          }
          // Any filter change starts again at page 1.
          if (!("page" in changes)) next.delete("page");
          return next;
        },
        { replace: true },
      );
    },
    [setSearchParams],
  );

  const reset = useCallback(() => setSearchParams(new URLSearchParams(), { replace: true }), [setSearchParams]);

  return { params, update, reset };
}
