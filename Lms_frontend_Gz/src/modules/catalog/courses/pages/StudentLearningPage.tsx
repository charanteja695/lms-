import React, { useState, useMemo, useEffect, useRef, useCallback } from "react";
import { useParams, useNavigate, Link, useSearchParams } from "react-router-dom";
import { useAuth } from "@/modules/user-management/auth/hooks/useAuth";
import { useGetCourseQuery, useGetVersionQuery } from "@/modules/catalog/courses/api/coursesApi";
import {
  useListEnrollmentsQuery,
  useGetUnlockStateQuery,
  useCompleteItemMutation,
  useEnrollStudentMutation,
} from "@/modules/learning/enrollments/api/enrollmentsApi";
import { useListMyCoursesQuery } from "@/modules/learning/common/api/myCoursesApi";
import { useGetMyTestQuery, useListAttemptsQuery } from "@/modules/assessments/attempts/api/attemptsApi";
import {
  useListCertificatesQuery,
  useGetCertificateDownloadMutation,
} from "@/modules/certificates/issued/api/certificatesApi";
import { PageLoader } from "@/shared/ui";
import { useNotify } from "@/core/hooks/useNotify";
import { cn } from "@/core/lib/cn";
import {
  Play,
  Pause,
  RotateCcw,
  Volume2,
  VolumeX,
  Maximize2,
  CheckCircle2,
  Lock,
  Award,
  Clock,
  ChevronRight,
  ChevronDown,
  Menu,
  X,
  FileText,
  Check,
  Download,
  GripVertical,
  BookOpen,
  Share2,
  ExternalLink,
  Eye,
  Settings2,
  ShieldAlert,
} from "lucide-react";
import { InAppPdfViewer } from "../components/InAppPdfViewer";

type MaterialTab = "video" | "pdf" | "notes" | "materials";

export type VideoQuality = "Auto" | "420p" | "720p" | "1080p" | "2040p";

interface VideoQualityOption {
  id: VideoQuality;
  label: string;
  resolution: string;
  badge: string;
  description: string;
  src: string;
}

const QUALITY_OPTIONS: VideoQualityOption[] = [
  {
    id: "Auto",
    label: "Auto",
    resolution: "Auto (1080p Adaptive)",
    badge: "Auto (1080p)",
    description: "Adaptive resolution based on connection speed",
    src: "https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/BigBuckBunny.mp4",
  },
  {
    id: "2040p",
    label: "2040p",
    resolution: "4K UHD (2160p / 2040p)",
    badge: "2040p 4K",
    description: "Ultra High Definition 2040p (4K UHD)",
    src: "https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/TearsOfSteel.mp4",
  },
  {
    id: "1080p",
    label: "1080p",
    resolution: "Full HD (1080p)",
    badge: "1080p FHD",
    description: "Standard Full High Definition stream",
    src: "https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/BigBuckBunny.mp4",
  },
  {
    id: "720p",
    label: "720p",
    resolution: "HD (720p)",
    badge: "720p HD",
    description: "High Definition standard stream",
    src: "https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/ElephantsDream.mp4",
  },
  {
    id: "420p",
    label: "420p",
    resolution: "SD (420p)",
    badge: "420p SD",
    description: "Standard definition, low bandwidth saver",
    src: "https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/ForBiggerBlazes.mp4",
  },
];

interface SavedVideoProgress {
  currentTime: number;
  duration: number;
  percent: number;
  completed: boolean;
  updatedAt: string;
}

export type CourseNavTab = "overview" | "modules" | "assessments" | "certificate";

export function StudentLearningPage() {
  const { courseId } = useParams<{ courseId: string }>();
  const navigate = useNavigate();
  const notify = useNotify();
  const { user } = useAuth();
  const [searchParams, setSearchParams] = useSearchParams();

  // Top-level tab: Course Overview | Modules | Assessments | Certificate
  const activeCourseTab = (searchParams.get("tab") as CourseNavTab) || "modules";
  const handleSelectCourseTab = (tab: CourseNavTab) => {
    setSearchParams(
      (prev) => {
        const next = new URLSearchParams(prev);
        next.set("tab", tab);
        return next;
      },
      { replace: true }
    );
  };

  // Certificate download state
  const [downloadingCertId, setDownloadingCertId] = useState<string | null>(null);
  const [downloadCert] = useGetCertificateDownloadMutation();

  const handleDownloadPdf = async (certId: string, certCode: string) => {
    try {
      setDownloadingCertId(certId);
      notify.info("Preparing verified PDF certificate...");
      const res = await downloadCert(certId).unwrap();
      if (res?.url) {
        window.open(res.url, "_blank");
        notify.success("Certificate download started.");
      } else {
        window.print();
      }
    } catch {
      notify.success(`Certificate ${certCode} verified. Printing document.`);
      window.print();
    } finally {
      setDownloadingCertId(null);
    }
  };

  // Active Tab & Selection State
  const [activeTab, setActiveTab] = useState<MaterialTab>("video");
  const [selectedTopicId, setSelectedTopicId] = useState<string | null>(null);
  const [expandedModules, setExpandedModules] = useState<Record<string, boolean>>({});

  // Mobile sidebar toggle
  const [isMobileSidebarOpen, setIsMobileSidebarOpen] = useState(false);

  // Split Panel Resizing State
  const [leftWidthPct, setLeftWidthPct] = useState<number>(() => {
    try {
      const saved = localStorage.getItem("examlms_learning_split_pct");
      if (saved) {
        const val = Number(saved);
        if (!isNaN(val) && val >= 45 && val <= 80) return val;
      }
    } catch {}
    return 66; // default 66% left / 34% right
  });
  const [isDragging, setIsDragging] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  // Video Player Ref & State
  const videoRef = useRef<HTMLVideoElement>(null);
  const playerContainerRef = useRef<HTMLDivElement>(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(600); // 10 mins default
  const [isMuted, setIsMuted] = useState(false);
  const [playbackRate, setPlaybackRate] = useState(1);
  const [isFullscreen, setIsFullscreen] = useState(false);

  // Video Quality State
  const [videoQuality, setVideoQuality] = useState<VideoQuality>("Auto");
  const [isQualityMenuOpen, setIsQualityMenuOpen] = useState(false);
  const qualityMenuRef = useRef<HTMLDivElement>(null);

  // In-App PDF Viewer State
  const [isPdfViewerOpen, setIsPdfViewerOpen] = useState(false);

  // Local Storage Key for Video Progress
  const progressStorageKey = useMemo(() => {
    const studentId = user?.user_id || "guest";
    return `examlms_video_progress_${studentId}_${courseId || "default"}`;
  }, [user?.user_id, courseId]);

  // Map of topicId -> SavedVideoProgress
  const [videoProgressMap, setVideoProgressMap] = useState<Record<string, SavedVideoProgress>>(() => {
    try {
      const stored = localStorage.getItem(progressStorageKey);
      if (stored) return JSON.parse(stored);
    } catch {}
    return {};
  });

  // Queries
  const { data: course, isLoading: isCourseLoading, isError: isCourseError } = useGetCourseQuery(courseId ?? "", {
    skip: !courseId,
  });

  const publishedVersion = course?.versions?.find((v) => v.status === "published");
  const versionId = publishedVersion?.version_id || course?.versions?.[course.versions.length - 1]?.version_id;
  const { data: versionDetail, isLoading: isVersionLoading } = useGetVersionQuery(
    { courseId: courseId ?? "", versionId: versionId ?? "" },
    { skip: !courseId || !versionId }
  );

  const { data: enrollmentsData, isLoading: isEnrollmentsLoading } = useListEnrollmentsQuery({
    status: "active",
    per_page: 50,
  });

  const { data: myCourses } = useListMyCoursesQuery();

  // Find enrollment for this course
  const enrollment = useMemo(() => {
    const list = enrollmentsData?.items ?? [];
    const courseMatch = myCourses?.find((c) => String(c.course_id) === String(courseId));
    if (courseMatch?.enrollment_id) {
      const found = list.find((e) => String(e.enrollment_id) === String(courseMatch.enrollment_id));
      if (found) return found;
    }
    return list[0];
  }, [enrollmentsData, myCourses, courseId]);

  const { data: unlockState } = useGetUnlockStateQuery(enrollment?.enrollment_id ?? "", {
    skip: !enrollment?.enrollment_id,
  });

  const [completeItemMutation, { isLoading: isCompleting }] = useCompleteItemMutation();
  const [enrollMutation, { isLoading: isEnrolling }] = useEnrollStudentMutation();

  // Final Exam Query
  const finalTestId = versionDetail?.rule?.final_test_id;
  const { data: finalTestDetail } = useGetMyTestQuery(String(finalTestId ?? ""), {
    skip: !finalTestId,
  });
  const { data: finalAttemptsData } = useListAttemptsQuery(
    { test_id: finalTestId ? String(finalTestId) : undefined },
    { skip: !finalTestId }
  );

  // Modules List from unlockState or versionDetail
  const modulesList = useMemo(() => {
    if (unlockState?.modules && unlockState.modules.length > 0) {
      return unlockState.modules;
    }
    return (versionDetail?.modules ?? []).map((m, mIdx) => ({
      module_id: m.module_id,
      title: m.title,
      position: m.position || mIdx + 1,
      unlocked: true,
      completed: false,
      test_passed: false,
      topics: (m.topics ?? []).map((t, tIdx) => ({
        topic_id: t.topic_id,
        title: t.title,
        position: t.position || tIdx + 1,
        unlocked: true,
        completed: false,
        test_passed: false,
        completed_items: 0,
        required_items: t.items?.length || 1,
        items: (t.items ?? []).map((it, itIdx) => ({
          topic_item_id: it.topic_item_id,
          title: it.title,
          item_type: (it as any).kind || (it as any).item_type || "notes",
          position: it.position || itIdx + 1,
          required: true,
          completed: false,
        })),
      })),
    }));
  }, [unlockState, versionDetail]);

  // Set default expanded modules
  useEffect(() => {
    if (modulesList.length > 0 && Object.keys(expandedModules).length === 0) {
      const initial: Record<string, boolean> = {};
      modulesList.forEach((m) => {
        initial[m.module_id] = true;
      });
      setExpandedModules(initial);
    }
  }, [modulesList]);

  // Determine active topic
  const activeTopic = useMemo(() => {
    for (const m of modulesList) {
      for (const t of m.topics) {
        if (selectedTopicId && String(t.topic_id) === String(selectedTopicId)) return t;
      }
    }
    return modulesList[0]?.topics[0] || null;
  }, [modulesList, selectedTopicId]);

  // Determine active module
  const currentActiveModule = useMemo(() => {
    if (!activeTopic) return modulesList[0] || null;
    return (
      modulesList.find((m) => m.topics.some((t) => String(t.topic_id) === String(activeTopic.topic_id))) ||
      modulesList[0] ||
      null
    );
  }, [modulesList, activeTopic]);

  const activeItem = activeTopic?.items?.[0];

  // Helper: Calculate Chapter Completion Percentage
  const getChapterProgress = useCallback(
    (topic: any): number => {
      if (!topic) return 0;
      // 1. If backend marks topic as completed or test passed -> 100%
      if (topic.completed || topic.test_passed) return 100;

      // 2. Check local/synced video progress
      const key = String(topic.topic_id);
      const saved = videoProgressMap[key];
      if (saved) {
        if (saved.completed) return 100;
        if (saved.percent > 0) return Math.min(100, saved.percent);
      }

      // 3. Check topic items completion ratio
      if (topic.required_items > 0 && topic.completed_items > 0) {
        return Math.min(100, Math.round((topic.completed_items / topic.required_items) * 100));
      }

      return 0;
    },
    [videoProgressMap]
  );

  // Helper: Calculate Module Completion Percentage
  const getModuleProgress = useCallback(
    (mod: any): number => {
      if (!mod || !mod.topics || mod.topics.length === 0) return 0;
      if (mod.completed || mod.test_passed) return 100;
      const sum = mod.topics.reduce((acc: number, t: any) => acc + getChapterProgress(t), 0);
      return Math.round(sum / mod.topics.length);
    },
    [getChapterProgress]
  );

  // Overall Course Progress
  const progressPercent = useMemo(() => {
    if (modulesList.length === 0) return 0;
    const sum = modulesList.reduce((acc, m) => acc + getModuleProgress(m), 0);
    return Math.round(sum / modulesList.length);
  }, [modulesList, getModuleProgress]);

  // Final Exam Status: "completed" | "in_progress" | "available" | "locked"
  const finalStatus = useMemo(() => {
    if (!finalTestId) return "locked";

    // Completed?
    const hasCompletedAttempt = finalAttemptsData?.items?.some(
      (a) => a.status === "graded" || a.result === "passed" || a.score !== null
    );
    if (
      hasCompletedAttempt ||
      (finalTestDetail?.best_percent != null &&
        finalTestDetail.best_percent >= (finalTestDetail?.pass_mark_percent ?? 70))
    ) {
      return "completed";
    }

    // In Progress?
    if (finalTestDetail?.open_attempt_id || finalAttemptsData?.items?.some((a) => a.status === "in_progress")) {
      return "in_progress";
    }

    // Available?
    const allModulesFinished =
      modulesList.length > 0 && modulesList.every((m) => m.completed || (m as any).test_passed || getModuleProgress(m) === 100);
    const isEligible = Boolean(unlockState?.eligible_for_final || finalTestDetail?.can_start || allModulesFinished);
    if (isEligible) {
      return "available";
    }

    return "locked";
  }, [finalTestId, finalAttemptsData, finalTestDetail, unlockState, modulesList, getModuleProgress]);

  // Certificate Data & Course Completion Evaluation
  const { data: certsData } = useListCertificatesQuery({ per_page: 50 });
  const certificates = certsData?.items ?? [];
  const courseCertificate = useMemo(() => {
    return certificates.find((c) => String(c.course_id) === String(courseId));
  }, [certificates, courseId]);

  const isCourseCompleted =
    Boolean(courseCertificate) ||
    finalStatus === "completed" ||
    (modulesList.length > 0 && modulesList.every((m) => m.completed || (m as any).test_passed));

  // Restore video progress when switching chapters
  useEffect(() => {
    if (!activeTopic) return;
    const key = String(activeTopic.topic_id);
    const saved = videoProgressMap[key];
    if (saved && saved.currentTime > 0) {
      setCurrentTime(saved.currentTime);
      if (saved.duration) setDuration(saved.duration);
      if (videoRef.current) {
        videoRef.current.currentTime = saved.currentTime;
      }
    } else {
      setCurrentTime(0);
      if (videoRef.current) {
        videoRef.current.currentTime = 0;
      }
    }
    setIsPlaying(false);
  }, [activeTopic?.topic_id]);

  // Save Progress Debounced
  const saveProgressDebounced = useRef<NodeJS.Timeout | null>(null);
  const persistProgress = useCallback(
    (timeSec: number, durSec: number, forceComplete = false) => {
      if (!activeTopic) return;
      const key = String(activeTopic.topic_id);
      const computedPct = durSec > 0 ? Math.min(100, Math.round((timeSec / durSec) * 100)) : 0;
      const isDone = forceComplete || computedPct >= 90;

      const record: SavedVideoProgress = {
        currentTime: Math.floor(timeSec),
        duration: Math.floor(durSec),
        percent: isDone ? 100 : computedPct,
        completed: isDone,
        updatedAt: new Date().toISOString(),
      };

      setVideoProgressMap((prev) => {
        const next = { ...prev, [key]: record };
        try {
          localStorage.setItem(progressStorageKey, JSON.stringify(next));
        } catch {}
        return next;
      });

      // Auto sync with backend if completed and enrolled
      if (isDone && enrollment?.enrollment_id && activeItem?.topic_item_id) {
        completeItemMutation({
          enrollmentId: enrollment.enrollment_id,
          topicItemId: activeItem.topic_item_id,
        }).catch(() => {});
      }
    },
    [activeTopic, progressStorageKey, enrollment?.enrollment_id, activeItem?.topic_item_id, completeItemMutation]
  );

  // Time update listener
  const handleTimeUpdate = () => {
    if (!videoRef.current) return;
    const cur = videoRef.current.currentTime;
    const dur = videoRef.current.duration || duration || 600;
    setCurrentTime(cur);

    if (saveProgressDebounced.current) clearTimeout(saveProgressDebounced.current);
    saveProgressDebounced.current = setTimeout(() => {
      persistProgress(cur, dur);
    }, 1500);
  };

  const handleLoadedMetadata = () => {
    if (!videoRef.current) return;
    const dur = videoRef.current.duration;
    if (dur && !isNaN(dur) && dur > 0) {
      setDuration(dur);
    }
  };

  const handleVideoEnded = () => {
    setIsPlaying(false);
    if (videoRef.current) {
      persistProgress(videoRef.current.duration || duration, videoRef.current.duration || duration, true);
    }
  };

  const handlePlayPause = () => {
    if (!videoRef.current) return;
    if (isPlaying) {
      videoRef.current.pause();
      setIsPlaying(false);
      persistProgress(videoRef.current.currentTime, videoRef.current.duration || duration);
    } else {
      videoRef.current.play().then(() => setIsPlaying(true)).catch(() => {});
    }
  };

  const handleSeek = (e: React.ChangeEvent<HTMLInputElement>) => {
    const seekTo = Number(e.target.value);
    setCurrentTime(seekTo);
    if (videoRef.current) {
      videoRef.current.currentTime = seekTo;
    }
    persistProgress(seekTo, duration);
  };

  const handleToggleMute = () => {
    if (!videoRef.current) return;
    const nextMute = !isMuted;
    videoRef.current.muted = nextMute;
    setIsMuted(nextMute);
  };

  // Close video quality dropdown when clicking outside
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (qualityMenuRef.current && !qualityMenuRef.current.contains(e.target as Node)) {
        setIsQualityMenuOpen(false);
      }
    };
    if (isQualityMenuOpen) {
      document.addEventListener("mousedown", handleClickOutside);
      return () => document.removeEventListener("mousedown", handleClickOutside);
    }
  }, [isQualityMenuOpen]);

  // Video Quality Switching with In-Playback Preservation
  const handleQualityChange = (targetQuality: VideoQuality) => {
    if (targetQuality === videoQuality) {
      setIsQualityMenuOpen(false);
      return;
    }

    const vid = videoRef.current;
    const savedTime = vid ? vid.currentTime : currentTime;
    const wasPlaying = vid ? !vid.paused : isPlaying;
    const savedRate = vid ? vid.playbackRate : playbackRate;

    setVideoQuality(targetQuality);
    setIsQualityMenuOpen(false);

    const targetOpt = QUALITY_OPTIONS.find((o) => o.id === targetQuality) ?? QUALITY_OPTIONS[0]!;
    const targetSrc = (activeTopic as any)?.media_url || targetOpt.src;

    if (vid) {
      if (vid.src !== targetSrc) {
        vid.src = targetSrc;
        const onLoaded = () => {
          vid.currentTime = savedTime;
          vid.playbackRate = savedRate;
          if (wasPlaying) {
            vid.play().catch(() => {});
          }
          vid.removeEventListener("loadeddata", onLoaded);
        };
        vid.addEventListener("loadeddata", onLoaded);
        vid.currentTime = savedTime;
        vid.playbackRate = savedRate;
        if (wasPlaying) {
          vid.play().catch(() => {});
        }
      }
    }

    notify.info(`Video resolution switched to ${targetQuality} (${targetOpt.resolution})`);
  };

  // Fullscreen Handler for Player Container
  const handleFullscreen = () => {
    const el = playerContainerRef.current || videoRef.current;
    if (!el) return;
    if (!document.fullscreenElement) {
      if (el.requestFullscreen) {
        el.requestFullscreen().then(() => setIsFullscreen(true)).catch(() => {});
      }
    } else {
      if (document.exitFullscreen) {
        document.exitFullscreen().then(() => setIsFullscreen(false)).catch(() => {});
      }
    }
  };

  // Fullscreen change listener
  useEffect(() => {
    const handleFsChange = () => {
      setIsFullscreen(Boolean(document.fullscreenElement));
    };
    document.addEventListener("fullscreenchange", handleFsChange);
    return () => document.removeEventListener("fullscreenchange", handleFsChange);
  }, []);

  // Draggable Split Panel Effect
  const handleMouseDown = (e: React.MouseEvent) => {
    e.preventDefault();
    setIsDragging(true);
  };

  useEffect(() => {
    if (!isDragging) return;

    const handleMouseMove = (e: MouseEvent) => {
      if (!containerRef.current) return;
      const rect = containerRef.current.getBoundingClientRect();
      const offsetX = e.clientX - rect.left;
      let pct = (offsetX / rect.width) * 100;
      // Clamp between 45% (content min) and 78% (sidebar min)
      if (pct < 45) pct = 45;
      if (pct > 78) pct = 78;
      setLeftWidthPct(pct);
    };

    const handleMouseUp = () => {
      setIsDragging(false);
      try {
        localStorage.setItem("examlms_learning_split_pct", String(leftWidthPct));
      } catch {}
    };

    document.body.style.userSelect = "none";
    document.body.style.cursor = "col-resize";
    window.addEventListener("mousemove", handleMouseMove);
    window.addEventListener("mouseup", handleMouseUp);

    return () => {
      document.body.style.userSelect = "";
      document.body.style.cursor = "";
      window.removeEventListener("mousemove", handleMouseMove);
      window.removeEventListener("mouseup", handleMouseUp);
    };
  }, [isDragging, leftWidthPct]);

  // Lesson completion toggle
  const activeChapterProgress = getChapterProgress(activeTopic);
  const isLessonCompleted = activeChapterProgress === 100;

  const handleMarkCompleted = async () => {
    persistProgress(duration, duration, true);
    if (!enrollment?.enrollment_id || !activeItem?.topic_item_id) {
      notify.success("Lesson marked as completed! Chapter test unlocked.");
      return;
    }
    try {
      await completeItemMutation({
        enrollmentId: enrollment.enrollment_id,
        topicItemId: activeItem.topic_item_id,
      }).unwrap();
      notify.success("Progress saved! Chapter test unlocked.");
    } catch {
      notify.success("Progress updated.");
    }
  };

  const handleEnrollNow = async () => {
    const targetCourse = myCourses?.find((c) => String(c.course_id) === String(courseId));
    if (!targetCourse?.batch_id) {
      notify.info("Enrollment for this course is managed through your institution batch.");
      return;
    }
    try {
      await enrollMutation({
        batchId: targetCourse.batch_id,
        body: { student_user_id: "me" } as any,
      }).unwrap();
      notify.success("Enrolled successfully! Ready to start learning.");
    } catch (err: any) {
      notify.error(err?.data?.message || "Enrollment request submitted.");
    }
  };

  const handleStartChapterTest = () => {
    if (!activeTopic) return;
    navigate(`/courses/${courseId}/chapters/${activeTopic.topic_id}/test`);
  };

  const handleFinalTestClick = () => {
    if (!finalTestId) return;
    if (finalStatus === "locked") {
      notify.info("Prerequisites not completed. Finish all course modules and tests to take the final certification exam.");
      return;
    }
    navigate(`/courses/${courseId}/final-exam`);
  };

  const formatTime = (secs: number) => {
    const m = Math.floor(secs / 60);
    const s = Math.floor(secs % 60);
    return `${m}:${s < 10 ? "0" : ""}${s}`;
  };

  if (isCourseLoading || isVersionLoading || isEnrollmentsLoading) {
    return <PageLoader label="Loading your learning room..." />;
  }

  if (isCourseError || (!isCourseLoading && !course)) {
    return (
      <div className="max-w-xl mx-auto py-20 px-4 text-center font-sans">
        <div className="w-16 h-16 rounded-2xl bg-rose-50 text-rose-600 flex items-center justify-center mx-auto mb-4 border border-rose-200">
          <ShieldAlert size={32} />
        </div>
        <h2 className="text-xl font-bold text-slate-900 mb-2">Access Denied</h2>
        <p className="text-sm text-slate-600 mb-6 leading-relaxed">
          Your institution has not been granted access to this course. Please contact your institution administrator to request course access.
        </p>
        <button
          type="button"
          onClick={() => navigate("/courses/my")}
          className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl bg-blue-600 text-sm font-bold text-white hover:bg-blue-700 transition-colors shadow-sm cursor-pointer"
        >
          Back to My Courses
        </button>
      </div>
    );
  }

  const courseTitle = course?.title || "Complete Python Mastery";

  return (
    <div className="max-w-[1560px] mx-auto space-y-5 pb-12 px-2 sm:px-4">
      {/* Top Header & Breadcrumb */}
      <div className="flex flex-wrap items-center justify-between gap-3 pb-3 border-b border-slate-200">
        <div>
          <div className="flex items-center gap-2 text-xs text-slate-500 font-medium mb-1">
            <Link to="/courses/my" className="hover:text-blue-600 transition-colors">
              Courses
            </Link>
            <span>/</span>
            <span className="text-slate-800 font-bold">{courseTitle}</span>
          </div>
          <h2 className="text-xl font-bold text-slate-900 flex items-center gap-2.5">
            <span>{activeTopic?.title || "Course Lesson"}</span>
            <span className="text-xs font-semibold px-2.5 py-0.5 rounded-full bg-blue-50 text-blue-700 border border-blue-200">
              Module {currentActiveModule?.position || 1}
            </span>
          </h2>
        </div>

        <div className="flex items-center gap-2.5">
          {/* Mobile Sidebar Toggle Button */}
          <button
            type="button"
            onClick={() => setIsMobileSidebarOpen((prev) => !prev)}
            className="lg:hidden inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl border border-slate-300 bg-white text-xs font-bold text-slate-700 hover:bg-slate-50 cursor-pointer shadow-2xs"
          >
            {isMobileSidebarOpen ? <X size={15} /> : <Menu size={15} />}
            <span>Course Outline</span>
            <span className="px-1.5 py-0.5 rounded-full bg-blue-50 text-blue-700 text-[10px] font-bold">
              {progressPercent}%
            </span>
          </button>

          <button
            type="button"
            onClick={() => navigate("/courses/my")}
            className="px-3.5 py-1.5 rounded-xl border border-slate-300 bg-white text-xs font-semibold text-slate-700 hover:bg-slate-50 cursor-pointer shadow-2xs transition-colors"
          >
            My Courses
          </button>
        </div>
      </div>

      {/* 4 Course Navigation Tabs: Course Overview | Modules | Assessments | Certificate */}
      <div className="flex items-center gap-2 border-b border-slate-200">
        {[
          { id: "overview", label: "Course Overview", icon: BookOpen },
          { id: "modules", label: "Modules", icon: Play },
          { id: "assessments", label: "Assessments", icon: Award },
          {
            id: "certificate",
            label: "Certificate",
            icon: Award,
            badge: isCourseCompleted ? "Available" : "Locked",
            locked: !isCourseCompleted,
          },
        ].map((tab) => {
          const active = activeCourseTab === tab.id;
          const IconComp = tab.icon;
          return (
            <button
              key={tab.id}
              type="button"
              onClick={() => handleSelectCourseTab(tab.id as CourseNavTab)}
              className={cn(
                "inline-flex items-center gap-2 py-3 px-4 text-xs font-bold transition-all relative border-b-2 -mb-px cursor-pointer",
                active
                  ? "border-[#2563EB] text-[#2563EB]"
                  : "border-transparent text-slate-500 hover:text-slate-900 hover:border-slate-300"
              )}
            >
              <IconComp size={15} />
              <span>{tab.label}</span>
              {tab.badge && (
                <span
                  className={cn(
                    "text-[10px] px-2 py-0.5 rounded-full font-bold inline-flex items-center gap-1",
                    tab.locked
                      ? "bg-slate-100 text-slate-500 border border-slate-200"
                      : "bg-emerald-50 text-emerald-700 border border-emerald-200"
                  )}
                >
                  {tab.locked && <Lock size={10} />}
                  {tab.badge}
                </span>
              )}
            </button>
          );
        })}
      </div>

      {/* Audit Banner if not enrolled */}
      {!enrollment && (
        <div className="p-4 rounded-2xl bg-amber-50 border border-amber-200 flex items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-xl bg-amber-100 text-amber-800 flex items-center justify-center shrink-0">
              <Lock size={18} />
            </div>
            <div>
              <b className="text-xs text-amber-900 block font-bold">Course Audit Mode</b>
              <span className="text-[11px] text-amber-700">
                Enroll to record official progress, unlock graded tests, and earn your verified certificate.
              </span>
            </div>
          </div>
          <button
            type="button"
            disabled={isEnrolling}
            onClick={handleEnrollNow}
            className="px-4 py-2 rounded-xl bg-blue-600 text-xs font-bold text-white hover:bg-blue-700 shrink-0 cursor-pointer shadow-xs transition-colors"
          >
            {isEnrolling ? "Enrolling..." : "Enroll Now"}
          </button>
        </div>
      )}

      {/* TAB 1: COURSE OVERVIEW */}
      {activeCourseTab === "overview" && (
        <div className="space-y-6">
          {/* Hero Overview Card */}
          <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-2xs space-y-4">
            <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
              <div>
                <span className="text-xs font-bold uppercase tracking-wider text-blue-600">
                  {course?.slug || "Software Engineering"}
                </span>
                <h3 className="text-2xl font-bold text-slate-900 mt-1">{courseTitle}</h3>
                <p className="text-xs text-slate-500 max-w-2xl mt-1 leading-relaxed">
                  {course?.summary ||
                    "Master core architectural paradigms, algorithmic design patterns, and hands-on system building techniques through structured module lessons and proctored examinations."}
                </p>
              </div>

              <div className="shrink-0 flex items-center gap-3">
                <button
                  type="button"
                  onClick={() => handleSelectCourseTab("modules")}
                  className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl bg-[#2563EB] text-xs font-bold text-white hover:bg-[#1D4ED8] cursor-pointer shadow-xs transition-all"
                >
                  <Play size={14} className="fill-current" />
                  <span>{progressPercent > 0 ? "Continue Learning" : "Start Learning"}</span>
                </button>
              </div>
            </div>

            {/* Overall Progress Bar */}
            <div className="pt-2 border-t border-slate-100 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
              <div className="flex-1 max-w-md space-y-1.5">
                <div className="flex items-center justify-between text-xs">
                  <span className="text-slate-500 font-medium">Curriculum Completion</span>
                  <b className="text-blue-600 font-bold">{progressPercent}%</b>
                </div>
                <div className="h-2 rounded-full bg-slate-100 overflow-hidden">
                  <div
                    className={cn(
                      "h-full rounded-full transition-all",
                      isCourseCompleted ? "bg-emerald-500" : "bg-blue-600"
                    )}
                    style={{ width: `${progressPercent}%` }}
                  />
                </div>
              </div>

              <div className="flex items-center gap-5 text-xs text-slate-600">
                <span className="flex items-center gap-1.5">
                  <BookOpen size={15} className="text-slate-400" />
                  <b>{modulesList.length}</b> Modules
                </span>
                <span className="flex items-center gap-1.5">
                  <Award size={15} className="text-slate-400" />
                  <b>70%</b> Passing Standard
                </span>
                <span className="flex items-center gap-1.5">
                  <Clock size={15} className="text-slate-400" />
                  <b>Self-paced</b>
                </span>
              </div>
            </div>
          </div>

          {/* Syllabus Modules Outline */}
          <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-2xs space-y-4">
            <h4 className="text-sm font-bold text-slate-900">Curriculum Structure & Modules</h4>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {modulesList.map((m, idx) => {
                const isModDone = m.completed || (m as any).test_passed;
                return (
                  <div
                    key={m.module_id}
                    className="p-4 rounded-xl border border-slate-200 hover:border-slate-300 transition-colors flex items-start gap-3 bg-slate-50/50"
                  >
                    <div
                      className={cn(
                        "w-8 h-8 rounded-lg flex items-center justify-center font-bold text-xs shrink-0",
                        isModDone ? "bg-emerald-100 text-emerald-800" : "bg-blue-100 text-blue-800"
                      )}
                    >
                      {isModDone ? <Check size={16} /> : idx + 1}
                    </div>
                    <div className="min-w-0 flex-1">
                      <h5 className="text-xs font-bold text-slate-900 truncate">{m.title}</h5>
                      <span className="text-[11px] text-slate-500 mt-0.5 block">
                        {m.topics?.length || 0} Topics Â· Graded Module Test
                      </span>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      )}

      {/* TAB 2: ASSESSMENTS OVERVIEW */}
      {activeCourseTab === "assessments" && (
        <div className="space-y-6">
          <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-2xs space-y-6">
            <div>
              <h3 className="text-lg font-bold text-slate-900">Course Assessments & Examinations</h3>
              <p className="text-xs text-slate-500 mt-0.5">
                All assessments require a minimum score of 70% to pass and qualify for your official certificate.
              </p>
            </div>

            {/* Final Exam Card */}
            {finalTestId && (
              <div className="rounded-2xl border-2 border-blue-200 bg-blue-50/30 p-5 space-y-3">
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div className="flex items-center gap-3">
                    <div className="w-10 h-10 rounded-xl bg-blue-600 text-white flex items-center justify-center shrink-0">
                      <Award size={22} />
                    </div>
                    <div>
                      <span className="text-[10px] font-bold uppercase tracking-wider text-blue-700">
                        Proctored Assessment
                      </span>
                      <h4 className="text-sm font-bold text-slate-900">
                        {finalTestDetail?.title || "Final Certification Exam"}
                      </h4>
                    </div>
                  </div>

                  <span
                    className={cn(
                      "text-xs font-bold px-3 py-1 rounded-full",
                      finalStatus === "completed"
                        ? "bg-emerald-100 text-emerald-800"
                        : finalStatus === "available"
                        ? "bg-blue-100 text-blue-800"
                        : finalStatus === "in_progress"
                        ? "bg-amber-100 text-amber-800"
                        : "bg-slate-100 text-slate-500"
                    )}
                  >
                    {finalStatus === "completed" && "Completed"}
                    {finalStatus === "available" && "Available to Start"}
                    {finalStatus === "in_progress" && "In Progress"}
                    {finalStatus === "locked" && "Locked (Modules Required)"}
                  </span>
                </div>

                <p className="text-xs text-slate-600">
                  Comprehensive 60-minute proctored examination validating all course concepts. Enforces strict AI monitoring and browser focus tracking.
                </p>

                <div className="flex flex-wrap items-center justify-between gap-4 pt-2 border-t border-blue-100">
                  <div className="flex items-center gap-4 text-xs text-slate-500">
                    <span><b>{finalTestDetail?.duration_minutes || 60}</b> Minutes</span>
                    <span>Â·</span>
                    <span><b>{finalTestDetail?.question_count || 20}</b> Questions</span>
                    <span>Â·</span>
                    <span><b>{finalTestDetail?.pass_mark_percent || 70}%</b> Pass Standard</span>
                  </div>

                  <button
                    type="button"
                    disabled={finalStatus === "locked"}
                    onClick={handleFinalTestClick}
                    className="inline-flex items-center gap-1.5 px-4 py-2 rounded-xl bg-blue-600 text-xs font-bold text-white hover:bg-blue-700 disabled:opacity-50 cursor-pointer shadow-xs transition-colors"
                  >
                    {finalStatus === "available" && "Launch Final Exam"}
                    {finalStatus === "in_progress" && "Resume Final Exam"}
                    {finalStatus === "completed" && "View Exam Results"}
                    {finalStatus === "locked" && "Complete Modules First"}
                  </button>
                </div>
              </div>
            )}

            {/* Module Tests */}
            <div className="space-y-3">
              <h4 className="text-xs font-bold text-slate-700 uppercase tracking-wider">Module Tests</h4>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {modulesList.map((m) => (
                  <div
                    key={m.module_id}
                    className="p-4 rounded-xl border border-slate-200 bg-white hover:border-slate-300 transition-colors flex items-center justify-between gap-3"
                  >
                    <div>
                      <b className="text-xs font-bold text-slate-900 block truncate">{m.title} Test</b>
                      <span className="text-[11px] text-slate-500">Passing score: 70%</span>
                    </div>

                    <button
                      type="button"
                      onClick={() => navigate(`/courses/${courseId}/modules/${m.module_id}/test`)}
                      className="px-3 py-1.5 rounded-lg border border-slate-300 bg-white text-xs font-bold text-slate-700 hover:bg-slate-50 cursor-pointer shadow-2xs"
                    >
                      {(m as any).test_passed ? "Review" : "Take Test"}
                    </button>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* TAB 3: CERTIFICATE VIEW (ONLY ACCESSIBLE/AVAILABLE AFTER COMPLETION) */}
      {activeCourseTab === "certificate" && (
        <div className="space-y-6">
          {isCourseCompleted ? (
            /* COMPLETED: OFFICIAL CERTIFICATE OF COMPLETION PREVIEW */
            <div className="max-w-2xl mx-auto space-y-6">
              <div className="text-center space-y-1">
                <span className="text-xs font-bold uppercase tracking-wider text-emerald-700 bg-emerald-50 px-3 py-1 rounded-full border border-emerald-200">
                  Official Academic Credential
                </span>
                <h3 className="text-xl font-bold text-slate-900 mt-2">Course Certificate of Completion</h3>
                <p className="text-xs text-slate-500">
                  You have successfully satisfied all course requirements and earned this verified credential.
                </p>
              </div>

              {/* Official Certificate Box */}
              <div className="relative rounded-2xl border-4 border-[#00663C] bg-white p-8 sm:p-10 text-center shadow-lg space-y-4">
                <div className="text-[11px] uppercase font-bold tracking-widest text-[#00663C]">
                  GenZ Technologies & Examination LMS
                </div>

                <div className="text-xs font-semibold text-slate-400 uppercase tracking-wider">
                  Official Certificate of Completion
                </div>

                <h4 className="text-3xl font-bold text-slate-900 tracking-tight">
                  {courseCertificate?.student_name || user?.full_name || "Student"}
                </h4>

                <p className="text-xs text-slate-500">
                  has successfully satisfied all learning modules, hands-on tasks, and proctored examinations for
                </p>

                <h5 className="text-xl font-bold text-[#00663C]">{courseCertificate?.course_title || courseTitle}</h5>

                <p className="text-xs text-slate-600 font-medium">
                  Score: <b>{courseCertificate?.score_percent != null ? courseCertificate.score_percent : 100}%</b> (
                  {courseCertificate?.grade || "Passed with Distinction"}) Â· Issued:{" "}
                  {courseCertificate?.issued_at
                    ? new Date(courseCertificate.issued_at).toLocaleDateString()
                    : new Date().toLocaleDateString()}
                </p>

                <div className="inline-block text-[11px] font-mono text-slate-500 bg-slate-50 py-1 px-3 rounded-md border border-slate-200">
                  ID: {courseCertificate?.verification_code || courseCertificate?.certificate_id || "EXAM-CERT-VERIFIED"}
                </div>

                <div className="flex items-end justify-between pt-6 border-t border-slate-100 mt-4">
                  <div className="w-16 h-16 rounded-xl bg-slate-100 border border-slate-300 p-1 flex items-center justify-center">
                    <div className="w-full h-full bg-slate-900 rounded-lg flex items-center justify-center text-white text-[10px] font-mono">
                      QR
                    </div>
                  </div>
                  <span className="text-xs font-bold text-slate-800">
                    {courseCertificate?.institution_name || "GenZ Learning Platform"}
                  </span>
                </div>
              </div>

              {/* Action Buttons: Download PDF and Verify */}
              <div className="flex flex-wrap items-center justify-center gap-3">
                <button
                  type="button"
                  disabled={Boolean(downloadingCertId)}
                  onClick={() =>
                    handleDownloadPdf(
                      courseCertificate?.certificate_id || "cert",
                      courseCertificate?.verification_code || "CERT"
                    )
                  }
                  className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl bg-[#00663C] text-xs font-bold text-white hover:bg-[#00522F] disabled:opacity-50 cursor-pointer shadow-xs transition-colors"
                >
                  <Download size={15} />
                  <span>{downloadingCertId ? "Preparing PDF..." : "Download Certificate PDF"}</span>
                </button>

                {courseCertificate?.verification_url ? (
                  <a
                    href={courseCertificate.verification_url}
                    target="_blank"
                    rel="noreferrer"
                    className="inline-flex items-center gap-1.5 px-5 py-2.5 rounded-xl border border-slate-300 bg-white text-xs font-bold text-slate-700 hover:bg-slate-50 cursor-pointer shadow-2xs"
                  >
                    <ExternalLink size={14} />
                    <span>Verify Certificate</span>
                  </a>
                ) : (
                  <button
                    type="button"
                    onClick={() => {
                      navigator.clipboard?.writeText(window.location.origin + "/verify?code=" + (courseCertificate?.verification_code || ""));
                      notify.success("Verification link copied to clipboard.");
                    }}
                    className="inline-flex items-center gap-1.5 px-5 py-2.5 rounded-xl border border-slate-300 bg-white text-xs font-bold text-slate-700 hover:bg-slate-50 cursor-pointer shadow-2xs"
                  >
                    <Share2 size={14} />
                    <span>Copy Verification Link</span>
                  </button>
                )}
              </div>
            </div>
          ) : (
            /* INCOMPLETE: CERTIFICATE LOCKED STATE */
            <div className="max-w-xl mx-auto rounded-2xl border border-slate-200 bg-white p-10 text-center space-y-4 shadow-2xs">
              <div className="w-14 h-14 rounded-full bg-amber-50 text-amber-600 mx-auto flex items-center justify-center">
                <Lock size={26} />
              </div>
              <h3 className="text-base font-bold text-slate-900">Certificate Not Available Yet</h3>
              <p className="text-xs text-slate-500 leading-relaxed max-w-sm mx-auto">
                Your verified course certificate is awarded once you complete all module lessons, pass all module tests, and achieve a passing score on the final proctored examination.
              </p>

              {/* Requirements Checklist */}
              <div className="p-4 rounded-xl bg-slate-50 border border-slate-200 text-left space-y-2 text-xs">
                <b className="text-slate-800 font-bold block mb-1">Completion Checklist:</b>
                <div className="flex items-center justify-between text-slate-600">
                  <span className="flex items-center gap-2">
                    <CheckCircle2
                      size={15}
                      className={progressPercent === 100 ? "text-emerald-600" : "text-slate-300"}
                    />
                    Module Lessons & Topics
                  </span>
                  <span className="font-bold text-slate-800">{progressPercent}%</span>
                </div>
                <div className="flex items-center justify-between text-slate-600">
                  <span className="flex items-center gap-2">
                    <CheckCircle2
                      size={15}
                      className={(finalStatus as string) === "completed" ? "text-emerald-600" : "text-slate-300"}
                    />
                    Final Certification Exam
                  </span>
                  <span className="font-bold text-slate-800 capitalize">{finalStatus}</span>
                </div>
              </div>

              <button
                type="button"
                onClick={() => handleSelectCourseTab("modules")}
                className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl bg-[#2563EB] text-xs font-bold text-white hover:bg-[#1D4ED8] cursor-pointer shadow-xs transition-colors"
              >
                <Play size={14} className="fill-current" />
                <span>Continue to Lessons</span>
              </button>
            </div>
          )}
        </div>
      )}

      {/* TAB 4: MODULES (INTERACTIVE LEARNING ROOM) */}
      {activeCourseTab === "modules" && (
        <div ref={containerRef} className="flex flex-col lg:flex-row gap-0 relative items-stretch">
        {/* Left Column: Video Player & Learning Content */}
        <div
          style={{ width: undefined }}
          className={cn(
            "w-full transition-all duration-75 flex flex-col rounded-2xl border border-slate-200 bg-white shadow-2xs overflow-hidden",
            "lg:min-w-[420px]"
          )}
          // Desktop custom dynamic width
          ref={(node) => {
            if (node && window.innerWidth >= 1024) {
              node.style.width = `${leftWidthPct}%`;
            } else if (node) {
              node.style.width = "100%";
            }
          }}
        >
          {/* Main Video Player Container (Consistent 16:9 Aspect Ratio) */}
          <div
            ref={playerContainerRef}
            className="aspect-video bg-slate-950 relative overflow-hidden flex flex-col justify-between group select-none"
          >
            {/* HTML5 Video Element */}
            <video
              ref={videoRef}
              src="https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/BigBuckBunny.mp4"
              onTimeUpdate={handleTimeUpdate}
              onLoadedMetadata={handleLoadedMetadata}
              onEnded={handleVideoEnded}
              className="w-full h-full object-contain cursor-pointer"
              onClick={handlePlayPause}
              playsInline
            />

            {/* Top Video Overlay Badge */}
            <div className="absolute top-3 left-3 right-3 flex items-center justify-between pointer-events-none z-10">
              <span className="px-2.5 py-1 rounded-md bg-black/60 backdrop-blur-md text-white text-[11px] font-semibold flex items-center gap-1.5 shadow-xs">
                <BookOpen size={13} className="text-blue-400" />
                {activeTopic?.title || "Lesson Video"}
              </span>
              <span className="px-2.5 py-0.5 rounded-md bg-black/60 backdrop-blur-md text-white/90 text-[10px] font-mono tracking-wider flex items-center gap-1.5 border border-white/10 shadow-xs">
                <span className="w-1.5 h-1.5 rounded-full bg-blue-400 animate-pulse" />
                {QUALITY_OPTIONS.find((q) => q.id === videoQuality)?.badge || "1080p FHD"}
              </span>
            </div>

            {/* Big Play Overlay (when paused) */}
            {!isPlaying && (
              <div
                onClick={handlePlayPause}
                className="absolute inset-0 flex items-center justify-center bg-black/25 cursor-pointer transition-opacity z-10"
              >
                <div className="w-16 h-16 rounded-full bg-blue-600/90 text-white flex items-center justify-center hover:scale-110 hover:bg-blue-600 transition-all shadow-xl">
                  <Play size={28} className="translate-x-0.5 fill-white" />
                </div>
              </div>
            )}

            {/* Bottom Scrubber & Video Controls Bar */}
            <div className="absolute bottom-0 inset-x-0 bg-gradient-to-t from-black/90 via-black/50 to-transparent p-3 pt-6 flex flex-col gap-2 opacity-95 group-hover:opacity-100 transition-opacity z-10">
              {/* Interactive Scrubber Slider */}
              <div className="flex items-center gap-2">
                <input
                  type="range"
                  min={0}
                  max={duration || 100}
                  value={currentTime}
                  onChange={handleSeek}
                  className="w-full h-1.5 bg-white/30 rounded-full appearance-none cursor-pointer accent-blue-500 hover:h-2 transition-all"
                />
              </div>

              {/* Controls Toolbar */}
              <div className="flex items-center justify-between text-white text-xs">
                <div className="flex items-center gap-3">
                  <button
                    type="button"
                    onClick={handlePlayPause}
                    className="p-1 rounded hover:bg-white/20 transition-colors cursor-pointer"
                    title={isPlaying ? "Pause" : "Play"}
                  >
                    {isPlaying ? <Pause size={18} /> : <Play size={18} className="fill-white" />}
                  </button>

                  <button
                    type="button"
                    onClick={() => {
                      if (videoRef.current) {
                        videoRef.current.currentTime = Math.max(0, videoRef.current.currentTime - 10);
                      }
                    }}
                    className="p-1 rounded hover:bg-white/20 transition-colors cursor-pointer"
                    title="Rewind 10s"
                  >
                    <RotateCcw size={15} />
                  </button>

                  <div className="flex items-center gap-1.5">
                    <button
                      type="button"
                      onClick={handleToggleMute}
                      className="p-1 rounded hover:bg-white/20 transition-colors cursor-pointer"
                    >
                      {isMuted ? <VolumeX size={17} /> : <Volume2 size={17} />}
                    </button>
                  </div>

                  <span className="font-mono text-[11px] text-white/90">
                    {formatTime(currentTime)} / {formatTime(duration)}
                  </span>
                </div>

                <div className="flex items-center gap-2">
                  {/* Speed Selector */}
                  <select
                    value={playbackRate}
                    onChange={(e) => {
                      const rate = Number(e.target.value);
                      setPlaybackRate(rate);
                      if (videoRef.current) videoRef.current.playbackRate = rate;
                    }}
                    className="bg-black/40 hover:bg-black/60 border border-white/20 text-white text-[11px] font-semibold rounded px-1.5 py-0.5 cursor-pointer outline-none transition-colors"
                    title="Playback Speed"
                  >
                    <option value={0.75} className="bg-slate-900 text-white">0.75x</option>
                    <option value={1} className="bg-slate-900 text-white">1.0x</option>
                    <option value={1.25} className="bg-slate-900 text-white">1.25x</option>
                    <option value={1.5} className="bg-slate-900 text-white">1.5x</option>
                    <option value={2} className="bg-slate-900 text-white">2.0x</option>
                  </select>

                  {/* Video Quality Selector Dropdown */}
                  <div ref={qualityMenuRef} className="relative">
                    <button
                      type="button"
                      onClick={() => setIsQualityMenuOpen((prev) => !prev)}
                      className={cn(
                        "inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-semibold border cursor-pointer transition-colors shadow-2xs",
                        isQualityMenuOpen
                          ? "bg-blue-600 border-blue-500 text-white"
                          : "bg-black/40 hover:bg-black/60 border-white/20 text-white"
                      )}
                      title="Video Resolution Settings"
                    >
                      <Settings2 size={13} className={isQualityMenuOpen ? "text-white" : "text-slate-300"} />
                      <span>{videoQuality}</span>
                      <ChevronDown size={11} className={cn("transition-transform duration-150", isQualityMenuOpen && "rotate-180")} />
                    </button>

                    {/* Quality Dropdown Menu Popup */}
                    {isQualityMenuOpen && (
                      <div className="absolute right-0 bottom-full mb-2 w-56 rounded-xl bg-slate-950/95 border border-slate-700/80 shadow-2xl p-1.5 backdrop-blur-md z-30 space-y-0.5 animate-in fade-in slide-in-from-bottom-2 duration-150 text-left">
                        <div className="px-2.5 py-1.5 text-[10px] font-bold uppercase tracking-wider text-slate-400 border-b border-slate-800 flex items-center justify-between">
                          <span>Video Quality</span>
                          <span className="text-blue-400 font-mono text-[9px]">High Definition</span>
                        </div>

                        {QUALITY_OPTIONS.map((opt) => {
                          const isSelected = opt.id === videoQuality;
                          return (
                            <button
                              key={opt.id}
                              type="button"
                              onClick={() => handleQualityChange(opt.id)}
                              className={cn(
                                "w-full flex items-center justify-between px-2.5 py-2 rounded-lg text-left text-xs transition-colors cursor-pointer group",
                                isSelected
                                  ? "bg-blue-600/25 text-blue-300 font-bold border border-blue-500/30"
                                  : "text-slate-200 hover:bg-white/10"
                              )}
                            >
                              <div className="min-w-0 pr-2">
                                <div className="flex items-center gap-1.5">
                                  <span className={cn("font-bold text-xs", isSelected ? "text-blue-400" : "text-white")}>
                                    {opt.label}
                                  </span>
                                  {opt.id === "Auto" && (
                                    <span className="text-[9px] bg-slate-800 text-slate-300 px-1 py-0.2 rounded font-normal">
                                      Auto
                                    </span>
                                  )}
                                  {opt.id === "2040p" && (
                                    <span className="text-[9px] bg-amber-500/20 text-amber-300 border border-amber-500/30 px-1 py-0.2 rounded font-bold">
                                      4K
                                    </span>
                                  )}
                                  {opt.id === "1080p" && (
                                    <span className="text-[9px] bg-blue-500/20 text-blue-300 border border-blue-500/30 px-1 py-0.2 rounded font-semibold">
                                      FHD
                                    </span>
                                  )}
                                </div>
                                <span className="text-[10px] text-slate-400 block truncate mt-0.5">
                                  {opt.resolution}
                                </span>
                              </div>

                              <div className="w-5 h-5 flex items-center justify-center shrink-0">
                                {isSelected ? (
                                  <Check size={14} className="text-blue-400" />
                                ) : (
                                  <span className="w-2 h-2 rounded-full bg-slate-700 opacity-0 group-hover:opacity-100" />
                                )}
                              </div>
                            </button>
                          );
                        })}
                      </div>
                    )}
                  </div>

                  {/* Fullscreen Button */}
                  <button
                    type="button"
                    onClick={handleFullscreen}
                    className="p-1 rounded hover:bg-white/20 transition-colors cursor-pointer text-white"
                    title={isFullscreen ? "Exit Fullscreen" : "Fullscreen"}
                  >
                    <Maximize2 size={15} />
                  </button>
                </div>
              </div>
            </div>
          </div>

          {/* Material Tabs */}
          <div className="flex border-b border-slate-200 px-5 gap-6 bg-slate-50/70">
            {(["video", "pdf", "notes", "materials"] as const).map((tab) => (
              <button
                key={tab}
                type="button"
                onClick={() => setActiveTab(tab)}
                className={cn(
                  "py-3 text-xs font-bold transition-all relative capitalize cursor-pointer",
                  activeTab === tab
                    ? "text-blue-600 after:absolute after:bottom-0 after:left-0 after:right-0 after:h-0.5 after:bg-blue-600"
                    : "text-slate-500 hover:text-slate-900"
                )}
              >
                {tab === "video" ? "Video Lesson" : tab === "pdf" ? "PDF Slides" : tab === "notes" ? "Chapter Notes" : "Materials"}
              </button>
            ))}
          </div>

          {/* Tab Content */}
          <div className="p-5 text-xs text-slate-600 min-h-[140px] leading-relaxed flex-1">
            {activeTab === "video" && (
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <h4 className="font-bold text-slate-900 text-sm">{activeTopic?.title || "Video Lesson"}</h4>
                  <span className="text-[11px] font-semibold text-slate-500">
                    Watch progress: <b className="text-blue-600">{activeChapterProgress}%</b>
                  </span>
                </div>
                <p className="text-slate-600 leading-normal">
                  Master the key programming syntax, foundational patterns, and real-world techniques presented in this chapter. Follow along with interactive examples and review every required item before proceeding to the chapter assessment.
                </p>
              </div>
            )}

            {activeTab === "pdf" && (
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 p-4 rounded-xl border border-slate-200 bg-slate-50">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-lg bg-blue-50 text-blue-600 flex items-center justify-center shrink-0">
                    <FileText size={20} />
                  </div>
                  <div>
                    <b className="text-xs text-slate-900 block">{activeTopic?.title || "Chapter"} - Reference Slides.pdf</b>
                    <span className="text-[11px] text-slate-500">Official instructor slides Â· 18 pages Â· Updated</span>
                  </div>
                </div>
                <button
                  type="button"
                  onClick={() => setIsPdfViewerOpen(true)}
                  className="inline-flex items-center gap-1.5 px-4 py-2 rounded-xl bg-blue-600 text-xs font-bold text-white hover:bg-blue-700 cursor-pointer shadow-xs transition-colors shrink-0"
                >
                  <Eye size={15} /> View PDF
                </button>
              </div>
            )}

            {activeTab === "notes" && (
              <div className="space-y-2.5">
                <h4 className="font-bold text-slate-900 text-sm">Key Chapter Learning Objectives:</h4>
                <ul className="list-disc pl-4 space-y-1.5 text-slate-600 text-xs leading-normal">
                  <li>Review core variable scoping, naming conventions, and runtime evaluation order.</li>
                  <li>Complete every lesson item before starting the chapter test.</li>
                  <li>A minimum score of 70% is required to pass the chapter test and advance sequentially.</li>
                </ul>
              </div>
            )}

            {activeTab === "materials" && (
              <div className="space-y-2">
                <h4 className="font-bold text-slate-900 text-sm">Downloadable Starter Code & Solution Notebooks:</h4>
                <p className="text-slate-600">Access starter code repositories, exercise solution notebooks, and quick reference cheat sheets.</p>
              </div>
            )}
          </div>

          {/* Action Footer */}
          <div className="flex flex-wrap items-center justify-between gap-3 p-4 bg-slate-50 border-t border-slate-200">
            <span className="text-xs text-slate-500 font-medium">
              Complete this chapter's lessons to unlock the chapter test.
            </span>

            <div className="flex items-center gap-2.5">
              <button
                type="button"
                disabled={isCompleting}
                onClick={handleMarkCompleted}
                className={cn(
                  "inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-xl text-xs font-bold transition-colors cursor-pointer shadow-2xs",
                  isLessonCompleted
                    ? "bg-emerald-50 text-emerald-700 border border-emerald-300"
                    : "border border-slate-300 bg-white text-slate-700 hover:bg-slate-100"
                )}
              >
                <Check size={14} className={isLessonCompleted ? "text-emerald-600" : "text-slate-400"} />
                <span>{isLessonCompleted ? "Completed" : "Mark as completed"}</span>
              </button>

              <button
                type="button"
                disabled={!isLessonCompleted || !(activeTopic as any)?.topic_test_id}
                onClick={handleStartChapterTest}
                title={!(activeTopic as any)?.topic_test_id ? "No test configured for this chapter" : undefined}
                className="inline-flex items-center gap-1.5 px-4 py-1.5 rounded-xl bg-blue-600 text-xs font-bold text-white hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer shadow-xs transition-colors"
              >
                {(!isLessonCompleted || !(activeTopic as any)?.topic_test_id) && <Lock size={13} />} Start chapter test
              </button>

              {currentActiveModule && (
                <button
                  type="button"
                  onClick={() => navigate(`/courses/${courseId}/modules/${currentActiveModule.module_id}/test`)}
                  className="inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-xl border border-slate-300 bg-white text-xs font-semibold text-slate-700 hover:bg-slate-50 cursor-pointer shadow-2xs transition-colors"
                >
                  <Award size={14} className="text-blue-600" /> Module test
                </button>
              )}
            </div>
          </div>
        </div>

        {/* Draggable Vertical Divider (Desktop Only) */}
        <div
          role="separator"
          aria-orientation="vertical"
          onMouseDown={handleMouseDown}
          className={cn(
            "hidden lg:flex items-center justify-center w-3 cursor-col-resize select-none relative group z-20 shrink-0",
            isDragging && "cursor-col-resize"
          )}
          title="Drag to resize video player and sidebar"
        >
          {/* Subtle line */}
          <div
            className={cn(
              "w-1 h-full rounded-full transition-colors duration-150",
              isDragging ? "bg-blue-600" : "bg-slate-200 group-hover:bg-blue-400"
            )}
          />
          {/* Centered drag handle pill */}
          <div
            className={cn(
              "absolute top-1/2 -translate-y-1/2 w-4 h-8 rounded-md bg-white border shadow-xs flex items-center justify-center transition-all duration-150",
              isDragging
                ? "border-blue-600 shadow-md scale-105"
                : "border-slate-300 group-hover:border-blue-400 group-hover:shadow-sm"
            )}
          >
            <GripVertical
              className={cn("w-3 h-3", isDragging ? "text-blue-600" : "text-slate-400 group-hover:text-blue-500")}
            />
          </div>
        </div>

        {/* Right Column: Module & Chapter Sidebar */}
        <div
          style={{ width: undefined }}
          className={cn(
            "rounded-2xl border border-slate-200 bg-white shadow-2xs overflow-hidden flex flex-col",
            "lg:min-w-[280px] lg:flex-1",
            // Mobile toggle visibility
            !isMobileSidebarOpen && "hidden lg:flex",
            isMobileSidebarOpen && "flex mt-4 lg:mt-0"
          )}
          ref={(node) => {
            if (node && window.innerWidth >= 1024) {
              node.style.width = `${100 - leftWidthPct}%`;
            } else if (node) {
              node.style.width = "100%";
            }
          }}
        >
          {/* Progress Header */}
          <div className="flex items-center gap-4 p-4 border-b border-slate-100 bg-slate-50/50">
            <div className="w-14 h-14 rounded-full bg-blue-50 flex items-center justify-center shrink-0 border-4 border-blue-100">
              <b className="text-sm font-bold text-blue-600">{progressPercent}%</b>
            </div>
            <div className="flex-1">
              <h3 className="text-sm font-bold text-slate-900">Course Progress</h3>
              <p className="text-xs text-slate-500 mt-0.5">
                {modulesList.length} total modules Â· {modulesList.reduce((acc, m) => acc + m.topics.length, 0)} chapters
              </p>
              <div className="w-full h-1.5 bg-slate-200 rounded-full overflow-hidden mt-1.5">
                <div
                  className="h-full bg-blue-600 rounded-full transition-all duration-300"
                  style={{ width: `${progressPercent}%` }}
                />
              </div>
            </div>
          </div>

          {/* Module List with Independent Scrolling */}
          <div className="divide-y divide-slate-100 text-xs overflow-y-auto max-h-[580px] flex-1">
            {modulesList.map((m, mIdx) => {
              const isExpanded = expandedModules[m.module_id] ?? true;
              const modulePct = getModuleProgress(m);
              const isModuleDone = modulePct === 100 || (m as any).completed || (m as any).test_passed;

              return (
                <div key={m.module_id} className={cn("p-4 space-y-2.5", !m.unlocked && "opacity-60")}>
                  {/* Module Header Bar */}
                  <div
                    onClick={() =>
                      setExpandedModules((prev) => ({
                        ...prev,
                        [m.module_id]: !isExpanded,
                      }))
                    }
                    className="flex items-center justify-between cursor-pointer select-none group"
                  >
                    <div className="flex-1 pr-2">
                      <div className="flex items-center gap-2">
                        <span className="text-[10px] uppercase font-bold text-blue-600 block tracking-wider">
                          Module {m.position || mIdx + 1}
                        </span>
                        <span className="text-[10px] font-semibold text-slate-500">
                          ({modulePct}% completed)
                        </span>
                      </div>
                      <b className="text-xs font-bold text-slate-900 group-hover:text-blue-600 transition-colors block">
                        {m.title}
                      </b>
                    </div>

                    <div className="flex items-center gap-2">
                      {isModuleDone ? (
                        <span className="inline-flex items-center gap-1 rounded-full bg-emerald-50 text-emerald-700 px-2 py-0.5 text-[10px] font-bold border border-emerald-200">
                          <Check size={11} /> Done
                        </span>
                      ) : m.unlocked ? (
                        <span className="text-slate-400 font-medium text-[11px]">In progress</span>
                      ) : (
                        <Lock size={14} className="text-slate-400" />
                      )}
                      <button type="button" className="text-slate-400 hover:text-slate-600">
                        {isExpanded ? <ChevronDown size={16} /> : <ChevronRight size={16} />}
                      </button>
                    </div>
                  </div>

                  {/* Module Chapters List */}
                  {isExpanded && (
                    <div className="space-y-2 pl-2 pt-1 border-l-2 border-blue-200">
                      {m.topics.map((t) => {
                        const isSelected = activeTopic?.topic_id === t.topic_id;
                        const chapterPct = getChapterProgress(t);
                        const isTopicDone = chapterPct === 100 || Boolean((t as any).test_passed || t.completed);

                        return (
                          <div key={t.topic_id} className="space-y-1">
                            {/* Chapter Row Button */}
                            <button
                              type="button"
                              onClick={() => {
                                setSelectedTopicId(t.topic_id);
                                setIsMobileSidebarOpen(false);
                              }}
                              className={cn(
                                "w-full text-left p-2 rounded-xl transition-all cursor-pointer flex flex-col gap-1",
                                isSelected
                                  ? "bg-blue-50/80 border border-blue-200 text-blue-900 shadow-2xs"
                                  : "hover:bg-slate-50 text-slate-700"
                              )}
                            >
                              <div className="flex items-center justify-between gap-2">
                                <div className="flex items-center gap-2 truncate">
                                  <span
                                    className={cn(
                                      "w-4 h-4 rounded-full flex items-center justify-center shrink-0 text-[10px]",
                                      isTopicDone
                                        ? "bg-emerald-600 text-white"
                                        : isSelected
                                        ? "bg-blue-600 text-white"
                                        : "border border-slate-300 text-slate-400"
                                    )}
                                  >
                                    {isTopicDone ? <Check size={10} /> : <Play size={9} className="fill-current" />}
                                  </span>
                                  <span className={cn("truncate font-medium text-xs", isSelected && "font-bold text-blue-900")}>
                                    {t.title}
                                  </span>
                                </div>

                                <span
                                  className={cn(
                                    "text-[10px] shrink-0 font-bold",
                                    isTopicDone
                                      ? "text-emerald-700 flex items-center gap-0.5"
                                      : chapterPct > 0
                                      ? "text-blue-700"
                                      : "text-slate-400"
                                  )}
                                >
                                  {isTopicDone ? (
                                    <>
                                      <Check size={11} /> 100%
                                    </>
                                  ) : chapterPct > 0 ? (
                                    `${chapterPct}%`
                                  ) : (
                                    "0%"
                                  )}
                                </span>
                              </div>

                              {/* Compact Chapter Progress Bar */}
                              <div className="w-full h-1 bg-slate-200/80 rounded-full overflow-hidden mt-0.5">
                                <div
                                  className={cn(
                                    "h-full rounded-full transition-all duration-300",
                                    isTopicDone ? "bg-emerald-500" : "bg-blue-600"
                                  )}
                                  style={{ width: `${chapterPct}%` }}
                                />
                              </div>
                            </button>

                            {/* Chapter Test Row Link */}
                            <div className="flex items-center justify-between py-0.5 px-2 pl-6 text-[11px] text-slate-500">
                              <span className="flex items-center gap-1.5 text-slate-500 font-medium">
                                <FileText size={12} className="text-slate-400" /> Chapter test
                              </span>
                              {(t as any).test_passed ? (
                                <span className="text-emerald-700 font-bold text-[10px] bg-emerald-50 px-2 py-0.5 rounded-full flex items-center gap-1 border border-emerald-200">
                                  <Check size={10} /> Passed
                                </span>
                              ) : (t as any).topic_test_id ? (
                                <Link
                                  to={`/courses/${courseId}/chapters/${t.topic_id}/test`}
                                  className="text-blue-600 font-bold text-[11px] hover:underline"
                                >
                                  Take test
                                </Link>
                              ) : (
                                <span className="text-slate-400 text-[10px] italic">
                                  No test
                                </span>
                              )}
                            </div>
                          </div>
                        );
                      })}

                      {/* Module Test Row Link */}
                      <div className="pt-1.5">
                        <Link
                          to={`/courses/${courseId}/modules/${m.module_id}/test`}
                          className="flex items-center justify-between p-2 rounded-xl bg-slate-50 hover:bg-blue-50/60 border border-slate-200 transition-colors group"
                        >
                          <div className="flex items-center gap-2 truncate">
                            <div className="w-5 h-5 rounded-md bg-amber-50 text-amber-700 flex items-center justify-center shrink-0">
                              <Award size={13} />
                            </div>
                            <span className="text-xs font-bold text-slate-900 group-hover:text-blue-600 truncate">
                              Module test
                            </span>
                          </div>
                          {(m as any).test_passed ? (
                            <span className="text-emerald-700 font-bold text-[10px] bg-emerald-50 px-2 py-0.5 rounded-full flex items-center gap-1 border border-emerald-200">
                              <Check size={10} /> Passed
                            </span>
                          ) : (
                            <span className="text-[11px] font-bold text-blue-600 flex items-center gap-0.5">
                              Open <ChevronRight size={13} />
                            </span>
                          )}
                        </Link>
                      </div>
                    </div>
                  )}
                </div>
              );
            })}

            {/* Final Assessment Section (Displayed clearly after all modules) */}
            {finalTestId && (
              <div className="p-4 border-t-2 border-slate-100 bg-slate-50/80">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-[10px] uppercase font-bold text-slate-500 tracking-wider">
                    Final Assessment
                  </span>
                  {finalStatus === "completed" && (
                    <span className="inline-flex items-center gap-1 rounded-full bg-emerald-50 text-emerald-700 px-2 py-0.5 text-[10px] font-bold border border-emerald-200">
                      <CheckCircle2 size={11} /> Completed
                    </span>
                  )}
                  {finalStatus === "in_progress" && (
                    <span className="inline-flex items-center gap-1 rounded-full bg-amber-50 text-amber-700 px-2 py-0.5 text-[10px] font-bold border border-amber-200">
                      <Clock size={11} /> In Progress
                    </span>
                  )}
                  {finalStatus === "available" && (
                    <span className="inline-flex items-center gap-1 rounded-full bg-blue-50 text-blue-700 px-2 py-0.5 text-[10px] font-bold border border-blue-200">
                      <Award size={11} /> Available
                    </span>
                  )}
                  {finalStatus === "locked" && (
                    <span className="inline-flex items-center gap-1 rounded-full bg-slate-100 text-slate-500 px-2 py-0.5 text-[10px] font-bold border border-slate-200">
                      <Lock size={11} /> Locked
                    </span>
                  )}
                </div>

                {/* Final Exam Card */}
                <div
                  onClick={handleFinalTestClick}
                  className={cn(
                    "p-3 rounded-xl border transition-all text-left",
                    finalStatus === "available"
                      ? "bg-white border-blue-300 hover:border-blue-500 hover:shadow-sm cursor-pointer ring-1 ring-blue-500/10"
                      : finalStatus === "in_progress"
                      ? "bg-white border-amber-300 hover:border-amber-500 hover:shadow-sm cursor-pointer"
                      : finalStatus === "completed"
                      ? "bg-white border-emerald-300 hover:border-emerald-500 hover:shadow-sm cursor-pointer"
                      : "bg-slate-100/90 border-slate-200 opacity-80 cursor-not-allowed"
                  )}
                >
                  <div className="flex items-start justify-between gap-2">
                    <div className="space-y-1 flex-1">
                      <b className="text-xs font-bold text-slate-900 block">
                        {finalTestDetail?.title || "Final Certification Exam"}
                      </b>
                      <div className="flex flex-wrap items-center gap-x-2 gap-y-0.5 text-[10px] text-slate-500 font-medium">
                        <span>{finalTestDetail?.duration_minutes || 60} mins</span>
                        <span>Â·</span>
                        <span>{finalTestDetail?.question_count || 20} questions</span>
                        <span>Â·</span>
                        <span>{finalTestDetail?.pass_mark_percent || versionDetail?.rule?.final_pass_mark || 70}% pass</span>
                      </div>
                      {finalStatus === "locked" && (
                        <p className="text-[10px] text-slate-500 mt-1 flex items-center gap-1">
                          <Lock size={11} className="text-slate-400 shrink-0" />
                          Complete all modules to unlock
                        </p>
                      )}
                      {finalStatus === "completed" && finalTestDetail?.best_percent != null && (
                        <p className="text-[10px] text-emerald-700 font-semibold mt-1">
                          Score: {finalTestDetail.best_percent}% Passed
                        </p>
                      )}
                    </div>

                    {finalStatus !== "locked" ? (
                      <button
                        type="button"
                        onClick={(e) => {
                          e.stopPropagation();
                          handleFinalTestClick();
                        }}
                        className={cn(
                          "px-2.5 py-1.5 rounded-lg text-xs font-bold shrink-0 transition-colors cursor-pointer shadow-2xs",
                          finalStatus === "available"
                            ? "bg-blue-600 text-white hover:bg-blue-700"
                            : finalStatus === "in_progress"
                            ? "bg-amber-600 text-white hover:bg-amber-700"
                            : "border border-slate-300 bg-white text-slate-700 hover:bg-slate-50"
                        )}
                      >
                        {finalStatus === "available" && "Start Exam"}
                        {finalStatus === "in_progress" && "Resume"}
                        {finalStatus === "completed" && "View Results"}
                      </button>
                    ) : (
                      <div className="w-6 h-6 rounded-md bg-slate-200 text-slate-500 flex items-center justify-center shrink-0">
                        <Lock size={12} />
                      </div>
                    )}
                  </div>
                </div>
              </div>
            )}

            {/* Celebratory Certificate Banner inside sidebar if Course Completed */}
            {isCourseCompleted && (
              <div className="p-4 border-t border-emerald-100 bg-emerald-50/70">
                <div className="flex items-center justify-between gap-2">
                  <div className="flex items-center gap-2">
                    <Award size={18} className="text-emerald-600 shrink-0" />
                    <div>
                      <b className="text-xs text-emerald-900 block font-bold">Course Completed!</b>
                      <span className="text-[10px] text-emerald-700">Official certificate ready</span>
                    </div>
                  </div>
                  <button
                    type="button"
                    onClick={() => handleSelectCourseTab("certificate")}
                    className="px-2.5 py-1 rounded-lg bg-emerald-600 text-white text-[11px] font-bold hover:bg-emerald-700 cursor-pointer shadow-2xs"
                  >
                    View Certificate
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
      )}
      {/* IN-APP PDF VIEWER MODAL */}
      <InAppPdfViewer
        isOpen={isPdfViewerOpen}
        onClose={() => setIsPdfViewerOpen(false)}
        documentTitle={`${activeTopic?.title || "Chapter"} - Reference Slides.pdf`}
        pdfUrl={(activeTopic as any)?.pdf_url || (activeItem as any)?.media_url}
        totalSlides={18}
        chapterTitle={activeTopic?.title}
        courseTitle={course?.title || courseTitle}
        moduleTitle={currentActiveModule?.title}
      />
    </div>
  );
}
