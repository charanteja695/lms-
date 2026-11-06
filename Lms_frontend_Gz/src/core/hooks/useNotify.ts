import { useMemo } from "react";

import { useAppDispatch } from "@/app/hooks";
import { toApiError } from "@/core/lib/apiError";
import { toastAdded } from "@/core/toast/toastSlice";

export function useNotify() {
  const dispatch = useAppDispatch();
  return useMemo(
    () => ({
      success: (title: string, description?: string) => dispatch(toastAdded({ tone: "success", title, description })),
      info: (title: string, description?: string) => dispatch(toastAdded({ tone: "info", title, description })),
      error: (title: string, description?: string) => dispatch(toastAdded({ tone: "error", title, description })),
      /** Show an API failure using the server's own message. */
      apiError: (error: unknown, title = "Action failed") => {
        const apiError = toApiError(error);
        const detail = apiError.details[0]?.message;
        dispatch(toastAdded({ tone: "error", title, description: detail ? `${apiError.message} ${detail}` : apiError.message }));
      },
    }),
    [dispatch],
  );
}
