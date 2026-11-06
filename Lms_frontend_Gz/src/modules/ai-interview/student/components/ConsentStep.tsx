import { useState } from "react";

import { useNotify } from "@/core/hooks/useNotify";
import { useGetConsentQuery, useGiveConsentMutation, useStartInterviewMutation } from "@/modules/ai-interview/student/api/studentInterviewsApi";
import { Alert, Button, Card, Checkbox, Spinner } from "@/shared/ui";

/** Consent (the server's current text and version), then start: the server sets the end time from here. */
export function ConsentStep({ interviewId, onStarted }: { interviewId: string; onStarted: () => void }) {
  const notify = useNotify();
  const { data: consent, isLoading } = useGetConsentQuery(interviewId);
  const [give, { isLoading: giving }] = useGiveConsentMutation();
  const [start, { isLoading: starting }] = useStartInterviewMutation();
  const [agreed, setAgreed] = useState(false);
  const [recording, setRecording] = useState(false);

  if (isLoading || !consent) return <Spinner />;

  return (
    <Card title="Before you begin">
      <div className="space-y-4 text-sm text-slate-700">
        <p className="whitespace-pre-wrap">{consent.text}</p>
        {consent.instructions && <Alert tone="info">{consent.instructions}</Alert>}
        <Checkbox label="I agree" checked={agreed} onChange={(e) => setAgreed(e.target.checked)} />
        <Checkbox
          label={consent.recording_required ? "I agree to my answers being recorded (required)" : "Record my spoken answers (optional)"}
          checked={recording}
          onChange={(e) => setRecording(e.target.checked)}
        />
        <p className="text-xs text-slate-500">The timer starts when you press Start and can't be paused.</p>
        <div className="flex justify-end">
          <Button
            loading={giving || starting}
            disabled={!agreed || (consent.recording_required && !recording)}
            onClick={async () => {
              try {
                await give({ id: interviewId, version: consent.version, recording }).unwrap();
                await start(interviewId).unwrap();
                onStarted();
              } catch (error) {
                notify.apiError(error, "Couldn't start");
              }
            }}
          >
            Start the interview
          </Button>
        </div>
      </div>
    </Card>
  );
}
