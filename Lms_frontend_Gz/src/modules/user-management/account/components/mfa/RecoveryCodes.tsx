import { useState } from "react";

import { useNotify } from "@/core/hooks/useNotify";
import { Alert, Button } from "@/shared/ui";

export function RecoveryCodes({ codes, onDone }: { codes: string[]; onDone: () => void }) {
  const notify = useNotify();
  const [confirmed, setConfirmed] = useState(false);
  const copy = async () => {
    await navigator.clipboard.writeText(codes.join("\n"));
    notify.success("Recovery codes copied");
  };
  return (
    <div className="max-w-lg space-y-4">
      <Alert tone="warning" title="Save your recovery codes now">
        Each code signs you in once if you lose your phone. They will not be shown again.
      </Alert>
      <ul className="grid grid-cols-2 gap-2 rounded-lg border border-slate-200 bg-slate-50 p-4 font-mono text-sm">
        {codes.map((code) => (
          <li key={code}>{code}</li>
        ))}
      </ul>
      <div className="flex flex-wrap items-center gap-3">
        <Button variant="secondary" icon="download" onClick={() => void copy()}>
          Copy codes
        </Button>
        <label className="flex items-center gap-2 text-sm text-slate-700">
          <input type="checkbox" checked={confirmed} onChange={(event) => setConfirmed(event.target.checked)} className="h-4 w-4 rounded border-slate-300 text-brand-600" />
          I have saved these codes
        </label>
      </div>
      <Button disabled={!confirmed} onClick={onDone}>
        Done
      </Button>
    </div>
  );
}
