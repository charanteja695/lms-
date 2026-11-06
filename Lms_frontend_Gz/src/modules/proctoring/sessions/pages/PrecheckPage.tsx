import { useEffect, useState } from "react";
import { useLocation, useNavigate, useParams } from "react-router-dom";

import { useNotify } from "@/core/hooks/useNotify";
import { cn } from "@/core/lib/cn";
import { proctoringSessionStorage } from "@/core/lib/storage";
import { useCreateProctorSessionMutation, useSubmitPrecheckMutation } from "@/modules/proctoring/sessions/api/sessionsApi";
import { CameraCaptureStep } from "@/modules/proctoring/sessions/components/CameraCaptureStep";
import { ConsentStep } from "@/modules/proctoring/sessions/components/ConsentStep";
import { LivenessStep } from "@/modules/proctoring/sessions/components/LivenessStep";
import { ScreenShareStep } from "@/modules/proctoring/sessions/components/ScreenShareStep";
import { SystemCheckStep, type SystemCheckResult } from "@/modules/proctoring/sessions/components/SystemCheckStep";
import type { ProctorSession, Requirements } from "@/modules/proctoring/sessions/types";
import { Alert, Button, EmptyState, Icon, PageHeader, PageLoader } from "@/shared/ui";

type Step = "system" | "camera" | "liveness" | "screen" | "consent" | "result";
type Media = { camera: boolean; microphone: boolean; screen: boolean };

const LABELS: Record<Step, string> = {
  system: "Device check",
  camera: "Face scan",
  liveness: "Face movements",
  screen: "Share screen",
  consent: "Rules",
  result: "Start",
};

/** The steps this test needs, in the order the student meets them. */
function stepsFor(requirements: Requirements): Step[] {
  if (requirements.level !== "strict") return ["system", "consent", "result"];
  return [
    "system",
    "camera",
    ...(requirements.liveness_poses.length ? (["liveness"] as const) : []),
    ...(requirements.screen_share ? (["screen"] as const) : []),
    "consent",
    "result",
  ];
}

function Stepper({ steps, current }: { steps: Step[]; current: Step }) {
  const at = steps.indexOf(current);
  return (
    <ol className="mb-6 flex items-center gap-1 overflow-x-auto pb-1" aria-label="Steps">
      {steps.map((step, i) => (
        <li key={step} className="flex shrink-0 items-center gap-1">
          <span
            className={cn(
              "flex items-center gap-2 rounded-full px-3 py-1.5 text-xs font-semibold ring-1",
              i < at ? "bg-brand-50 text-brand-700 ring-brand-200" : i === at ? "bg-navy-950 text-white ring-navy-950" : "bg-white text-slate-500 ring-slate-200",
            )}
            aria-current={i === at ? "step" : undefined}
          >
            {i < at ? <Icon name="check" size={13} strokeWidth={3} /> : <span className="tabular-nums">{i + 1}</span>}
            {LABELS[step]}
          </span>
          {i < steps.length - 1 && <span className="h-px w-4 bg-slate-300" aria-hidden="true" />}
        </li>
      ))}
    </ol>
  );
}

/**
 * Before a proctored test: device check -> face scan (face and ID photo) -> face movements -> screen (if required) ->
 * rules and agreement -> start. The server checks every step again before the clock can start.
 */
export function PrecheckPage() {
  const { testId = "" } = useParams();
  const location = useLocation();
  const navigate = useNavigate();
  const notify = useNotify();
  // where to go back to afterwards, and what that page needs handed back to it (the instructions page: the attempt)
  const returnState = location.state as { returnTo?: string; attemptId?: string; returnState?: Record<string, unknown> } | null;

  const [createSession, { isLoading: creating }] = useCreateProctorSessionMutation();
  const [submitPrecheck, { isLoading: submitting }] = useSubmitPrecheckMutation();
  const [session, setSession] = useState<ProctorSession | null>(null);
  const [requirements, setRequirements] = useState<Requirements | null>(null);
  const [step, setStep] = useState<Step>("system");
  const [system, setSystem] = useState<SystemCheckResult | null>(null);
  const [failures, setFailures] = useState<Record<string, string>[]>([]);
  const [media, setMedia] = useState<Media>({ camera: false, microphone: false, screen: false });

  useEffect(() => {
    if (!testId) return;
    createSession(testId)
      .unwrap()
      .then((result) => {
        setSession(result.session);
        setRequirements(result.requirements);
      })
      .catch((error: unknown) => notify.apiError(error));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [testId]);

  if (!testId) return <EmptyState icon="alert" title="No test was specified" description="Start a proctored test from My tests." />;
  if (creating || !requirements || !session) return <PageLoader />;

  const steps = stepsFor(requirements);
  const next = (from: Step) => setStep(steps[steps.indexOf(from) + 1] ?? "result");

  // the session this attempt reports against, for the test page (useExamProctoring) to pick up
  const remember = (sessionId: string) => {
    if (!returnState?.attemptId) return;
    proctoringSessionStorage.write(returnState.attemptId, {
      sessionId,
      heartbeatIntervalSeconds: requirements.heartbeat_interval_seconds,
      snapshotIntervalSeconds: requirements.snapshot_interval_seconds,
      screenShare: requirements.screen_share,
      audioIntervalSeconds: requirements.audio_interval_seconds,
      audioClipSeconds: requirements.audio_clip_seconds,
      videoChunkSeconds: requirements.video_recording ? requirements.video_chunk_seconds : 0,
    });
  };

  const finish = async () => {
    if (!system) return;
    // Rejoining a test already running (another tab or browser): the new photos are kept, the check-in itself was done.
    if (session.status === "active") {
      remember(session.session_id);
      setFailures([]);
      setStep("result");
      return;
    }
    try {
      const result = await submitPrecheck({
        sessionId: session.session_id,
        body: {
          consent: true,
          consent_version: requirements.consent_version,
          browser: system.browser,
          fullscreen_supported: system.fullscreenSupported,
          bandwidth_kbps: system.bandwidthKbps,
          camera: media.camera,
          microphone: media.microphone,
          screen_share: media.screen,
        },
      }).unwrap();
      setFailures(result.failures);
      setSession(result.session);
      if (result.failures.length === 0) remember(result.session.session_id);
      setStep("result");
    } catch (error) {
      notify.apiError(error);
    }
  };

  return (
    <>
      <PageHeader title="Before your test" description="A few quick checks so your result counts. It takes about two minutes." />
      <Stepper steps={steps} current={step} />
      {step === "system" && (
        <SystemCheckStep
          onContinue={(result) => {
            setSystem(result);
            next("system");
          }}
        />
      )}
      {step === "camera" && (
        <CameraCaptureStep
          sessionId={session.session_id}
          onContinue={(result) => {
            setMedia((current) => ({ ...current, ...result }));
            next("camera");
          }}
        />
      )}
      {step === "liveness" && <LivenessStep sessionId={session.session_id} poses={requirements.liveness_poses} onContinue={() => next("liveness")} />}
      {step === "screen" && (
        <ScreenShareStep
          onContinue={(screen) => {
            setMedia((current) => ({ ...current, screen }));
            next("screen");
          }}
        />
      )}
      {step === "consent" && <ConsentStep requirements={requirements} onAccept={() => void finish()} />}
      {step === "result" && (
        <div className="space-y-4">
          {failures.length === 0 ? (
            <>
              <Alert tone="success" title="You're ready">
                {requirements.video_recording ? "Recording starts with the test. " : ""}Your test starts as soon as you press Start.
              </Alert>
              <div className="flex justify-end">
                <Button icon="play" onClick={() => navigate(returnState?.returnTo ?? "/my-tests", { replace: true, state: { ...returnState?.returnState, autoStart: true } })}>Start the test</Button>
              </div>
            </>
          ) : (
            <>
              <Alert tone="error" title="A few things need fixing">
                <ul className="list-disc space-y-1 pl-5">
                  {failures.map((failure, index) => (
                    <li key={index}>{failure.message}</li>
                  ))}
                </ul>
              </Alert>
              <div className="flex justify-end">
                <Button loading={submitting} onClick={() => setStep(steps[0] ?? "system")}>
                  Try again
                </Button>
              </div>
            </>
          )}
        </div>
      )}
    </>
  );
}
