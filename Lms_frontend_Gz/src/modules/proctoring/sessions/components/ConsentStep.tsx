import { useState } from "react";

import type { Requirements } from "@/modules/proctoring/sessions/types";
import { Alert, Button, Card, Checkbox, Icon, type IconName } from "@/shared/ui";

function Rule({ icon, title, children }: { icon: IconName; title: string; children: string }) {
  return (
    <li className="flex gap-3 rounded-xl border border-slate-200/80 bg-white p-3.5">
      <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-accent-50 text-accent-600 ring-1 ring-accent-100">
        <Icon name={icon} size={17} />
      </span>
      <span>
        <span className="block text-sm font-semibold text-navy-950">{title}</span>
        <span className="block text-sm text-slate-500">{children}</span>
      </span>
    </li>
  );
}

/** The test's rules and what is recorded; the student agrees before the test can start. */
export function ConsentStep({ requirements, onAccept }: { requirements: Requirements; onAccept: () => void }) {
  const [checked, setChecked] = useState(false);
  const strict = requirements.level === "strict";

  return (
    <Card title="Test rules and agreement" description="Read these once. Breaking a rule is recorded and may be reviewed by a person.">
      <div className="space-y-5">
        <ul className="grid gap-3 sm:grid-cols-2">
          <Rule icon="monitor" title="Stay in this tab, in fullscreen">Switching tabs or windows, or leaving fullscreen, is recorded.</Rule>
          <Rule icon="ban" title="No copy and paste">Copying, pasting and right-click are blocked and recorded.</Rule>
          {strict && <Rule icon="video" title="You are recorded">Your camera and microphone are recorded for the whole test. The recording is saved when you submit.</Rule>}
          {strict && <Rule icon="user" title="Stay in view, alone">Keep your face in view. Other people, voices or a phone are flagged.</Rule>}
          {requirements.screen_share && <Rule icon="monitor" title="Your screen is shared">Your entire screen is shared and captured for the whole test.</Rule>}
          <Rule icon="shield" title="Fair review">A low-risk attempt is cleared automatically; anything else is checked by a person, and you may appeal once.</Rule>
        </ul>
        {!requirements.consent_version && <Alert tone="warning">No current consent text is configured.</Alert>}
        <div className="rounded-xl bg-slate-50 p-4 ring-1 ring-slate-200">
          <Checkbox
            label="I agree to these terms and conditions, and to being monitored and recorded during this test."
            checked={checked}
            onChange={(event) => setChecked(event.target.checked)}
          />
        </div>
        <div className="flex justify-end">
          <Button icon="check" disabled={!checked} onClick={onAccept}>
            I agree, continue
          </Button>
        </div>
      </div>
    </Card>
  );
}
