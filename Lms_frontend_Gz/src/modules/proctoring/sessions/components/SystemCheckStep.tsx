import { useEffect, useState } from "react";

import { Badge, Button, Card } from "@/shared/ui";

export interface SystemCheckResult {
  browser: string;
  fullscreenSupported: boolean;
  bandwidthKbps: number;
}

function estimateBandwidthKbps(): number {
  const connection = (navigator as unknown as { connection?: { downlink?: number } }).connection;
  return connection?.downlink ? Math.round(connection.downlink * 1000) : 1000;
}

export function SystemCheckStep({ onContinue }: { onContinue: (result: SystemCheckResult) => void }) {
  const [result, setResult] = useState<SystemCheckResult | null>(null);

  useEffect(() => {
    setResult({ browser: navigator.userAgent, fullscreenSupported: document.fullscreenEnabled ?? false, bandwidthKbps: estimateBandwidthKbps() });
  }, []);

  if (!result) return null;

  return (
    <Card title="System check">
      <div className="space-y-3 text-sm">
        <div className="flex items-center justify-between">
          <span className="text-slate-600">Fullscreen support</span>
          <Badge tone={result.fullscreenSupported ? "green" : "red"}>{result.fullscreenSupported ? "Supported" : "Not supported"}</Badge>
        </div>
        <div className="flex items-center justify-between">
          <span className="text-slate-600">Estimated connection</span>
          <Badge tone={result.bandwidthKbps > 0 ? "green" : "gray"}>{result.bandwidthKbps.toLocaleString()} kbps</Badge>
        </div>
        <div className="flex items-center justify-between">
          <span className="text-slate-600">Browser</span>
          <span className="max-w-xs truncate text-xs text-slate-500">{result.browser}</span>
        </div>
      </div>
      <div className="mt-4 flex justify-end">
        <Button onClick={() => onContinue(result)}>Continue</Button>
      </div>
    </Card>
  );
}
