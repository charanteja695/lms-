import { useCallback, useState } from "react";

import type { ConfirmOptions } from "@/shared/ui";

/**
 * Pairs a ConfirmDialog with the action it guards. The API is called only after the user confirms.
 *
 *   const confirm = useConfirmAction();
 *   confirm.ask({ title, description, confirmLabel }, async (reason) => { await mutate(...) });
 *   <ConfirmDialog {...confirm.dialogProps} />
 */
export function useConfirmAction() {
  const [options, setOptions] = useState<ConfirmOptions | null>(null);
  const [action, setAction] = useState<((reason?: string) => Promise<void>) | null>(null);
  const [loading, setLoading] = useState(false);

  const ask = useCallback((next: ConfirmOptions, run: (reason?: string) => Promise<void>) => {
    setOptions(next);
    setAction(() => run);
  }, []);

  const close = useCallback(() => {
    setOptions(null);
    setAction(null);
  }, []);

  const onConfirm = useCallback(
    async (reason?: string) => {
      if (!action) return;
      setLoading(true);
      try {
        await action(reason);
        close();
      } finally {
        setLoading(false);
      }
    },
    [action, close],
  );

  return { ask, dialogProps: { open: options !== null, options, loading, onConfirm, onCancel: close } };
}
