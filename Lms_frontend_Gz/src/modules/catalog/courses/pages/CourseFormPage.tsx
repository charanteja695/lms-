import { useState, useEffect, useMemo, useRef } from "react";
import { useNavigate, useParams } from "react-router-dom";
import {
  useGetCourseQuery,
  useGetVersionQuery,
  useCreateCourseMutation,
  useUpdateCourseMutation,
} from "@/modules/catalog/courses/api/coursesApi";
import { ThumbnailUploader } from "@/modules/catalog/courses/components/common/ThumbnailUploader";
import { CoursePageHeader } from "@/modules/catalog/courses/components/common/CoursePageHeader";
import { CourseCreationStepper, type StepperStepItem } from "@/modules/catalog/courses/components/common/CourseCreationStepper";
import { ConfirmModal } from "@/modules/catalog/courses/components/common/ConfirmModal";
import { Icon, PageLoader } from "@/shared/ui";
import { AccessDeniedPage } from "@/shared/pages/AccessDeniedPage";
import { usePermissions } from "@/modules/user-management/common/permissions/usePermissions";
import { useNotify } from "@/core/hooks/useNotify";
import { parseCourseSummary, computeCourseStepsStatus } from "@/modules/catalog/courses/utils/courseMetrics";
import { cn } from "@/core/lib/cn";

export function CourseFormPage() {
  const { permissions, isLoading: isLoadingPerms } = usePermissions();
  const { courseId } = useParams<{ courseId: string }>();
  const isEdit = Boolean(courseId);
  const navigate = useNavigate();
  const notify = useNotify();

  const isAuthorized = permissions.role === "super_admin" || permissions.role === "admin";

  const {
    data: course,
    isLoading: isLoadingCourse,
    isError: isLoadError,
    error: loadError,
    refetch,
  } = useGetCourseQuery(courseId ?? "", {
    skip: !isEdit,
    refetchOnMountOrArgChange: true,
  });

  const versionId = course?.versions?.[course.versions.length - 1]?.version_id;
  const { data: versionDetail } = useGetVersionQuery(
    { courseId: courseId ?? "", versionId: versionId ?? "" },
    { skip: !courseId || !versionId }
  );

  const [createCourse] = useCreateCourseMutation();
  const [updateCourse] = useUpdateCourseMutation();

  // Form states
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [level, setLevel] = useState<"Beginner" | "Intermediate" | "Advanced">("Beginner");
  const [duration, setDuration] = useState("12 hours");
  const [passingPercentage, setPassingPercentage] = useState("70%");
  const [thumbnailUrl, setThumbnailUrl] = useState<string | null>(null);
  const [thumbnailMediaId, setThumbnailMediaId] = useState<string | null>(null);

  const [isSubmitting, setIsSubmitting] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // Initial values tracker for dirty checking
  const initialValuesRef = useRef({
    title: "",
    description: "",
    level: "Beginner",
    duration: "12 hours",
    passingPercentage: "70%",
    thumbnailMediaId: null as string | null,
  });
  const [isInitialized, setIsInitialized] = useState(!isEdit);
  const [isDiscardModalOpen, setIsDiscardModalOpen] = useState(false);
  const [pendingNavigateUrl, setPendingNavigateUrl] = useState<string | null>(null);

  // Initialize fields on load for Edit
  useEffect(() => {
    if (course && isEdit && !isInitialized) {
      const parsed = parseCourseSummary(course.summary);
      const initT = course.title || "";
      const initD = parsed.cleanDescription || "";
      const initL = parsed.level;
      const initDur = parsed.duration === "0h" ? "12 hours" : parsed.duration;
      const initPass = parsed.passPercentage || "70%";
      const initMedia = course.thumbnail_media_id ? String(course.thumbnail_media_id) : null;

      setTitle(initT);
      setDescription(initD);
      setLevel(initL);
      setDuration(initDur);
      setPassingPercentage(initPass);

      if (course.thumbnail_media_id) {
        setThumbnailMediaId(initMedia);
        setThumbnailUrl(`/api/v1/media/stream/${course.thumbnail_media_id}`);
      }

      initialValuesRef.current = {
        title: initT,
        description: initD,
        level: initL,
        duration: initDur,
        passingPercentage: initPass,
        thumbnailMediaId: initMedia,
      };
      setIsInitialized(true);
    }
  }, [course, isEdit, isInitialized]);

  // Dirty check
  const isDirty = useMemo(() => {
    if (!isInitialized) return false;
    const init = initialValuesRef.current;
    return (
      title !== init.title ||
      description !== init.description ||
      level !== init.level ||
      duration !== init.duration ||
      passingPercentage !== init.passingPercentage ||
      thumbnailMediaId !== init.thumbnailMediaId
    );
  }, [title, description, level, duration, passingPercentage, thumbnailMediaId, isInitialized]);

  // Browser beforeunload protection
  useEffect(() => {
    const handleBeforeUnload = (e: BeforeUnloadEvent) => {
      if (isDirty) {
        e.preventDefault();
        e.returnValue = "";
      }
    };
    window.addEventListener("beforeunload", handleBeforeUnload);
    return () => window.removeEventListener("beforeunload", handleBeforeUnload);
  }, [isDirty]);

  // Safe navigation handler checking dirty state
  const handleSafeNavigate = (targetUrl: string) => {
    if (isDirty) {
      setPendingNavigateUrl(targetUrl);
      setIsDiscardModalOpen(true);
    } else {
      navigate(targetUrl);
    }
  };

  const handleConfirmDiscard = () => {
    setIsDiscardModalOpen(false);
    if (pendingNavigateUrl) {
      navigate(pendingNavigateUrl);
    } else {
      navigate(isEdit ? `/courses/${courseId}` : "/courses");
    }
  };

  // Stepper calculations
  const stepsStatus = useMemo(() => {
    return computeCourseStepsStatus(course, versionDetail, false);
  }, [course, versionDetail]);

  const stepperSteps: StepperStepItem[] = useMemo(() => {
    const cid = courseId;
    return [
      {
        id: 1,
        label: "Course details",
        sublabel: isEdit && stepsStatus.step1Done ? "Done" : "Current",
        status: isEdit && stepsStatus.step1Done ? "done" : "current",
        path: cid ? `/courses/${cid}/edit?step=1` : undefined,
      },
      {
        id: 2,
        label: "Modules",
        sublabel: stepsStatus.step2Done ? "Done" : "Not started",
        status: stepsStatus.step2Done ? "done" : "pending",
        path: cid ? `/courses/${cid}?tab=modules&step=2` : undefined,
      },
      {
        id: 3,
        label: "Chapters",
        sublabel: stepsStatus.step3Done ? "Done" : "Not started",
        status: stepsStatus.step3Done ? "done" : "pending",
        path:
          cid && versionDetail?.modules?.[0]?.module_id
            ? `/courses/${cid}/modules/${versionDetail.modules[0].module_id}/chapters?step=3`
            : cid
            ? `/courses/${cid}?tab=modules&step=3`
            : undefined,
      },
      {
        id: 4,
        label: "Approve questions",
        sublabel: stepsStatus.step4Done ? "Done" : "Not started",
        status: stepsStatus.step4Done ? "done" : "pending",
        path: cid ? `/courses/${cid}/questions/review?step=4` : undefined,
      },
      {
        id: 5,
        label: "Final exam",
        sublabel: stepsStatus.step5Done ? "Configured" : "Not started",
        status: stepsStatus.step5Done ? "done" : "pending",
        path: cid ? `/courses/${cid}?tab=final_exam&step=5` : undefined,
      },
    ];
  }, [courseId, isEdit, stepsStatus, versionDetail]);

  if (isLoadingPerms) {
    return <PageLoader label="Checking permissions..." />;
  }

  if (!isAuthorized) {
    return (
      <AccessDeniedPage
        title="Course Authoring Restricted"
        message="Only Platform Administrators and Academic Administrators have permission to create or edit courses."
      />
    );
  }

  if (isEdit && isLoadingCourse) {
    return <PageLoader label="Loading course details..." />;
  }

  if (isEdit && isLoadError) {
    return (
      <div className="flex flex-col items-center justify-center p-16 text-center max-w-md mx-auto">
        <div className="w-12 h-12 rounded-full bg-rose-100 text-rose-600 flex items-center justify-center mb-4">
          <Icon name="alertCircle" size={24} />
        </div>
        <h3 className="text-base font-bold text-slate-900 mb-1">Course not found</h3>
        <p className="text-xs text-slate-500 mb-5">
          {(loadError as any)?.data?.message || "The requested course could not be loaded."}
        </p>
        <div className="flex items-center gap-3">
          <button
            type="button"
            onClick={() => refetch()}
            className="px-4 py-2 rounded-xl border border-slate-300 bg-white text-xs font-semibold text-slate-700 hover:bg-slate-50 cursor-pointer"
          >
            Retry
          </button>
          <button
            type="button"
            onClick={() => navigate("/courses")}
            className="px-4 py-2 rounded-xl bg-[#00663C] text-xs font-bold text-white hover:bg-[#00522F] cursor-pointer"
          >
            Back to courses
          </button>
        </div>
      </div>
    );
  }

  const saveCourseData = async (shouldNavigateToNextStep: boolean) => {
    if (!title.trim()) {
      setErrorMessage("Course name is required");
      return;
    }

    try {
      setIsSubmitting(true);
      setErrorMessage(null);

      const summaryText = `[${level}] [${duration}] [Pass: ${passingPercentage}] ${description.trim()}`;

      if (isEdit && courseId) {
        await updateCourse({
          courseId,
          body: {
            title: title.trim(),
            summary: summaryText,
            thumbnail_media_id: thumbnailMediaId || undefined,
          },
        }).unwrap();
        notify.success("Course updated successfully");

        initialValuesRef.current = {
          title: title.trim(),
          description: description.trim(),
          level,
          duration,
          passingPercentage,
          thumbnailMediaId,
        };

        if (shouldNavigateToNextStep) {
          navigate(`/courses/${courseId}?tab=modules&step=2`);
        } else {
          notify.success("Draft saved");
        }
      } else {
        const slug =
          title.trim().toLowerCase().replace(/[^a-z0-9]+/g, "-") + "-" + Date.now().toString(36);
        const res = await createCourse({
          title: title.trim(),
          slug,
          summary: summaryText,
          thumbnail_media_id: thumbnailMediaId || undefined,
        }).unwrap();
        notify.success("Course created successfully");

        if (shouldNavigateToNextStep) {
          navigate(`/courses/${res.course_id}?tab=modules&step=2`);
        } else {
          navigate(`/courses/${res.course_id}`);
        }
      }
    } catch (err: any) {
      setErrorMessage(err?.data?.message || err?.message || "Failed to save course.");
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    await saveCourseData(true);
  };

  const handleSaveAsDraft = async () => {
    await saveCourseData(false);
  };

  const backTarget = isEdit ? `/courses/${courseId}` : "/courses";

  return (
    <div className="max-w-5xl mx-auto space-y-6 pb-12">
      {/* 1. Universal Breadcrumbs & Back Header */}
      <CoursePageHeader
        breadcrumbs={[
          { label: "Courses", href: "/courses" },
          ...(isEdit && course
            ? [
                { label: course.title, href: `/courses/${courseId}` },
                { label: "Edit course", current: true },
              ]
            : [{ label: "Create course", current: true }]),
        ]}
        title={isEdit ? "Edit course" : "Create course"}
        description={
          isEdit
            ? "Update course metadata, level, duration and passing score."
            : "Step 1 of 5: Start with the basics. You add modules and chapters next."
        }
        backHref={backTarget}
        onBackClick={() => handleSafeNavigate(backTarget)}
      />

      {/* 2. 5-Step Stepper */}
      <CourseCreationStepper
        courseId={courseId}
        activeStepId={1}
        steps={stepperSteps}
        onStepClick={(step) => {
          if (step.path) handleSafeNavigate(step.path);
        }}
      />

      {/* 3. Main Form Card */}
      <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-2xs">
        <form onSubmit={handleSubmit} className="grid grid-cols-1 md:grid-cols-12 gap-8">
          {/* Left Column: Thumbnail Uploader */}
          <div className="md:col-span-4">
            <ThumbnailUploader
              value={thumbnailUrl}
              mediaId={thumbnailMediaId}
              onChange={(url, mediaId) => {
                setThumbnailUrl(url);
                setThumbnailMediaId(mediaId);
              }}
            />
          </div>

          {/* Right Column: Fields */}
          <div className="md:col-span-8 space-y-4">
            {errorMessage && (
              <div className="rounded-xl bg-rose-50 p-3.5 text-xs font-semibold text-rose-700 border border-rose-200">
                {errorMessage}
              </div>
            )}

            <div>
              <label className="block text-xs font-bold text-slate-800 mb-1.5">Course name *</label>
              <input
                type="text"
                required
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                placeholder="e.g. Complete Python Mastery"
                className="w-full rounded-xl border border-slate-300 px-3.5 py-2.5 text-sm text-slate-900 focus:border-[#00663C] focus:outline-none focus:ring-1 focus:ring-[#00663C]"
              />
            </div>

            <div>
              <label className="block text-xs font-bold text-slate-800 mb-1.5">Description</label>
              <textarea
                rows={3}
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder="Comprehensive course covering core programming, modules, and hands-on practices."
                className="w-full rounded-xl border border-slate-300 px-3.5 py-2.5 text-sm text-slate-900 focus:border-[#00663C] focus:outline-none focus:ring-1 focus:ring-[#00663C] resize-none"
              />
            </div>

            {/* Level Segments */}
            <div>
              <label className="block text-xs font-bold text-slate-800 mb-1.5">Level</label>
              <div className="flex rounded-xl border border-slate-300 overflow-hidden bg-slate-50 p-0.5">
                {(["Beginner", "Intermediate", "Advanced"] as const).map((lvl) => (
                  <button
                    key={lvl}
                    type="button"
                    onClick={() => setLevel(lvl)}
                    className={cn(
                      "flex-1 py-2 text-xs font-semibold rounded-lg transition-colors cursor-pointer",
                      level === lvl
                        ? "bg-emerald-50 text-[#00663C] border border-[#00663C]/30 font-bold"
                        : "text-slate-600 hover:text-slate-900"
                    )}
                  >
                    {lvl}
                  </button>
                ))}
              </div>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <label className="block text-xs font-bold text-slate-800 mb-1.5">Duration</label>
                <input
                  type="text"
                  value={duration}
                  onChange={(e) => setDuration(e.target.value)}
                  placeholder="12 hours"
                  className="w-full rounded-xl border border-slate-300 px-3.5 py-2.5 text-sm text-slate-900 focus:border-[#00663C] focus:outline-none focus:ring-1 focus:ring-[#00663C]"
                />
              </div>

              <div>
                <label className="block text-xs font-bold text-slate-800 mb-1.5">Passing percentage</label>
                <input
                  type="text"
                  value={passingPercentage}
                  onChange={(e) => setPassingPercentage(e.target.value)}
                  placeholder="70%"
                  className="w-full rounded-xl border border-slate-300 px-3.5 py-2.5 text-sm text-slate-900 focus:border-[#00663C] focus:outline-none focus:ring-1 focus:ring-[#00663C]"
                />
                <span className="text-[11px] text-slate-400 mt-1 block">
                  Students need this score in every test.
                </span>
              </div>
            </div>

            {/* Actions matching Step 1 requirements */}
            <div className="flex flex-wrap items-center justify-between gap-3 pt-4 border-t border-slate-100">
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={() => handleSafeNavigate(backTarget)}
                  disabled={isSubmitting}
                  className="px-4 py-2 rounded-xl border border-slate-300 bg-white text-xs font-semibold text-slate-700 hover:bg-slate-50 cursor-pointer"
                >
                  Cancel
                </button>
                <button
                  type="button"
                  onClick={handleSaveAsDraft}
                  disabled={isSubmitting || !title.trim()}
                  className="px-4 py-2 rounded-xl border border-slate-300 bg-white text-xs font-semibold text-slate-700 hover:bg-slate-50 cursor-pointer disabled:opacity-50"
                >
                  Save as draft
                </button>
              </div>

              <button
                type="submit"
                disabled={isSubmitting}
                className="px-5 py-2 rounded-xl bg-[#00663C] text-xs font-bold text-white hover:bg-[#00522F] disabled:opacity-50 cursor-pointer shadow-xs inline-flex items-center gap-1.5"
              >
                <span>{isSubmitting ? "Saving..." : "Save and continue"}</span>
                <Icon name="arrow-right" size={14} />
              </button>
            </div>
          </div>
        </form>
      </div>

      {/* Discard changes Confirmation Modal */}
      <ConfirmModal
        isOpen={isDiscardModalOpen}
        title="Discard changes?"
        description="You have unsaved changes in this form. If you leave now, your changes will be discarded."
        confirmLabel="Discard"
        tone="danger"
        onConfirm={handleConfirmDiscard}
        onClose={() => setIsDiscardModalOpen(false)}
      />
    </div>
  );
}
