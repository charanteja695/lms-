import { useState } from "react";

import { useNotify } from "@/core/hooks/useNotify";
import { toApiError } from "@/core/lib/apiError";
import { useAnswerTurnAudioMutation, useAnswerTurnMutation, type TurnPair } from "@/modules/ai-interview/student/api/studentInterviewsApi";
import { useVoiceAnswer } from "@/modules/ai-interview/student/hooks/useVoiceAnswer";
import { Alert, Button, Checkbox, Textarea } from "@/shared/ui";

/** Typed or spoken answer. Each send has its own Idempotency-Key: a retry replays the same turn, never records two. */
export function AnswerBox({ interviewId, onReply }: { interviewId: string; onReply: (pair: TurnPair) => void }) {
  const notify = useNotify();
  const [answer, { isLoading: sending }] = useAnswerTurnMutation();
  const [answerAudio, { isLoading: uploading }] = useAnswerTurnAudioMutation();
  const voice = useVoiceAnswer();
  const [text, setText] = useState("");
  const [speak, setSpeak] = useState(false);
  const [voiceOff, setVoiceOff] = useState(false);

  const handle = async (work: () => Promise<TurnPair>) => {
    try {
      const pair = await work();
      if (pair.audio && pair.audio_type) void new Audio(`data:${pair.audio_type};base64,${pair.audio}`).play().catch(() => undefined);
      onReply(pair);
      setText("");
    } catch (error) {
      if (toApiError(error).code === "SPEECH_UNAVAILABLE") {
        setVoiceOff(true);
        notify.error("Voice isn't available", "Type your answer instead.");
      } else notify.apiError(error);
    }
  };

  return (
    <div className="space-y-2 border-t border-slate-200 bg-white p-3">
      {voice.error && <Alert tone="warning">{voice.error}</Alert>}
      <Textarea aria-label="Your answer" rows={3} maxLength={8000} value={text} placeholder="Type your answer…" onChange={(e) => setText(e.target.value)} />
      <div className="flex flex-wrap items-center justify-between gap-2">
        <Checkbox label="Read the questions aloud" checked={speak} onChange={(e) => setSpeak(e.target.checked)} />
        <div className="flex gap-2">
          {!voiceOff && (
            <Button
              variant={voice.recording ? "danger" : "secondary"}
              loading={uploading}
              onClick={async () => {
                if (!voice.recording) return void voice.start();
                const audio = await voice.stop();
                if (audio) await handle(() => answerAudio({ id: interviewId, audio, want_audio: speak, key: crypto.randomUUID() }).unwrap());
              }}
            >
              {voice.recording ? "Stop and send" : "Answer by voice"}
            </Button>
          )}
          <Button loading={sending} disabled={!text.trim() || voice.recording} onClick={() => void handle(() => answer({ id: interviewId, text: text.trim(), want_audio: speak, key: crypto.randomUUID() }).unwrap())}>
            Send answer
          </Button>
        </div>
      </div>
    </div>
  );
}
