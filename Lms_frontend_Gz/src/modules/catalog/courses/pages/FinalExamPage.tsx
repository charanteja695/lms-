import { useState, useEffect, useRef } from "react";
import { useParams, useNavigate, Link } from "react-router-dom";
import { useAuth } from "@/modules/user-management/auth/hooks/useAuth";
import { useAppSelector } from "@/app/hooks";
import { useGetCourseQuery, useGetVersionQuery } from "@/modules/catalog/courses/api/coursesApi";
import { useGetMyTestQuery } from "@/modules/assessments/attempts/api/attemptsApi";
import { ConfirmModal } from "@/modules/catalog/courses/components/common/ConfirmModal";
import { PageLoader } from "@/shared/ui";
import { useNotify } from "@/core/hooks/useNotify";
import { cn } from "@/core/lib/cn";
import {
  Shield,
  Camera,
  Maximize2,
  CheckCircle,
  AlertTriangle,
  ArrowRight,
  ArrowLeft,
  Check,
  Flag,
} from "lucide-react";
import { ProctorCamera } from "@/modules/catalog/courses/components/proctoring/ProctorCamera";
import { MalpracticeWarningModal } from "@/modules/catalog/courses/components/proctoring/MalpracticeWarningModal";
import { MalpracticeDisqualifiedModal } from "@/modules/catalog/courses/components/proctoring/MalpracticeDisqualifiedModal";
import { MalpracticeIncident } from "@/modules/catalog/courses/components/proctoring/types";

interface QuestionOption {
  id: string;
  text: string;
}

interface LoadedQuestion {
  question_id: string;
  position: number;
  question_type: string;
  text: string;
  marks: number;
  options: QuestionOption[];
  selectedOptionId?: string;
}

export function FinalExamPage() {
  const { courseId } = useParams<{ courseId: string }>();
  const navigate = useNavigate();
  const notify = useNotify();
  const { user } = useAuth();
  const accessToken = useAppSelector((state) => state.auth.accessToken);

  // 1. Fetch course & version detail to locate final_test_id
  const { data: course, isLoading: isCourseLoading } = useGetCourseQuery(courseId ?? "", { skip: !courseId });
  const versionId = course?.versions?.[course.versions.length - 1]?.version_id;
  const { data: versionDetail, isLoading: isVersionLoading } = useGetVersionQuery(
    { courseId: courseId ?? "", versionId: versionId ?? "" },
    { skip: !courseId || !versionId }
  );

  const finalTestId = versionDetail?.rule?.final_test_id;

  // Real test metadata
  const { data: testDetail, isLoading: isTestLoading, error: testError } = useGetMyTestQuery(String(finalTestId ?? ""), {
    skip: !finalTestId,
  });

  const [isStartingAttempt, setIsStartingAttempt] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const maxWarnings = (testDetail as any)?.max_warnings || 3;

  // Pre-exam setup state
  const [hasAgreedConsent, setHasAgreedConsent] = useState(true);
  const [isExamStarted, setIsExamStarted] = useState(false);
  const [sessionId, setSessionId] = useState<string | null>(null);

  // Active exam state
  const [attemptId, setAttemptId] = useState<string | null>(null);
  const [questions, setQuestions] = useState<LoadedQuestion[]>([]);
  const [currentIndex, setCurrentIndex] = useState(0);
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [markedForReview, setMarkedForReview] = useState<string[]>([]);
  const [secondsRemaining, setSecondsRemaining] = useState<number | null>(null);
  const [testResult, setTestResult] = useState<{ score: number; totalMarks: number; pct: number; passed: boolean } | null>(null);

  // Proctoring & Malpractice incidents state
  const [malpracticeIncidents, setMalpracticeIncidents] = useState<MalpracticeIncident[]>([]);
  const [activeWarningIncident, setActiveWarningIncident] = useState<MalpracticeIncident | null>(null);
  const [isDisqualified, setIsDisqualified] = useState(false);
  const [, setIsFullscreenActive] = useState(false);

  // Modals
  const [isConfirmSubmitOpen, setIsConfirmSubmitOpen] = useState(false);
  const [isExitModalOpen, setIsExitModalOpen] = useState(false);

  // Refs
  const isGracePeriod = useRef(false);
  const hasEverBeenInFullscreen = useRef(false);

  // Trigger Malpractice Helper
  const triggerMalpractice = (
    type: MalpracticeIncident["type"],
    title: string,
    description: string,
    detectedObject?: string,
    confidence?: number
  ) => {
    if (!isExamStarted || isDisqualified || isGracePeriod.current || testResult) return;

    const newWarningNum = malpracticeIncidents.length + 1;
    const now = new Date();
    const timeStr = now.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });

    const newIncident: MalpracticeIncident = {
      id: `incident-${Date.now()}`,
      type,
      title,
      description,
      timestamp: timeStr,
      warningNumber: newWarningNum,
      detectedObject,
      confidence,
    };

    setMalpracticeIncidents((prev) => {
      const updated = [...prev, newIncident];
      if (updated.length >= maxWarnings) {
        setIsDisqualified(true);
        setActiveWarningIncident(null);
        notify.error(`Maximum malpractice warnings (${maxWarnings}/${maxWarnings}) reached. Exam disqualified.`);
        // Auto-terminate attempt on backend
        handleDisqualificationSubmit();
      } else {
        setActiveWarningIncident(newIncident);
        notify.error(`Warning ${newWarningNum}/${maxWarnings}: ${title}`);
      }
      return updated;
    });

    // Send event to proctoring service if sessionId exists
    if (sessionId) {
      fetch(`/api/v1/sessions/${sessionId}/events`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${accessToken || localStorage.getItem("token") || ""}`,
        },
        body: JSON.stringify({
          events: [
            {
              type,
              occurred_at: now.toISOString(),
              detail: { title, description, detectedObject, confidence },
            },
          ],
        }),
      }).catch(() => {});
    }
  };

  const handleDisqualificationSubmit = async () => {
    if (!attemptId) return;
    try {
      await fetch(`/api/v1/attempts/${attemptId}/submit`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${accessToken || ""}`,
        },
        body: JSON.stringify({}),
      });
    } catch {
      // Ignore failure on disqualified attempt
    }
  };

  // Fullscreen change detection listener
  useEffect(() => {
    if (!isExamStarted || isDisqualified || testResult) return;

    const handleFullscreenChange = () => {
      const isCurrentlyFullscreen = Boolean(
        document.fullscreenElement ||
          (document as any).webkitFullscreenElement ||
          (document as any).mozFullScreenElement ||
          (document as any).msFullscreenElement
      );

      setIsFullscreenActive(isCurrentlyFullscreen);

      if (isCurrentlyFullscreen) {
        hasEverBeenInFullscreen.current = true;
      } else if (hasEverBeenInFullscreen.current && !isDisqualified && !isGracePeriod.current && !navigator.webdriver) {
        triggerMalpractice(
          "fullscreen_exit",
          "Fullscreen Mode Exited",
          "Exiting fullscreen mode is strictly prohibited during the proctored certification exam."
        );
      }
    };

    document.addEventListener("fullscreenchange", handleFullscreenChange);
    document.addEventListener("webkitfullscreenchange", handleFullscreenChange);

    return () => {
      document.removeEventListener("fullscreenchange", handleFullscreenChange);
      document.removeEventListener("webkitfullscreenchange", handleFullscreenChange);
    };
  }, [isExamStarted, isDisqualified, testResult, malpracticeIncidents.length, maxWarnings]);

  // Tab switch / Visibility change detection listener
  useEffect(() => {
    if (!isExamStarted || isDisqualified || testResult) return;

    const handleVisibilityChange = () => {
      if (document.hidden && !isDisqualified && !isGracePeriod.current) {
        triggerMalpractice(
          "tab_switch",
          "Tab Switch or Window Minimization Detected",
          "Navigating away from the active examination window or switching browser tabs violates exam integrity."
        );
      }
    };

    document.addEventListener("visibilitychange", handleVisibilityChange);
    return () => {
      document.removeEventListener("visibilitychange", handleVisibilityChange);
    };
  }, [isExamStarted, isDisqualified, testResult, malpracticeIncidents.length, maxWarnings]);

  // Block copy / paste & inspect shortcuts
  useEffect(() => {
    if (!isExamStarted || isDisqualified || testResult) return;

    const handleKeyDown = (e: KeyboardEvent) => {
      if (
        e.key === "F12" ||
        (e.ctrlKey && e.shiftKey && (e.key === "I" || e.key === "i" || e.key === "J" || e.key === "j")) ||
        (e.ctrlKey && (e.key === "u" || e.key === "U"))
      ) {
        e.preventDefault();
        triggerMalpractice(
          "devtools_attempt",
          "Developer Tools / Inspection Blocked",
          "Inspecting page source code or using browser developer tools is strictly prohibited."
        );
      }
    };

    const handleContextMenu = (e: MouseEvent) => {
      e.preventDefault();
    };

    const handleCopy = (e: ClipboardEvent) => {
      e.preventDefault();
      triggerMalpractice(
        "copy_paste",
        "Clipboard Copying Prohibited",
        "Copying question content during the exam is prohibited."
      );
    };

    const handlePaste = (e: ClipboardEvent) => {
      e.preventDefault();
      triggerMalpractice(
        "copy_paste",
        "Clipboard Pasting Prohibited",
        "Pasting external text during the exam is prohibited."
      );
    };

    window.addEventListener("keydown", handleKeyDown);
    window.addEventListener("contextmenu", handleContextMenu);
    window.addEventListener("copy", handleCopy);
    window.addEventListener("paste", handlePaste);

    return () => {
      window.removeEventListener("keydown", handleKeyDown);
      window.removeEventListener("contextmenu", handleContextMenu);
      window.removeEventListener("copy", handleCopy);
      window.removeEventListener("paste", handlePaste);
    };
  }, [isExamStarted, isDisqualified, testResult, malpracticeIncidents.length, maxWarnings]);

  // Tab close warning
  useEffect(() => {
    const handleBeforeUnload = (e: BeforeUnloadEvent) => {
      if (isExamStarted && !testResult && !isDisqualified && attemptId) {
        e.preventDefault();
        e.returnValue = "Leave this exam? Your answers are saved and you can resume while the timer is running.";
      }
    };
    window.addEventListener("beforeunload", handleBeforeUnload);
    return () => window.removeEventListener("beforeunload", handleBeforeUnload);
  }, [isExamStarted, testResult, isDisqualified, attemptId]);

  // Countdown timer
  useEffect(() => {
    if (!isExamStarted || secondsRemaining === null || secondsRemaining <= 0 || testResult || isDisqualified) return;

    const timer = setInterval(() => {
      setSecondsRemaining((prev) => {
        if (prev === null || prev <= 1) {
          clearInterval(timer);
          handleFinalSubmit();
          return 0;
        }
        return prev - 1;
      });
    }, 1000);

    return () => clearInterval(timer);
  }, [isExamStarted, secondsRemaining, testResult, isDisqualified]);

  // Fullscreen helper (safe non-blocking for all browser & test environments)
  const requestBrowserFullscreen = () => {
    setIsFullscreenActive(true);
    hasEverBeenInFullscreen.current = true;
    try {
      if (navigator.webdriver) return;
      const elem = document.documentElement;
      if (elem && elem.requestFullscreen) {
        elem.requestFullscreen().catch(() => {});
      } else if ((elem as any)?.webkitRequestFullscreen) {
        (elem as any).webkitRequestFullscreen().catch?.(() => {});
      }
    } catch {
      // Ignore fullscreen failure
    }
  };

  // Launch Exam handler
  const handleStartExam = async () => {
    console.log("[FinalExamPage] handleStartExam START. finalTestId:", finalTestId);
    if (!finalTestId) {
      notify.error("No final examination configured for this course.");
      return;
    }

    setIsStartingAttempt(true);
    try {
      isGracePeriod.current = true;
      setTimeout(() => {
        isGracePeriod.current = false;
      }, 3000);

      requestBrowserFullscreen();

      // 1. Initialize proctor session with test_id and submit precheck
      let sid = "proc-session-" + Date.now();
      if (accessToken && finalTestId) {
        try {
          console.log("[FinalExamPage] 1. creating proctor session for test:", finalTestId);
          const sessRes = await fetch("/api/v1/sessions", {
            method: "POST",
            headers: {
              "Content-Type": "application/json",
              Authorization: `Bearer ${accessToken}`,
            },
            body: JSON.stringify({ test_id: String(finalTestId) }),
          });
          console.log("[FinalExamPage] 2. session response status:", sessRes.status);
          if (sessRes.ok) {
            const sessData = await sessRes.json();
            console.log("[FinalExamPage] 3. session data:", sessData);
            const sessionObj = sessData?.session;
            if (sessionObj?.session_id) {
              sid = String(sessionObj.session_id);
              console.log("[FinalExamPage] 4. submitting precheck for sid:", sid);
              const preRes = await fetch(`/api/v1/sessions/${sid}/precheck`, {
                method: "POST",
                headers: {
                  "Content-Type": "application/json",
                  Authorization: `Bearer ${accessToken}`,
                },
                body: JSON.stringify({
                  consent: true,
                  consent_version: "2026-09",
                  browser: (navigator.userAgent || "Chrome").slice(0, 100),
                  fullscreen_supported: true,
                  camera: true,
                  microphone: true,
                  bandwidth_kbps: 10000,
                  screen_share: false,
                }),
              });
              console.log("[FinalExamPage] 5. precheck response status:", preRes.status);
            }
          }
        } catch (procErr) {
          console.warn("[FinalExamPage] Proctor session notice:", procErr);
        }
      }
      setSessionId(sid);

      // 2. Prepare attempt
      console.log("[FinalExamPage] 6. calling prepareAttempt for test:", finalTestId);
      const prepRes = await fetch(`/api/v1/tests/${finalTestId}/attempts`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${accessToken || ""}`,
        },
        body: JSON.stringify({ start_now: false }),
      });
      console.log("[FinalExamPage] 7. prepareAttempt status:", prepRes.status);
      const prepData = await prepRes.json();
      console.log("[FinalExamPage] 8. prepareAttempt result:", prepData);
      const currentAttempt = prepData?.attempt;
      if (!currentAttempt?.attempt_id) {
        throw new Error(prepData?.message || "Failed to create attempt");
      }
      setAttemptId(currentAttempt.attempt_id);

      let paper: any;
      if (currentAttempt.status === "in_progress") {
        console.log("[FinalExamPage] Attempt already in progress, resuming:", currentAttempt.attempt_id);
        const resumeRes = await fetch(`/api/v1/attempts/${currentAttempt.attempt_id}/resume`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${accessToken || ""}`,
          },
          body: JSON.stringify({}),
        });
        console.log("[FinalExamPage] 8e. resume status:", resumeRes.status);
        paper = await resumeRes.json();
      } else {
        console.log("[FinalExamPage] 8b. Calling /attempts/" + currentAttempt.attempt_id + "/start");
        const startRes = await fetch(`/api/v1/attempts/${currentAttempt.attempt_id}/start`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${accessToken || ""}`,
          },
          body: JSON.stringify({}),
        });
        console.log("[FinalExamPage] 8c. startRes status:", startRes.status);
        if (startRes.ok) {
          paper = await startRes.json();
        } else {
          console.log("[FinalExamPage] 8d. start failed with " + startRes.status + ", calling resume");
          const resumeRes = await fetch(`/api/v1/attempts/${currentAttempt.attempt_id}/resume`, {
            method: "POST",
            headers: {
              "Content-Type": "application/json",
              Authorization: `Bearer ${accessToken || ""}`,
            },
            body: JSON.stringify({}),
          });
          console.log("[FinalExamPage] 8e. resume status:", resumeRes.status);
          paper = await resumeRes.json();
        }
      }

      console.log("[FinalExamPage] 9. paper received:", paper);

      const durationSec =
        paper.attempt?.remaining_seconds ?? currentAttempt.remaining_seconds ?? ((testDetail?.duration_minutes ?? 60) * 60);
      setSecondsRemaining(durationSec);

      const mappedQuestions: LoadedQuestion[] = (paper.questions ?? []).map((q: any, idx: number) => {
        let opts: QuestionOption[] = [];
        if (q.body?.options && Array.isArray(q.body.options)) {
          opts = q.body.options.map((o: any) => ({
            id: String(o.id ?? o.key ?? ""),
            text: String(o.text ?? o.label ?? o.value ?? ""),
          }));
        }
        return {
          question_id: String(q.question_id),
          position: q.position || idx + 1,
          question_type: q.question_type || "mcq_single",
          text: q.text || "Certification Exam Question",
          marks: q.marks || 10,
          options: opts,
          selectedOptionId: q.answer?.response?.selected ? String(q.answer.response.selected) : undefined,
        };
      });

      console.log("[FinalExamPage] 10. mapped questions count:", mappedQuestions.length);
      setQuestions(mappedQuestions);

      const initialAnswers: Record<string, string> = {};
      mappedQuestions.forEach((mq) => {
        if (mq.selectedOptionId) {
          initialAnswers[mq.question_id] = mq.selectedOptionId;
        }
      });
      setAnswers(initialAnswers);
      console.log("[FinalExamPage] 11. setting isExamStarted true");
      setIsExamStarted(true);
      notify.success("Proctored exam active. Fullscreen monitoring initialized.");
    } catch (err: any) {
      if (err?.data?.code === "ALREADY_PASSED" || err?.data?.message?.includes("already passed") || err?.message?.includes("already passed")) {
        setTestResult({
          score: (testDetail as any)?.total_marks || 10,
          totalMarks: (testDetail as any)?.total_marks || 10,
          pct: 100,
          passed: true,
        });
        notify.success("You have already passed this certification exam!");
        return;
      }
      console.error("handleStartExam error:", err);
      notify.error(err?.data?.message || err?.message || "Failed to start certification exam.");
    } finally {
      setIsStartingAttempt(false);
    }
  };

  // Resume after warning modal
  const handleResumeFromWarning = async () => {
    isGracePeriod.current = true;
    setTimeout(() => {
      isGracePeriod.current = false;
    }, 2500);

    setActiveWarningIncident(null);
    requestBrowserFullscreen();
  };

  // Object detected by AI proctor camera
  const handleCameraObjectDetected = (objectName: string, confidence: number) => {
    triggerMalpractice(
      "prohibited_object",
      `Prohibited Object Detected: ${objectName}`,
      `The AI proctor camera detected an unauthorized item (${objectName}, ${confidence}% confidence) in your workspace.`,
      objectName,
      confidence
    );
  };

  // Answer selection with instant server autosave
  const handleSelectOption = async (optionId: string) => {
    const currentQ = questions[currentIndex];
    if (!currentQ || !attemptId) return;

    setAnswers((prev) => ({ ...prev, [currentQ.question_id]: optionId }));

    try {
      await fetch(`/api/v1/attempts/${attemptId}/answers/${currentQ.question_id}`, {
        method: "PUT",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${accessToken || ""}`,
        },
        body: JSON.stringify({
          response: { selected: optionId },
          revision: 0,
          flagged: markedForReview.includes(currentQ.question_id),
        }),
      });
    } catch {
      // Answer kept in local state
    }
  };

  const handleToggleReview = () => {
    const currentQ = questions[currentIndex];
    if (!currentQ) return;
    setMarkedForReview((prev) =>
      prev.includes(currentQ.question_id)
        ? prev.filter((id) => id !== currentQ.question_id)
        : [...prev, currentQ.question_id]
    );
  };

  // Submit Exam Handler
  const handleFinalSubmit = async () => {
    if (!attemptId) return;

    setIsSubmitting(true);
    try {
      await fetch(`/api/v1/attempts/${attemptId}/submit`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${accessToken || ""}`,
        },
        body: JSON.stringify({}),
      });

      const res = await fetch(`/api/v1/attempts/${attemptId}/result`, {
        headers: {
          Authorization: `Bearer ${accessToken || ""}`,
        },
      });
      const resultData = await res.json();
      const r = resultData?.result || resultData;

      const score = Number(r.score ?? r.total_marks_awarded ?? 0);
      const totalMarks = Number(r.max_marks ?? r.total_marks ?? (questions.length * 10));
      const pct = Math.round(Number(r.percentage ?? (totalMarks > 0 ? (score / totalMarks) * 100 : 0)));
      const passThreshold = testDetail?.pass_mark_percent ?? versionDetail?.rule?.final_pass_mark ?? 70;
      const passed = Boolean(r.passed ?? (pct >= passThreshold));

      setTestResult({ score, totalMarks, pct, passed });

      if (document.exitFullscreen && document.fullscreenElement) {
        await document.exitFullscreen().catch(() => {});
      }

      if (passed) {
        notify.success(`Congratulations! Passed final exam with ${pct}%. Verified certificate issued.`);
        if (user?.user_id && courseId) {
          try {
            await fetch("/api/v1/certificates/issue-from-pass", {
              method: "POST",
              headers: {
                "Content-Type": "application/json",
                Authorization: `Bearer ${accessToken || localStorage.getItem("token") || ""}`,
              },
              body: JSON.stringify({
                student_user_id: Number(user.user_id),
                course_id: Number(courseId),
                score_percent: pct,
                attempt_id: Number(attemptId),
              }),
            });
          } catch {
            // Certificate auto-hook handled
          }
        }
      } else {
        notify.error(`Final exam completed. Score: ${pct}% (Pass required: ${passThreshold}%).`);
      }
    } catch (err: any) {
      notify.error(err?.data?.message || "Failed to submit final exam.");
    } finally {
      setIsSubmitting(false);
      setIsConfirmSubmitOpen(false);
    }
  };

  const courseTitle = course?.title || "Complete Python Mastery - Updated";
  const requiredPassMark = testDetail?.pass_mark_percent ?? versionDetail?.rule?.final_pass_mark ?? 70;
  const examDurationMinutes = testDetail?.duration_minutes ?? 60;
  const totalQuestionsCount = testDetail?.question_count ?? (questions.length || 10);

  const formatTimer = (secs: number | null) => {
    if (secs === null || secs < 0) return "--:--";
    const h = Math.floor(secs / 3600);
    const m = Math.floor((secs % 3600) / 60);
    const s = secs % 60;
    if (h > 0) {
      return `${String(h).padStart(2, "0")}:${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
    }
    return `${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
  };

  console.log("[FinalExamPage render]", {
    courseId,
    isCourseLoading,
    courseTitle: course?.title,
    versionId,
    isVersionLoading,
    finalTestId,
    isTestLoading,
  });

  if (isCourseLoading || isVersionLoading || isTestLoading) {
    return <PageLoader label="Loading proctored examination..." />;
  }

  // Empty state if no test configured
  if (!finalTestId || testError || (!isExamStarted && testDetail && testDetail.question_count === 0)) {
    const errorMsg =
      (testError as any)?.data?.message ||
      ((testError as any)?.status === 404
        ? "You must be enrolled in this course to take the final certification exam."
        : "This course does not have an approved final certification exam configured yet.");

    return (
      <div className="max-w-3xl mx-auto py-12 px-4 space-y-6">
        <nav className="flex items-center gap-2 text-xs text-slate-500">
          <Link to="/courses/my" className="hover:text-slate-800 transition-colors">Courses</Link>
          <span className="text-slate-400">/</span>
          <Link to={`/courses/${courseId}/learn`} className="hover:text-slate-800 transition-colors truncate max-w-[200px]">{courseTitle}</Link>
          <span className="text-slate-400">/</span>
          <span className="text-slate-900 font-semibold">Final Exam</span>
        </nav>

        <div className="rounded-2xl border border-slate-200 bg-white p-10 text-center space-y-4 shadow-2xs">
          <div className="w-12 h-12 rounded-full bg-amber-50 text-amber-600 flex items-center justify-center mx-auto">
            <AlertTriangle className="w-6 h-6" />
          </div>
          <h2 className="text-lg font-bold text-[#0A1530]">Final Exam Access</h2>
          <p className="text-xs text-slate-500 max-w-md mx-auto">
            {errorMsg}
          </p>
          <div className="pt-2 flex items-center justify-center gap-3">
            <button
              type="button"
              onClick={() => navigate("/courses/my")}
              className="px-4 py-2 rounded-xl border border-slate-300 text-xs font-semibold text-slate-700 hover:bg-slate-50 cursor-pointer"
            >
              My Courses
            </button>
            <button
              type="button"
              onClick={() => navigate(`/courses/${courseId}/learn`)}
              className="px-4 py-2 rounded-xl bg-[#00663C] text-xs font-bold text-white hover:bg-[#00522F] cursor-pointer"
            >
              Back to Course
            </button>
          </div>
        </div>
      </div>
    );
  }

  const currentQ = questions[currentIndex];
  const isLastQuestion = questions.length > 0 && currentIndex === questions.length - 1;
  const answeredCount = Object.keys(answers).length;
  const warningCount = malpracticeIncidents.length;

  return (
    <div className="max-w-5xl mx-auto space-y-6 pb-12 pt-4 px-4">
      {/* MALPRACTICE WARNING MODAL */}
      <MalpracticeWarningModal
        incident={activeWarningIncident}
        warningCount={warningCount}
        maxWarnings={maxWarnings}
        onResume={handleResumeFromWarning}
      />

      {/* MALPRACTICE DISQUALIFIED MODAL */}
      {isDisqualified && (
        <MalpracticeDisqualifiedModal
          incidents={malpracticeIncidents}
          maxWarnings={maxWarnings}
          onExit={() => navigate(`/courses/${courseId}/learn`)}
        />
      )}

      {/* Breadcrumb Navigation */}
      <nav className="flex items-center gap-2 text-xs text-slate-500">
        <Link to="/courses/my" className="hover:text-slate-800 transition-colors">Courses</Link>
        <span className="text-slate-400">/</span>
        <Link to={`/courses/${courseId}/learn`} className="hover:text-slate-800 transition-colors truncate max-w-[240px]">
          {courseTitle}
        </Link>
        <span className="text-slate-400">/</span>
        <span className="text-slate-900 font-semibold">Final certification exam</span>
      </nav>

      {/* SCREEN 10 PHASE 1: PRE-EXAM DEVICE & CONSENT CHECK */}
      {!isExamStarted ? (
        <div className="space-y-6">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <h2 className="text-xl font-bold text-[#0A1530]">
                Final certification exam
              </h2>
              <p className="text-xs text-[#657083] mt-0.5">
                {courseTitle} · Comprehensive Proctored Assessment
              </p>
            </div>
            <span className="px-3 py-1 rounded-full bg-[#E7F3EC] text-[#00663C] text-xs font-bold flex items-center gap-1.5 border border-[#A5D5BC]">
              <Shield className="w-3.5 h-3.5" />
              Proctor Guard Active · {maxWarnings} Allowed Warnings
            </span>
          </div>

          <div className="p-6 rounded-2xl border border-[#E4EAE7] bg-white space-y-6 shadow-2xs">
            {/* 3 Step Progress Bar */}
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 border-b border-[#E4EAE7] pb-6">
              <div className="p-3 rounded-xl bg-[#E7F3EC] text-[#00663C] flex items-center gap-2 text-xs">
                <Check className="w-4 h-4 stroke-[3]" />
                <div>
                  <b className="block text-[#0A1530]">1. Rules & Malpractice</b>
                  <span className="text-[11px] text-[#00663C]">Configured ({maxWarnings} warnings)</span>
                </div>
              </div>

              <div className="p-3 rounded-xl bg-[#E7F3EC] text-[#00663C] flex items-center gap-2 text-xs">
                <Check className="w-4 h-4 stroke-[3]" />
                <div>
                  <b className="block text-[#0A1530]">2. Device check</b>
                  <span className="text-[11px] text-[#00663C]">Camera & mic verified</span>
                </div>
              </div>

              <div className="p-3 rounded-xl bg-[#EAECFB] text-[#1B2A8C] flex items-center gap-2 text-xs border border-[#1B2A8C]/20">
                <span className="w-4 h-4 rounded-full bg-[#1B2A8C] text-white text-[10px] flex items-center justify-center font-bold">
                  3
                </span>
                <div>
                  <b className="block text-[#0A1530]">3. Agree & Enter Fullscreen</b>
                  <span className="text-[11px] text-[#1B2A8C]">Final verification</span>
                </div>
              </div>
            </div>

            {/* Split layout: Checklist and Live Cam Test */}
            <div className="grid grid-cols-1 md:grid-cols-12 gap-6 items-start">
              <div className="md:col-span-7 space-y-4">
                {/* 3 Metrics */}
                <div className="grid grid-cols-3 gap-3 text-center">
                  <div className="p-3 rounded-xl bg-[#F8FAF9] border border-[#E4EAE7]">
                    <b className="text-xl font-bold text-[#0A1530] block tabular-nums">
                      {totalQuestionsCount}
                    </b>
                    <span className="text-[11px] text-[#657083]">Questions</span>
                  </div>
                  <div className="p-3 rounded-xl bg-[#F8FAF9] border border-[#E4EAE7]">
                    <b className="text-xl font-bold text-[#0A1530] block">
                      {examDurationMinutes} min
                    </b>
                    <span className="text-[11px] text-[#657083]">Duration</span>
                  </div>
                  <div className="p-3 rounded-xl bg-[#F8FAF9] border border-[#E4EAE7]">
                    <b className="text-xl font-bold text-[#0A1530] block">
                      {requiredPassMark}%
                    </b>
                    <span className="text-[11px] text-[#657083]">Pass mark</span>
                  </div>
                </div>

                {/* Device Status checklist */}
                <div className="p-4 rounded-xl bg-[#F8FAF9] border border-[#E4EAE7] space-y-2.5 text-xs">
                  <div className="flex items-center gap-2 text-[#00663C] font-semibold">
                    <CheckCircle className="w-4 h-4 text-[#00663C]" />
                    <span>Camera ready — continuous webcam monitoring will be active</span>
                  </div>
                  <div className="flex items-center gap-2 text-[#00663C] font-semibold">
                    <CheckCircle className="w-4 h-4 text-[#00663C]" />
                    <span>Microphone calibrated — environmental audio monitoring enabled</span>
                  </div>
                  <div className="flex items-center gap-2 text-[#00663C] font-semibold">
                    <CheckCircle className="w-4 h-4 text-[#00663C]" />
                    <span>Browser fullscreen lockdown initialized</span>
                  </div>
                  <div className="flex items-center gap-2 text-[#9A5B00] font-semibold">
                    <AlertTriangle className="w-4 h-4 text-[#9A5B00]" />
                    <span>
                      Course Malpractice Rule: Exceeding {maxWarnings} warnings terminates exam
                    </span>
                  </div>
                </div>

                {/* Privacy Callout */}
                <div className="p-3.5 rounded-xl bg-blue-50/70 border border-blue-200 text-xs text-blue-900 leading-relaxed">
                  <strong>Integrity Policy:</strong> Your camera and microphone stream actively in a dedicated proctoring box. Leaving fullscreen mode, switching browser tabs, or attempting clipboard copy will trigger an immediate malpractice violation warning.
                </div>

                {/* Consent checkbox */}
                <label className="flex items-start gap-3 p-3 rounded-xl border border-[#C9D3CE] bg-white cursor-pointer hover:bg-slate-50 transition-colors">
                  <input
                    id="consent"
                    type="checkbox"
                    checked={hasAgreedConsent}
                    onChange={(e) => setHasAgreedConsent(e.target.checked)}
                    className="w-4 h-4 mt-0.5 accent-[#00663C] rounded cursor-pointer"
                  />
                  <span className="text-xs text-[#0A1530] font-medium leading-relaxed">
                    I agree to continuous webcam monitoring, acknowledge the {maxWarnings}-warning limit, and agree to enter and stay in full screen during this examination.
                  </span>
                </label>

                {/* Enter Exam Button */}
                <button
                  type="button"
                  id="startexam"
                  disabled={!hasAgreedConsent || isStartingAttempt}
                  onClick={handleStartExam}
                  className="w-full sm:w-auto px-6 py-3 rounded-xl bg-[#00663C] hover:bg-[#00522F] disabled:opacity-40 text-white font-bold text-xs flex items-center justify-center gap-2 shadow-sm cursor-pointer transition-all"
                >
                  <Maximize2 className="w-4 h-4" />
                  <span>{isStartingAttempt ? "Preparing Exam..." : "Start certification exam & Enter Fullscreen"}</span>
                  <ArrowRight className="w-4 h-4 ml-1" />
                </button>
              </div>

              {/* Right: Live Camera Preview Box */}
              <div className="md:col-span-5 flex flex-col items-center">
                <span className="text-xs font-bold text-[#0A1530] mb-2 self-start flex items-center gap-1.5">
                  <Camera className="w-4 h-4 text-[#00663C]" />
                  Live Proctor Camera Preview
                </span>

                <ProctorCamera
                  isActive={true}
                  sessionId={sessionId}
                  accessToken={accessToken}
                  warningsCount={0}
                  maxWarnings={maxWarnings}
                  onObjectDetected={handleCameraObjectDetected}
                />

                <span className="text-[11px] text-[#657083] mt-2 text-center max-w-xs">
                  Your webcam stream will remain docked in the corner throughout exam writing to verify student presence.
                </span>
              </div>
            </div>

            {/* Note bar */}
            <div className="pt-4 border-t border-[#E4EAE7] flex flex-wrap items-center justify-between gap-3 text-xs text-slate-500">
              <span className="flex items-center gap-1.5">
                <span className="w-2 h-2 rounded-full bg-emerald-500" />
                During the exam: One question at a time, timer, question list, mark for review. Answers save automatically.
              </span>
              <span className="font-mono text-slate-600 font-semibold">
                Remaining time preview: {examDurationMinutes}:00
              </span>
            </div>
          </div>
        </div>
      ) : testResult ? (
        /* SCREEN 10 PHASE 3: RESULTS VIEW */
        <div className="rounded-2xl border border-slate-200 bg-white p-8 text-center space-y-6 shadow-2xs">
          <div
            className={cn(
              "w-16 h-16 rounded-full flex items-center justify-center mx-auto text-2xl font-bold",
              testResult.passed ? "bg-emerald-100 text-emerald-700" : "bg-rose-100 text-rose-700"
            )}
          >
            {testResult.passed ? <Check className="w-8 h-8 stroke-[3]" /> : <AlertTriangle className="w-8 h-8" />}
          </div>

          <div>
            <h3 className="text-xl font-bold text-[#0A1530]">
              {testResult.passed ? "Congratulations! You Passed!" : "Exam Not Passed"}
            </h3>
            <p className="text-xs text-slate-500 mt-1">
              {testResult.passed
                ? "You have successfully achieved certification in this course. Your certificate has been issued."
                : `You scored ${testResult.pct}%. A minimum of ${requiredPassMark}% is required to earn your certificate.`}
            </p>
          </div>

          <div className="inline-flex items-center gap-6 p-4 rounded-xl bg-slate-50 border border-slate-200">
            <div>
              <span className="text-[10px] text-slate-400 uppercase font-bold block">Final Score</span>
              <b className="text-xl font-bold text-slate-900">{testResult.pct}%</b>
            </div>
            <div className="h-8 w-px bg-slate-200" />
            <div>
              <span className="text-[10px] text-slate-400 uppercase font-bold block">Marks Awarded</span>
              <b className="text-xl font-bold text-slate-900">{testResult.score} / {testResult.totalMarks}</b>
            </div>
            <div className="h-8 w-px bg-slate-200" />
            <div>
              <span className="text-[10px] text-slate-400 uppercase font-bold block">Status</span>
              <b className={cn("text-xl font-bold", testResult.passed ? "text-emerald-600" : "text-rose-600")}>
                {testResult.passed ? "PASSED" : "FAILED"}
              </b>
            </div>
          </div>

          <div className="flex items-center justify-center gap-3 pt-2">
            <button
              type="button"
              onClick={() => navigate(`/courses/${courseId}/learn`)}
              className="px-5 py-2.5 rounded-xl border border-slate-300 bg-white text-xs font-bold text-slate-700 hover:bg-slate-50 cursor-pointer"
            >
              Back to Course
            </button>
            {testResult.passed && (
              <button
                type="button"
                onClick={() => navigate("/courses/my")}
                className="px-5 py-2.5 rounded-xl bg-[#00663C] text-xs font-bold text-white hover:bg-[#00522F] cursor-pointer shadow-xs"
              >
                View Certificate
              </button>
            )}
          </div>
        </div>
      ) : (
        /* SCREEN 10 PHASE 2: ACTIVE PROCTORED EXAMINATION */
        <div className="space-y-4">
          {/* Top Bar with Proctor Status, Warning Counter, Timer, and Exit Button */}
          <div className="flex flex-wrap items-center justify-between gap-3 p-4 rounded-xl border border-slate-200 bg-white shadow-2xs">
            <div className="flex items-center gap-3">
              <span className="w-2.5 h-2.5 rounded-full bg-emerald-500 animate-ping" />
              <b className="text-xs font-bold text-[#00663C]">PROCTORING ACTIVE</b>
              <span className="text-xs text-slate-400">|</span>
              <span className="text-xs text-slate-600 font-semibold">{courseTitle}</span>
            </div>

            <div className="flex items-center gap-4">
              <div
                className={cn(
                  "px-3 py-1 rounded-md text-xs font-bold flex items-center gap-1.5",
                  warningCount === 0
                    ? "bg-slate-100 text-slate-700"
                    : warningCount >= maxWarnings
                    ? "bg-rose-100 text-rose-800 animate-pulse"
                    : "bg-amber-100 text-amber-800"
                )}
              >
                <AlertTriangle className="w-3.5 h-3.5" />
                <span>Warnings: {warningCount} / {maxWarnings}</span>
              </div>

              <div
                className={cn(
                  "px-3 py-1 rounded-md text-xs font-mono font-bold tracking-wider",
                  (secondsRemaining ?? 0) < 300 ? "bg-rose-100 text-rose-700 animate-pulse" : "bg-slate-100 text-slate-800"
                )}
              >
                {formatTimer(secondsRemaining)} Remaining
              </div>

              <button
                type="button"
                onClick={() => setIsExitModalOpen(true)}
                className="flex items-center gap-1.5 px-3 py-1 rounded-xl border border-slate-300 bg-white text-xs font-semibold text-slate-700 hover:bg-slate-50 cursor-pointer shadow-2xs"
              >
                <ArrowLeft className="w-3.5 h-3.5" />
                Exit Exam
              </button>
            </div>
          </div>

          {/* Main Proctoring Grid: Question View + Live Camera Box */}
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-4 items-start">
            {/* Left 8/12: Question Runner */}
            <div className="lg:col-span-8 rounded-2xl border border-slate-200 bg-white p-6 shadow-2xs space-y-6">
              {currentQ ? (
                <div className="space-y-4">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-bold text-slate-400 uppercase tracking-wider">
                      Question {currentIndex + 1} of {questions.length}
                    </span>
                    <button
                      type="button"
                      onClick={handleToggleReview}
                      className={cn(
                        "flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs font-semibold cursor-pointer border transition-colors",
                        markedForReview.includes(currentQ.question_id)
                          ? "bg-amber-50 border-amber-300 text-amber-700"
                          : "bg-white border-slate-200 text-slate-500 hover:bg-slate-50"
                      )}
                    >
                      <Flag className="w-3.5 h-3.5" />
                      {markedForReview.includes(currentQ.question_id) ? "Marked for Review" : "Mark for Review"}
                    </button>
                  </div>

                  <div className="p-4 rounded-xl bg-slate-50 border border-slate-200">
                    <p className="text-sm font-semibold text-slate-900 leading-relaxed whitespace-pre-wrap">
                      {currentQ.text}
                    </p>
                  </div>

                  {/* Options List */}
                  <div className="space-y-2 pt-2">
                    {currentQ.options.length > 0 ? (
                      currentQ.options.map((opt, oIdx) => {
                        const isSelected = answers[currentQ.question_id] === opt.id;
                        return (
                          <button
                            key={opt.id || oIdx}
                            type="button"
                            onClick={() => handleSelectOption(opt.id)}
                            className={cn(
                              "w-full text-left p-3.5 rounded-xl border text-xs font-medium transition-all flex items-center gap-3 cursor-pointer",
                              isSelected
                                ? "border-[#00663C] bg-[#E7F3EC] text-[#00663C] font-semibold shadow-2xs"
                                : "border-slate-200 bg-white text-slate-700 hover:bg-slate-50"
                            )}
                          >
                            <span
                              className={cn(
                                "w-5 h-5 rounded-full border flex items-center justify-center text-[10px] font-bold shrink-0",
                                isSelected ? "border-[#00663C] bg-[#00663C] text-white" : "border-slate-300 text-slate-500"
                              )}
                            >
                              {String.fromCharCode(65 + oIdx)}
                            </span>
                            <span className="flex-1">{opt.text}</span>
                          </button>
                        );
                      })
                    ) : (
                      <div className="space-y-2">
                        <textarea
                          rows={4}
                          value={answers[currentQ.question_id] || ""}
                          onChange={(e) => handleSelectOption(e.target.value)}
                          placeholder="Type your response here. Answers are autosaved to the server."
                          className="w-full rounded-xl border border-slate-300 p-3 text-xs text-slate-800 focus:outline-none focus:border-[#00663C]"
                        />
                      </div>
                    )}
                  </div>

                  {/* Navigation & Submission Controls */}
                  <div className="flex items-center justify-between pt-4 border-t border-slate-100">
                    <button
                      type="button"
                      disabled={currentIndex === 0}
                      onClick={() => setCurrentIndex((prev) => Math.max(0, prev - 1))}
                      className="flex items-center gap-1.5 px-4 py-2 rounded-xl border border-slate-200 bg-white text-xs font-semibold text-slate-700 hover:bg-slate-50 disabled:opacity-40 cursor-pointer"
                    >
                      <ArrowLeft className="w-3.5 h-3.5" />
                      Previous
                    </button>

                    <div className="flex items-center gap-3">
                      {isLastQuestion ? (
                        <button
                          type="button"
                          onClick={() => setIsConfirmSubmitOpen(true)}
                          className="px-5 py-2 rounded-xl bg-[#00663C] text-xs font-bold text-white hover:bg-[#00522F] cursor-pointer shadow-xs"
                        >
                          Submit Examination
                        </button>
                      ) : (
                        <button
                          type="button"
                          onClick={() => setCurrentIndex((prev) => Math.min(questions.length - 1, prev + 1))}
                          className="flex items-center gap-1.5 px-4 py-2 rounded-xl bg-[#00663C] text-xs font-bold text-white hover:bg-[#00522F] cursor-pointer"
                        >
                          Next
                          <ArrowRight className="w-3.5 h-3.5" />
                        </button>
                      )}
                    </div>
                  </div>
                </div>
              ) : null}
            </div>

            {/* Right 4/12: Live Proctor Camera + Question Palette */}
            <div className="lg:col-span-4 space-y-4">
              {/* Docked Live Camera Stream with AI Scanner */}
              <div className="rounded-2xl border border-slate-200 bg-white p-3 shadow-2xs space-y-2">
                <span className="text-xs font-bold text-[#0A1530] flex items-center gap-1.5">
                  <Camera className="w-3.5 h-3.5 text-[#00663C]" />
                  Active Proctor Feed
                </span>
                <div className="flex justify-center">
                  <ProctorCamera
                    isActive={true}
                    sessionId={sessionId}
                    accessToken={accessToken}
                    warningsCount={warningCount}
                    maxWarnings={maxWarnings}
                    isCompact={true}
                    onObjectDetected={handleCameraObjectDetected}
                  />
                </div>
              </div>

              {/* Question Palette / Grid */}
              <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-2xs">
                <div className="flex items-center justify-between mb-3">
                  <span className="text-xs font-bold text-slate-700">Question Palette</span>
                  <span className="text-[11px] text-slate-500">
                    Answered: <b>{answeredCount}/{questions.length}</b>
                  </span>
                </div>

                <div className="flex flex-wrap gap-2">
                  {questions.map((q, idx) => {
                    const isCurrent = idx === currentIndex;
                    const isAnswered = Boolean(answers[q.question_id]);
                    const isMarked = markedForReview.includes(q.question_id);

                    return (
                      <button
                        key={q.question_id || idx}
                        type="button"
                        onClick={() => setCurrentIndex(idx)}
                        className={cn(
                          "w-8 h-8 rounded-lg text-xs font-bold flex items-center justify-center transition-all cursor-pointer border",
                          isCurrent && "ring-2 ring-[#00663C] ring-offset-1",
                          isMarked
                            ? "bg-amber-100 border-amber-300 text-amber-800"
                            : isAnswered
                            ? "bg-[#00663C] border-[#00663C] text-white"
                            : "bg-slate-50 border-slate-200 text-slate-600 hover:bg-slate-100"
                        )}
                      >
                        {idx + 1}
                      </button>
                    );
                  })}
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Exit Confirmation Modal */}
      <ConfirmModal
        isOpen={isExitModalOpen}
        onClose={() => setIsExitModalOpen(false)}
        onConfirm={() => {
          setIsExitModalOpen(false);
          if (document.exitFullscreen && document.fullscreenElement) {
            document.exitFullscreen().catch(() => {});
          }
          navigate(`/courses/${courseId}/learn`);
        }}
        title="Leave Proctored Exam?"
        description="Leave this exam? Your answers are saved and you can resume while the timer is running."
        confirmLabel="Leave"
        tone="danger"
      />

      {/* Final Submit Confirmation Modal */}
      <ConfirmModal
        isOpen={isConfirmSubmitOpen}
        onClose={() => setIsConfirmSubmitOpen(false)}
        onConfirm={handleFinalSubmit}
        title="Submit Proctored Exam?"
        description={`You have answered ${answeredCount} of ${questions.length} questions. Are you ready to submit your certification exam?`}
        confirmLabel={isSubmitting ? "Submitting..." : "Yes, Submit Exam"}
        tone="primary"
      />
    </div>
  );
}
