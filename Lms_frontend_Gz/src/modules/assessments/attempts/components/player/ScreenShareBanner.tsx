import { useState } from "react";

import { Alert, Button } from "@/shared/ui";

/** Shown while a test that requires screen sharing is not being shared (stopped, or lost on a reload). */
export function ScreenShareBanner({ screen }: { screen: { required: boolean; sharing: boolean; reshare: () => Promise<string | null> } }) {
  const [error, setError] = useState<string | null>(null);
  const [asking, setAsking] = useState(false);
  if (!screen.required || screen.sharing) return null;

  return (
    <Alert tone="warning" title="Your screen is not being shared" className="mb-4">
      <p>This test needs your entire screen shared until you submit. The time it was not shared is reported to the exam team.</p>
      {error && <p className="mt-1 font-medium">{error}</p>}
      <Button
        className="mt-3"
        size="sm"
        icon="monitor"
        loading={asking}
        onClick={async () => {
          setAsking(true);
          setError(await screen.reshare());
          setAsking(false);
        }}
      >
        Share entire screen
      </Button>
    </Alert>
  );
}
