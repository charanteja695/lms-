import { useState, useEffect, useMemo } from "react";
import { useNavigate, useParams } from "react-router-dom";
import {
  useGetCourseQuery,
  useGetVersionQuery,
  useCreateCourseMutation,
  useUpdateCourseMutation,
  usePublishCourseMutation,
  useUpdateRulesMutation,
} from "@/modules/catalog/courses/api/coursesApi";
import {
  useGetAdminCoursePricingQuery,
  useUpdateAdminCoursePricingMutation,
} from "@/modules/billing/institutional/api/institutionalApi";
import {
  useCreateModuleMutation,
  useUpdateModuleMutation,
  useDeleteModuleMutation,
  useCreateTopicMutation,
  useCreateItemMutation,
} from "@/modules/catalog/courses/api/curriculumApi";
import {
  useCreateTestMutation,
  useUpdateTestMutation,
  useSubmitTestMutation,
  useApproveTestMutation,
  useGetTestQuery,
} from "@/modules/assessments/tests/api/testsApi";
import { ThumbnailUploader } from "@/modules/catalog/courses/components/common/ThumbnailUploader";
import { AddModuleModal } from "@/modules/catalog/courses/components/modals/AddModuleModal";
import { AddChapterModal, type ChapterMaterial } from "@/modules/catalog/courses/components/modals/AddChapterModal";
import { ModuleTestSetupModal } from "@/modules/catalog/courses/components/modals/ModuleTestSetupModal";
import { ChapterTestSetupModal } from "@/modules/catalog/courses/components/modals/ChapterTestSetupModal";
import { ConfirmModal } from "@/modules/catalog/courses/components/common/ConfirmModal";
import { Icon, PageLoader, Button } from "@/shared/ui";
import { usePermissions } from "@/modules/user-management/common/permissions/usePermissions";
import { useNotify } from "@/core/hooks/useNotify";
import { parseCourseSummary } from "@/modules/catalog/courses/utils/courseMetrics";
import { cn } from "@/core/lib/cn";
import type { ModuleDetail } from "@/modules/catalog/courses/curriculumTypes";
import {
  Plus,
  Trash2,
  Edit,
  Layers,
  HelpCircle,
  ClipboardCheck,
  ShieldAlert,
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  Video,
  FileText,
  Camera,
  Mic,
  Maximize2,
  Check,
} from "lucide-react";

export function CourseFormPage() {
  const { permissions } = usePermissions();
  const { courseId } = useParams<{ courseId: string }>();
  const isEdit = Boolean(courseId);
  const navigate = useNavigate();
  const notify = useNotify();

  const isAuthorized = permissions.role === "super_admin" || permissions.role === "admin";

  // Step state: 1 = Basic Info, 2 = Pricing, 3 = Modules & Chapters, 4 = Assessments, 5 = Review & Publish
  const [currentStep, setCurrentStep] = useState<1 | 2 | 3 | 4 | 5>(1);

  // Active Course ID (persists newly created course when moving to Step 3)
  const [persistedCourseId, setPersistedCourseId] = useState<string | null>(courseId ?? null);
  const activeCourseId = courseId || persistedCourseId;

  // STEP 1: Basic Information Fields
  const [title, setTitle] = useState("");
  const [courseCode, setCourseCode] = useState("");
  const [shortDesc, setShortDesc] = useState("");
  const [fullDesc, setFullDesc] = useState("");
  const [thumbnailUrl, setThumbnailUrl] = useState<string | null>(null);
  const [thumbnailMediaId, setThumbnailMediaId] = useState<string | null>(null);
  const [category, setCategory] = useState("Programming");
  const [subcategory, setSubcategory] = useState("Python");
  const [instructor, setInstructor] = useState("Dr. Sneha Reddy");
  const [difficulty, setDifficulty] = useState<"Beginner" | "Intermediate" | "Advanced">("Beginner");
  const [language, setLanguage] = useState("English");
  const [duration, setDuration] = useState("42 Hours");

  // STEP 2: Course Pricing Fields
  const [individualPrice, setIndividualPrice] = useState("1999");
  const [discountType, setDiscountType] = useState<"none" | "percentage" | "fixed">("percentage");
  const [discountValue, setDiscountValue] = useState("15");
  const [accessValidity] = useState("Lifetime");
  const [pricingMethod] = useState<"fixed" | "monthly" | "hourly">("fixed");
  const [institutionalSeatPrice, setInstitutionalSeatPrice] = useState("499");
  const [bulkDiscountPercent, setBulkDiscountPercent] = useState("10");
  const [numberOfStudents, setNumberOfStudents] = useState("50");

  const [isSubmitting, setIsSubmitting] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // STEP 4: Final Exam Parameters
  const [examTitle, setExamTitle] = useState("");
  const [examDurationMinutes, setExamDurationMinutes] = useState(60);
  const [examPassMark, setExamPassMark] = useState(70);
  const [examAttempts, setExamAttempts] = useState(3);
  const [examCooldownDays, setExamCooldownDays] = useState(1);
  const [examCameraRequired, setExamCameraRequired] = useState(true);
  const [examMicRequired, setExamMicRequired] = useState(true);
  const [examFullscreenRequired, setExamFullscreenRequired] = useState(true);
  const [isSavingFinalExam, setIsSavingFinalExam] = useState(false);

  // Queries for existing/active course
  const { data: course, isLoading: isLoadingCourse } = useGetCourseQuery(
    activeCourseId ?? "",
    { skip: !activeCourseId }
  );

  const { data: adminPricingData = [] } = useGetAdminCoursePricingQuery(undefined, {
    skip: !activeCourseId,
  });

  const existingPricing = useMemo(() => {
    if (!activeCourseId) return null;
    return adminPricingData.find((p) => String(p.course_id) === String(activeCourseId)) || null;
  }, [adminPricingData, activeCourseId]);

  const latestVersion = course?.versions?.[course.versions.length - 1];
  const versionId = latestVersion?.version_id;

  const {
    data: versionDetail,
    refetch: refetchVersion,
  } = useGetVersionQuery(
    { courseId: activeCourseId ?? "", versionId: versionId ?? "" },
    { skip: !activeCourseId || !versionId }
  );

  // Mutations
  const [createCourse] = useCreateCourseMutation();
  const [updateCourse] = useUpdateCourseMutation();
  const [updateCoursePricing] = useUpdateAdminCoursePricingMutation();
  const [publishCourse] = usePublishCourseMutation();
  const [updateRules] = useUpdateRulesMutation();
  const [createModule] = useCreateModuleMutation();
  const [updateModule] = useUpdateModuleMutation();
  const [deleteModule] = useDeleteModuleMutation();
  const [createTopic] = useCreateTopicMutation();
  const [createItem] = useCreateItemMutation();
  const [createTest] = useCreateTestMutation();
  const [updateTest] = useUpdateTestMutation();
  const [submitTest] = useSubmitTestMutation();
  const [approveTest] = useApproveTestMutation();

  // Final Test query
  const finalTestId = versionDetail?.rule?.final_test_id;
  const { data: finalTestDetail, refetch: refetchFinalTest } = useGetTestQuery(
    finalTestId ?? "",
    { skip: !finalTestId }
  );

  // Modal States
  const [isAddModuleOpen, setIsAddModuleOpen] = useState(false);
  const [editingModule, setEditingModule] = useState<ModuleDetail | null>(null);
  const [deletingModule, setDeletingModule] = useState<ModuleDetail | null>(null);
  const [addingChapterToModule, setAddingChapterToModule] = useState<ModuleDetail | null>(null);
  const [managingModuleTest, setManagingModuleTest] = useState<ModuleDetail | null>(null);
  const [managingChapterTest, setManagingChapterTest] = useState<{
    chapter: any;
    moduleTitle?: string;
    moduleId: string;
  } | null>(null);
  const [collapsedModules, setCollapsedModules] = useState<Record<string, boolean>>({});

  // Populate fields if editing
  useEffect(() => {
    if (course && (isEdit || persistedCourseId)) {
      setTitle(course.title || "");
      const parsed = parseCourseSummary(course.summary);
      setShortDesc(parsed.cleanDescription || "");
      setFullDesc(course.summary || "");
      setCourseCode(course.course_id.slice(0, 8).toUpperCase());
      setDifficulty(parsed.level);
      setDuration(parsed.duration === "0h" ? "42 Hours" : parsed.duration);

      if (course.thumbnail_media_id) {
        setThumbnailMediaId(String(course.thumbnail_media_id));
        setThumbnailUrl(`/api/v1/media/stream/${course.thumbnail_media_id}`);
      }

      if (existingPricing) {
        setIndividualPrice(String(Math.round((existingPricing.individual_price_paise || 199900) / 100)));
        setInstitutionalSeatPrice(String(Math.round((existingPricing.fixed_price_paise || 49900) / 100)));
        if (existingPricing.min_students) {
          setNumberOfStudents(String(existingPricing.min_students));
        }
        if (existingPricing.discount_percent) {
          setDiscountType("percentage");
          setDiscountValue(String(existingPricing.discount_percent));
        }
      }
    }
  }, [course, isEdit, persistedCourseId, existingPricing]);

  // Sync Final Exam title & settings
  useEffect(() => {
    if (finalTestDetail) {
      setExamTitle(finalTestDetail.title || "");
      setExamDurationMinutes(finalTestDetail.duration_minutes || 60);
      setExamPassMark(finalTestDetail.pass_mark_percent || versionDetail?.rule?.final_pass_mark || 70);
      setExamAttempts(finalTestDetail.max_attempts || versionDetail?.rule?.final_test_attempts || 3);
      setExamCooldownDays(versionDetail?.rule?.final_test_cooldown_days || 1);
      setExamCameraRequired(finalTestDetail.proctoring_level === "strict" || finalTestDetail.proctoring_level === "basic");
    } else if (title) {
      setExamTitle(`${title} - Final Certification Exam`);
    }
  }, [finalTestDetail, title, versionDetail?.rule]);

  // Calculations for Individual Pricing
  const individualCalc = useMemo(() => {
    const base = parseFloat(individualPrice) || 0;
    let discount = 0;
    if (discountType === "percentage") {
      discount = (base * (parseFloat(discountValue) || 0)) / 100;
    } else if (discountType === "fixed") {
      discount = parseFloat(discountValue) || 0;
    }
    const afterDiscount = Math.max(0, base - discount);
    const gst = afterDiscount * 0.18;
    const finalPayable = afterDiscount + gst;

    return {
      base: Math.round(base),
      discount: Math.round(discount),
      afterDiscount: Math.round(afterDiscount),
      gst: Math.round(gst),
      finalPayable: Math.round(finalPayable),
    };
  }, [individualPrice, discountType, discountValue]);

  // Calculations for Institutional Bulk Pricing
  const institutionalCalc = useMemo(() => {
    const seatPrice = parseFloat(institutionalSeatPrice) || 0;
    const students = Math.max(0, parseInt(numberOfStudents, 10) || 0);
    const rawTotal = seatPrice * students;
    const discountPercent = Math.max(0, Math.min(100, parseFloat(bulkDiscountPercent) || 0));
    const bulkDiscount = (rawTotal * discountPercent) / 100;
    const afterDiscount = Math.max(0, rawTotal - bulkDiscount);
    const gst = afterDiscount * 0.18;
    const total = afterDiscount + gst;

    return {
      seatPrice,
      students,
      discountPercent,
      rawTotal: Math.round(rawTotal),
      bulkDiscount: Math.round(bulkDiscount),
      afterDiscount: Math.round(afterDiscount),
      gst: Math.round(gst),
      total: Math.round(total),
    };
  }, [institutionalSeatPrice, numberOfStudents, bulkDiscountPercent]);

  const modules = versionDetail?.modules ?? [];
  const totalChapters = useMemo(() => {
    return modules.reduce((acc, m) => acc + (m.topics?.length ?? 0), 0);
  }, [modules]);

  // Safe helper to build slug conforming to ^[a-z0-9]+(?:-[a-z0-9]+)*$ (3 to 220 chars)
  const buildCleanSlug = (rawTitle: string): string => {
    let clean = rawTitle
      .toLowerCase()
      .normalize("NFD")
      .replace(/[\u0300-\u036f]/g, "")
      .replace(/[^a-z0-9]+/g, "-")
      .replace(/^-+|-+$/g, "");

    if (!clean || clean.length < 3) {
      clean = "course-" + (clean || "catalog");
      clean = clean.replace(/^-+|-+$/g, "");
    }

    const suffix = Date.now().toString(36);
    const base = clean.slice(0, 180).replace(/-+$/g, "");
    return `${base || "course"}-${suffix}`;
  };

  // Safe helper to construct summary (10 to 495 chars, max 500)
  const buildCleanSummary = (params: {
    difficulty: string;
    duration: string;
    instructor: string;
    category: string;
    shortDesc: string;
    fullDesc: string;
    title: string;
  }): string => {
    const prefix = `[${params.difficulty}] [${params.duration}] [Pass: 70%] [Instructor: ${params.instructor.trim() || "Instructor"}] [Category: ${params.category}] `;
    const maxDescBudget = 490 - prefix.length;
    let desc = (params.shortDesc || params.fullDesc || params.title).trim();
    if (desc.length > maxDescBudget) {
      desc = desc.slice(0, maxDescBudget - 3) + "...";
    }
    if (desc.length < 5) {
      desc = `${desc} - Comprehensive course training.`;
    }
    const summary = `${prefix}${desc}`.trim();
    return summary.slice(0, 495);
  };

  // Save basic course & pricing to initialize activeCourseId before moving to Step 3
  const handleSaveBasicAndPricing = async (nextStep: 1 | 2 | 3 | 4 | 5) => {
    const cleanTitle = title.trim();
    if (!cleanTitle || cleanTitle.length < 3) {
      setErrorMessage("Course title must be at least 3 characters. Please enter a valid title.");
      setCurrentStep(1);
      return;
    }

    try {
      setIsSubmitting(true);
      setErrorMessage(null);

      const summaryPayload = buildCleanSummary({
        difficulty,
        duration,
        instructor,
        category,
        shortDesc,
        fullDesc,
        title: cleanTitle,
      });

      const cleanThumbnailId =
        thumbnailMediaId && /^\d+$/.test(thumbnailMediaId) ? thumbnailMediaId : undefined;

      let targetId = activeCourseId;

      if (targetId) {
        await updateCourse({
          courseId: targetId,
          body: {
            title: cleanTitle,
            summary: summaryPayload,
            thumbnail_media_id: cleanThumbnailId,
          },
        }).unwrap();
      } else {
        const slug = buildCleanSlug(cleanTitle);
        const res = await createCourse({
          title: cleanTitle,
          slug,
          summary: summaryPayload,
          thumbnail_media_id: cleanThumbnailId,
        }).unwrap();
        targetId = res.course_id;
        setPersistedCourseId(targetId);
      }

      if (targetId) {
        const individualPaise = Math.max(0, Math.round((parseFloat(individualPrice) || 0) * 100));
        const institutionalPaise = Math.max(0, Math.round((parseFloat(institutionalSeatPrice) || 0) * 100));
        const cleanStudents = Math.max(1, parseInt(numberOfStudents, 10) || 50);
        const cleanDiscountPercent =
          discountType === "percentage"
            ? Math.min(100, Math.max(0, Math.round(parseFloat(discountValue) || 0)))
            : 0;
        const cleanDiscountPaise =
          discountType === "fixed"
            ? Math.max(0, Math.round((parseFloat(discountValue) || 0) * 100))
            : 0;

        try {
          await updateCoursePricing({
            course_id: targetId,
            course_title: cleanTitle,
            category,
            individual_price_paise: individualPaise,
            pricing_method: pricingMethod,
            fixed_price_paise: institutionalPaise,
            monthly_price_paise: institutionalPaise,
            hourly_price_paise: 0,
            discount_type: discountType,
            discount_percent: cleanDiscountPercent,
            discount_paise: cleanDiscountPaise,
            gst_percent: 18,
            min_students: cleanStudents,
            max_students: cleanStudents,
            reason: isEdit ? "Updated via Course Wizard" : "Initial Course Creation",
          }).unwrap();
        } catch (priceErr: any) {
          console.warn("Pricing update warning:", priceErr);
          let priceMsg = priceErr?.data?.message || "Course created, but pricing configuration could not be set.";
          if (priceErr?.data?.details && Array.isArray(priceErr.data.details) && priceErr.data.details.length > 0) {
            priceMsg = priceErr.data.details
              .map((d: any) => `${d.field ? `${d.field.replace(/^body\./, "")}: ` : ""}${d.message || d.code}`)
              .join(", ");
          }
          notify.info(priceMsg);
        }
      }

      notify.success("Course details & pricing saved!");
      setCurrentStep(nextStep);
    } catch (err: any) {
      console.error("Course create/update error:", err);
      let errMsg = "Failed to save course details.";
      if (err?.data?.details && Array.isArray(err.data.details) && err.data.details.length > 0) {
        errMsg = err.data.details
          .map((d: any) => `${d.field ? `${d.field.replace(/^body\./, "")}: ` : ""}${d.message || d.code}`)
          .join(" | ");
      } else if (err?.data?.message) {
        errMsg = err.data.message;
      } else if (err?.message) {
        errMsg = err.message;
      }
      setErrorMessage(errMsg);
      notify.error(errMsg);
    } finally {
      setIsSubmitting(false);
    }
  };

  // Step 3: Handle Save Module
  const handleSaveModule = async (data: { title: string; description: string; position: number }) => {
    if (!activeCourseId || !versionId) return;
    try {
      if (editingModule) {
        await updateModule({
          courseId: activeCourseId,
          versionId,
          moduleId: editingModule.module_id,
          body: { title: data.title },
        }).unwrap();
        notify.success("Module updated");
      } else {
        await createModule({
          courseId: activeCourseId,
          versionId,
          body: { title: data.title, pass_mark: 70 },
        }).unwrap();
        notify.success("Module created");
      }
      setEditingModule(null);
      setIsAddModuleOpen(false);
      refetchVersion();
    } catch (err: any) {
      notify.apiError(err);
    }
  };

  // Step 3: Handle Delete Module
  const handleDeleteModule = async () => {
    if (!activeCourseId || !versionId || !deletingModule) return;
    try {
      await deleteModule({
        courseId: activeCourseId,
        versionId,
        moduleId: deletingModule.module_id,
      }).unwrap();
      notify.success("Module deleted");
      setDeletingModule(null);
      refetchVersion();
    } catch (err: any) {
      notify.apiError(err);
    }
  };

  // Step 3: Handle Save Chapter
  const handleSaveChapter = async (data: {
    title: string;
    position: number;
    description: string;
    objectives: string[];
    materials: ChapterMaterial[];
  }) => {
    if (!activeCourseId || !versionId || !addingChapterToModule) return;
    try {
      const res = await createTopic({
        courseId: activeCourseId,
        versionId,
        moduleId: addingChapterToModule.module_id,
        body: { title: data.title, pass_mark: 70 },
      }).unwrap();

      if (data.materials && data.materials.length > 0 && res.topic?.topic_id) {
        for (const mat of data.materials) {
          await createItem({
            courseId: activeCourseId,
            versionId,
            moduleId: addingChapterToModule.module_id,
            topicId: res.topic.topic_id,
            body: {
              item_type: mat.type === "video" ? "video" : mat.type === "pdf" ? "pdf" : "notes",
              title: mat.name,
              media_id: (mat as any).media_id || undefined,
            },
          }).unwrap();
        }
      }
      notify.success(`Chapter added to "${addingChapterToModule.title}"`);
      setAddingChapterToModule(null);
      refetchVersion();
    } catch (err: any) {
      notify.apiError(err);
    }
  };

  // Step 4: Handle Save Final Exam
  const handleSaveFinalExam = async () => {
    if (!activeCourseId || !versionId) return;
    try {
      setIsSavingFinalExam(true);
      let testPublicId = finalTestId;

      if (testPublicId) {
        await updateTest({
          testId: testPublicId,
          body: {
            title: examTitle || `${title} - Final Certification Exam`,
            duration_minutes: Number(examDurationMinutes) || 60,
            pass_mark_percent: Number(examPassMark) || 70,
            max_attempts: Number(examAttempts) || 3,
            proctoring_level: examCameraRequired ? "strict" : "none",
          },
        }).unwrap();
      } else {
        const created = await createTest({
          title: examTitle || `${title} - Final Certification Exam`,
          kind: "final",
          target_id: activeCourseId,
          duration_minutes: Number(examDurationMinutes) || 60,
          pass_mark_percent: Number(examPassMark) || 70,
          max_attempts: Number(examAttempts) || 3,
          time_mode: "overall",
          proctoring_level: examCameraRequired ? "strict" : "none",
          sections: [
            {
              title: "Comprehensive Final Assessment",
              slots: [
                {
                  slot_type: "fixed",
                  marks: 2,
                },
              ],
            },
          ],
        }).unwrap();
        testPublicId = created.test_id;
        if (testPublicId) {
          try {
            await submitTest(testPublicId).unwrap();
            await approveTest({ testId: testPublicId }).unwrap();
          } catch {}
        }
      }

      await updateRules({
        courseId: activeCourseId,
        versionId,
        body: {
          final_pass_mark: Number(examPassMark) || 70,
          final_test_attempts: Number(examAttempts) || 3,
          final_test_cooldown_days: Number(examCooldownDays) || 1,
          final_test_id: testPublicId || undefined,
        },
      }).unwrap();

      notify.success("Final Exam & Proctoring settings saved!");
      refetchVersion();
      if (testPublicId) refetchFinalTest();
    } catch (err: any) {
      notify.apiError(err);
    } finally {
      setIsSavingFinalExam(false);
    }
  };

  // Step 5: Publish Course
  const handlePublishCourse = async () => {
    if (!activeCourseId) return;
    try {
      setIsSubmitting(true);
      await publishCourse(activeCourseId).unwrap();
      notify.success("Course published successfully!");
      navigate(`/courses/${activeCourseId}`);
    } catch (err: any) {
      notify.apiError(err);
    } finally {
      setIsSubmitting(false);
    }
  };

  if (!isAuthorized) {
    return <PageLoader label="Checking authorization..." />;
  }

  if (isEdit && isLoadingCourse) {
    return <PageLoader label="Loading course..." />;
  }

  return (
    <div className="max-w-5xl mx-auto space-y-6 pb-16 font-sans text-navy-950">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-[#E4EAF5] pb-4">
        <div>
          <button
            type="button"
            onClick={() => navigate(activeCourseId ? `/courses/${activeCourseId}` : "/courses")}
            className="flex items-center gap-1.5 text-xs font-semibold text-slate-500 hover:text-navy-950 transition-colors mb-1 cursor-pointer"
          >
            <Icon name="arrowLeft" size={14} /> Back to {activeCourseId ? "Course Workspace" : "Course Management"}
          </button>
          <h1 className="text-[28px] font-bold text-[#111827] tracking-tight">
            {isEdit ? "Edit Course & Curriculum" : "Create New Course"}
          </h1>
        </div>
      </div>

      {/* 5-Step Wizard Navigation Bar */}
      <div className="flex items-center justify-between bg-white rounded-2xl border border-[#E5E7EB] p-2 sm:p-3 shadow-card overflow-x-auto no-scrollbar gap-1 sm:gap-2">
        {[
          { step: 1, label: "1. Basic Info" },
          { step: 2, label: "2. Pricing" },
          { step: 3, label: `3. Modules & Chapters (${modules.length})` },
          { step: 4, label: "4. Tests & Assessments" },
          { step: 5, label: "5. Review & Publish" },
        ].map((item) => (
          <button
            key={item.step}
            type="button"
            onClick={() => {
              setErrorMessage(null);
              setCurrentStep(item.step as any);
            }}
            className={cn(
              "flex-1 py-2 px-3 text-xs font-bold rounded-xl transition-all text-center cursor-pointer whitespace-nowrap",
              currentStep === item.step
                ? "bg-[#635BFF] text-white shadow-xs"
                : "text-slate-600 hover:text-navy-950 hover:bg-slate-100/70"
            )}
          >
            {item.label}
          </button>
        ))}
      </div>

      {errorMessage && (
        <div className="rounded-xl bg-rose-50 p-4 text-xs font-semibold text-rose-800 border border-rose-200 flex flex-wrap items-center justify-between gap-3 shadow-xs">
          <div className="flex items-center gap-2">
            <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-rose-200 text-rose-800 font-bold text-[11px]">!</span>
            <span>{errorMessage}</span>
          </div>
          {currentStep !== 1 && (
            <button
              type="button"
              onClick={() => setCurrentStep(1)}
              className="text-xs font-bold text-brand-600 hover:text-brand-800 underline cursor-pointer"
            >
              Back to Step 1: Basic Info
            </button>
          )}
        </div>
      )}

      {/* =========================================================================
          STEP 1: BASIC COURSE INFORMATION
          ========================================================================= */}
      {currentStep === 1 && (
        <div className="rounded-2xl border border-[#E4EAF5] bg-white p-6 shadow-card space-y-6">
          <div className="grid grid-cols-1 md:grid-cols-12 gap-8">
            {/* Left: Thumbnail */}
            <div className="md:col-span-4">
              <label className="block text-xs font-bold text-slate-700 mb-2">Course Thumbnail</label>
              <ThumbnailUploader
                value={thumbnailUrl}
                mediaId={thumbnailMediaId}
                onChange={(url, mediaId) => {
                  setThumbnailUrl(url);
                  setThumbnailMediaId(mediaId);
                }}
              />
            </div>

            {/* Right: Fields */}
            <div className="md:col-span-8 space-y-4">
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                <div className="sm:col-span-2">
                  <div className="flex items-center justify-between mb-1">
                    <label className="block text-xs font-bold text-slate-700">Course Title *</label>
                    <span className="text-[11px] text-slate-400">
                      {title.length}/200 {title.trim().length > 0 && title.trim().length < 3 ? "(min 3 chars required)" : ""}
                    </span>
                  </div>
                  <input
                    type="text"
                    required
                    maxLength={200}
                    value={title}
                    onChange={(e) => {
                      setTitle(e.target.value);
                      if (errorMessage && e.target.value.trim().length >= 3) {
                        setErrorMessage(null);
                      }
                    }}
                    placeholder="e.g. Master Python Programming & Clean Architecture"
                    className={cn(
                      "w-full rounded-xl border px-3.5 py-2 text-sm text-navy-950 focus:outline-none",
                      title.trim().length > 0 && title.trim().length < 3
                        ? "border-amber-400 bg-amber-50/20 focus:border-amber-500"
                        : "border-slate-200 focus:border-brand-500 focus:ring-1 focus:ring-brand-500"
                    )}
                  />
                  {title.trim().length > 0 && title.trim().length < 3 && (
                    <p className="text-[11px] text-amber-600 mt-1 font-medium">
                      Title must be at least 3 characters ({title.trim().length}/3).
                    </p>
                  )}
                </div>
                <div>
                  <label className="block text-xs font-bold text-slate-700 mb-1">Course Code</label>
                  <input
                    type="text"
                    value={courseCode}
                    onChange={(e) => setCourseCode(e.target.value)}
                    placeholder="CS-101"
                    className="w-full rounded-xl border border-slate-200 px-3.5 py-2 text-sm text-navy-950 font-mono focus:border-brand-500 focus:outline-none"
                  />
                </div>
              </div>

              <div>
                <div className="flex items-center justify-between mb-1">
                  <label className="block text-xs font-bold text-slate-700">Short Description</label>
                  <span className="text-[11px] text-slate-400">{shortDesc.length}/350</span>
                </div>
                <input
                  type="text"
                  maxLength={350}
                  value={shortDesc}
                  onChange={(e) => setShortDesc(e.target.value)}
                  placeholder="A concise 1-sentence overview for course marketplace cards."
                  className="w-full rounded-xl border border-slate-200 px-3.5 py-2 text-sm text-navy-950 focus:border-brand-500 focus:outline-none"
                />
              </div>

              <div>
                <div className="flex items-center justify-between mb-1">
                  <label className="block text-xs font-bold text-slate-700">Full Description</label>
                  <span className="text-[11px] text-slate-400">{fullDesc.length}/2000</span>
                </div>
                <textarea
                  rows={3}
                  value={fullDesc}
                  onChange={(e) => setFullDesc(e.target.value)}
                  placeholder="Detailed course objectives, syllabus scope, and student takeaways."
                  className="w-full rounded-xl border border-slate-200 px-3.5 py-2 text-sm text-navy-950 focus:border-brand-500 focus:outline-none resize-none"
                />
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                <div>
                  <label className="block text-xs font-bold text-slate-700 mb-1">Category</label>
                  <select
                    value={category}
                    onChange={(e) => setCategory(e.target.value)}
                    className="w-full rounded-xl border border-slate-200 px-3 py-2 text-xs text-navy-950 bg-white focus:outline-none"
                  >
                    <option value="Programming">Programming</option>
                    <option value="Data Science">Data Science</option>
                    <option value="Artificial Intelligence">Artificial Intelligence</option>
                    <option value="Cloud & DevOps">Cloud & DevOps</option>
                    <option value="Cybersecurity">Cybersecurity</option>
                    <option value="Business & Management">Business & Management</option>
                  </select>
                </div>
                <div>
                  <label className="block text-xs font-bold text-slate-700 mb-1">Subcategory</label>
                  <input
                    type="text"
                    value={subcategory}
                    onChange={(e) => setSubcategory(e.target.value)}
                    placeholder="e.g. Python, Fullstack"
                    className="w-full rounded-xl border border-slate-200 px-3.5 py-2 text-xs text-navy-950 focus:outline-none"
                  />
                </div>
                <div>
                  <label className="block text-xs font-bold text-slate-700 mb-1">Instructor</label>
                  <input
                    type="text"
                    value={instructor}
                    onChange={(e) => setInstructor(e.target.value)}
                    placeholder="Dr. Sneha Reddy"
                    className="w-full rounded-xl border border-slate-200 px-3.5 py-2 text-xs text-navy-950 focus:outline-none"
                  />
                </div>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                <div>
                  <label className="block text-xs font-bold text-slate-700 mb-1">Difficulty Level</label>
                  <div className="flex rounded-xl bg-slate-100 p-1">
                    {(["Beginner", "Intermediate", "Advanced"] as const).map((lvl) => (
                      <button
                        key={lvl}
                        type="button"
                        onClick={() => setDifficulty(lvl)}
                        className={cn(
                          "flex-1 py-1.5 text-xs font-bold rounded-lg transition-all cursor-pointer",
                          difficulty === lvl
                            ? "bg-brand-600 text-white shadow-2xs"
                            : "text-slate-600 hover:text-navy-950"
                        )}
                      >
                        {lvl}
                      </button>
                    ))}
                  </div>
                </div>

                <div>
                  <label className="block text-xs font-bold text-slate-700 mb-1">Language</label>
                  <input
                    type="text"
                    value={language}
                    onChange={(e) => setLanguage(e.target.value)}
                    placeholder="English"
                    className="w-full rounded-xl border border-slate-200 px-3.5 py-2 text-xs text-navy-950 focus:outline-none"
                  />
                </div>

                <div>
                  <label className="block text-xs font-bold text-slate-700 mb-1">Duration</label>
                  <input
                    type="text"
                    value={duration}
                    onChange={(e) => setDuration(e.target.value)}
                    placeholder="42 Hours"
                    className="w-full rounded-xl border border-slate-200 px-3.5 py-2 text-xs text-navy-950 focus:outline-none"
                  />
                </div>
              </div>
            </div>
          </div>

          <div className="flex items-center justify-end pt-4 border-t border-[#E4EAF5]">
            <button
              type="button"
              onClick={() => {
                setErrorMessage(null);
                setCurrentStep(2);
              }}
              className="inline-flex items-center gap-2 rounded-xl bg-[#6366F1] px-5 py-2.5 text-xs font-bold text-white shadow-xs hover:bg-[#4F46E5] transition-all cursor-pointer"
            >
              <span>Continue to Course Pricing</span>
              <Icon name="arrowRight" size={14} />
            </button>
          </div>
        </div>
      )}

      {/* =========================================================================
          STEP 2: COURSE PRICING
          ========================================================================= */}
      {currentStep === 2 && (
        <div className="rounded-2xl border border-[#E4EAF5] bg-white p-6 shadow-card space-y-6">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
            {/* Left: Individual Student Pricing */}
            <div className="space-y-4 rounded-xl border border-slate-200 p-5 bg-slate-50/40">
              <h3 className="text-sm font-bold text-navy-950 border-b border-slate-200 pb-2 flex items-center gap-2">
                <span className="w-2 h-2 rounded-full bg-brand-600" />
                Individual Student Pricing
              </h3>

              <div>
                <label className="block text-xs font-bold text-slate-700 mb-1">Base Price (₹) *</label>
                <input
                  type="number"
                  min="0"
                  value={individualPrice}
                  onChange={(e) => setIndividualPrice(e.target.value)}
                  className="w-full rounded-xl border border-slate-200 px-3 py-2 text-sm text-navy-950 font-bold bg-white focus:outline-none"
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-bold text-slate-700 mb-1">Discount Type</label>
                  <select
                    value={discountType}
                    onChange={(e) => setDiscountType(e.target.value as any)}
                    className="w-full rounded-xl border border-slate-200 px-3 py-2 text-xs text-navy-950 bg-white focus:outline-none"
                  >
                    <option value="none">No Discount</option>
                    <option value="percentage">Percentage (%)</option>
                    <option value="fixed">Fixed Off (₹)</option>
                  </select>
                </div>
                <div>
                  <label className="block text-xs font-bold text-slate-700 mb-1">Discount Value</label>
                  <input
                    type="number"
                    disabled={discountType === "none"}
                    value={discountValue}
                    onChange={(e) => setDiscountValue(e.target.value)}
                    className="w-full rounded-xl border border-slate-200 px-3 py-2 text-xs text-navy-950 bg-white disabled:opacity-50 focus:outline-none"
                  />
                </div>
              </div>

              {/* Price Calculation Box */}
              <div className="rounded-xl border border-blue-200 bg-blue-50/60 p-4 space-y-2 text-xs">
                <div className="flex justify-between text-slate-600">
                  <span>Base Price</span>
                  <span>₹{individualCalc.base.toLocaleString()}</span>
                </div>
                {individualCalc.discount > 0 && (
                  <div className="flex justify-between text-emerald-700 font-semibold">
                    <span>Discount</span>
                    <span>-₹{individualCalc.discount.toLocaleString()}</span>
                  </div>
                )}
                <div className="flex justify-between text-slate-600">
                  <span>GST (18%)</span>
                  <span>₹{individualCalc.gst.toLocaleString()}</span>
                </div>
                <div className="flex justify-between text-navy-950 font-extrabold text-sm pt-2 border-t border-blue-200">
                  <span>Final Student Payable Amount</span>
                  <span>₹{individualCalc.finalPayable.toLocaleString()}</span>
                </div>
              </div>
            </div>

            {/* Right: Institutional Bulk Pricing */}
            <div className="space-y-4 rounded-xl border border-slate-200 p-5 bg-slate-50/40">
              <h3 className="text-sm font-bold text-navy-950 border-b border-slate-200 pb-2 flex items-center gap-2">
                <span className="w-2 h-2 rounded-full bg-purple-600" />
                Institutional Bulk Pricing
              </h3>

              <div>
                <label className="block text-xs font-bold text-slate-700 mb-1">Price per Student (₹) *</label>
                <input
                  type="number"
                  min="0"
                  value={institutionalSeatPrice}
                  onChange={(e) => setInstitutionalSeatPrice(e.target.value)}
                  placeholder="499"
                  className="w-full rounded-xl border border-slate-200 px-3 py-2 text-sm text-navy-950 font-bold bg-white focus:outline-none focus:border-[#6366F1]"
                />
              </div>

              <div>
                <label className="block text-xs font-bold text-slate-700 mb-1">Number of Students *</label>
                <input
                  type="number"
                  min="1"
                  value={numberOfStudents}
                  onChange={(e) => setNumberOfStudents(e.target.value)}
                  placeholder="50"
                  className="w-full rounded-xl border border-slate-200 px-3 py-2 text-sm text-navy-950 font-bold bg-white focus:outline-none focus:border-[#6366F1]"
                />
                <p className="text-[11px] text-slate-500 mt-1">
                  Enter the number of students required for this institution. The quotation will be calculated automatically.
                </p>
              </div>

              <div>
                <label className="block text-xs font-bold text-slate-700 mb-1">Bulk Discount (%)</label>
                <input
                  type="number"
                  min="0"
                  max="50"
                  value={bulkDiscountPercent}
                  onChange={(e) => setBulkDiscountPercent(e.target.value)}
                  placeholder="10"
                  className="w-full rounded-xl border border-slate-200 px-3 py-2 text-xs text-navy-950 bg-white focus:outline-none focus:border-[#6366F1]"
                />
              </div>

              {/* Institutional Estimate Box */}
              <div className="rounded-xl border border-purple-200 bg-purple-50/60 p-4 space-y-2 text-xs">
                <div className="flex justify-between text-slate-600">
                  <span>Number of Students × Price per Student ({institutionalCalc.students} × ₹{institutionalCalc.seatPrice.toLocaleString()})</span>
                  <span>₹{institutionalCalc.rawTotal.toLocaleString()}</span>
                </div>
                <div className="flex justify-between text-slate-600 font-medium">
                  <span>Subtotal</span>
                  <span>₹{institutionalCalc.rawTotal.toLocaleString()}</span>
                </div>
                {institutionalCalc.bulkDiscount > 0 && (
                  <div className="flex justify-between text-emerald-700 font-semibold">
                    <span>Bulk Discount ({bulkDiscountPercent}%)</span>
                    <span>-₹{institutionalCalc.bulkDiscount.toLocaleString()}</span>
                  </div>
                )}
                <div className="flex justify-between text-slate-600">
                  <span>Amount after discount</span>
                  <span>₹{institutionalCalc.afterDiscount.toLocaleString()}</span>
                </div>
                <div className="flex justify-between text-slate-600">
                  <span>GST (18%)</span>
                  <span>₹{institutionalCalc.gst.toLocaleString()}</span>
                </div>
                <div className="flex justify-between text-purple-950 font-extrabold text-sm pt-2 border-t border-purple-200">
                  <span>Final Institutional Quotation</span>
                  <span>₹{institutionalCalc.total.toLocaleString()}</span>
                </div>
              </div>
            </div>
          </div>

          <div className="flex items-center justify-between pt-4 border-t border-[#E4EAF5]">
            <button
              type="button"
              onClick={() => setCurrentStep(1)}
              className="px-4 py-2 text-xs font-bold text-slate-600 hover:text-navy-950 cursor-pointer"
            >
              ← Back to Basic Information
            </button>

            <button
              type="button"
              onClick={() => handleSaveBasicAndPricing(3)}
              disabled={isSubmitting}
              className="inline-flex items-center gap-2 rounded-xl bg-brand-600 px-5 py-2.5 text-xs font-bold text-white shadow-xs hover:bg-brand-700 transition-all cursor-pointer disabled:opacity-50"
            >
              <span>{isSubmitting ? "Saving..." : "Save & Continue to Modules & Chapters"}</span>
              <Icon name="arrowRight" size={14} />
            </button>
          </div>
        </div>
      )}

      {/* =========================================================================
          STEP 3: INSERT MODULES & CHAPTERS
          ========================================================================= */}
      {currentStep === 3 && (
        <div className="rounded-2xl border border-[#E4EAF5] bg-white p-6 shadow-card space-y-6">
          <div className="flex flex-wrap items-center justify-between gap-3 pb-3 border-b border-slate-100">
            <div>
              <h2 className="text-base font-bold text-navy-950">Curriculum: Modules & Chapters</h2>
              <p className="text-xs text-slate-500 mt-0.5">
                Insert learning modules, chapters, video lectures, and study documents.
              </p>
            </div>

            <Button
              variant="primary"
              size="sm"
              onClick={() => {
                setEditingModule(null);
                setIsAddModuleOpen(true);
              }}
              className="gap-1.5 text-xs font-semibold bg-[#2563EB] hover:bg-blue-700 text-white"
            >
              <Plus size={14} />
              <span>Insert Module</span>
            </Button>
          </div>

          {modules.length === 0 ? (
            <div className="text-center py-12 border-2 border-dashed border-slate-200 rounded-2xl bg-slate-50/50">
              <Layers size={36} className="mx-auto text-slate-300 mb-2" />
              <h4 className="text-sm font-bold text-slate-800">No modules added yet</h4>
              <p className="text-xs text-slate-500 mt-1 mb-4 max-w-sm mx-auto">
                Get started by creating your first module to structure chapters and lesson content.
              </p>
              <Button
                variant="primary"
                size="sm"
                onClick={() => setIsAddModuleOpen(true)}
                className="gap-1 text-xs font-bold"
              >
                <Plus size={13} />
                <span>Insert First Module</span>
              </Button>
            </div>
          ) : (
            <div className="space-y-4">
              {modules.map((m, mIdx) => {
                const chapters = m.topics ?? [];
                const isCollapsed = collapsedModules[m.module_id] ?? false;

                return (
                  <div
                    key={m.module_id}
                    className="rounded-xl border border-slate-200 bg-white shadow-2xs overflow-hidden"
                  >
                    {/* Module Header Bar */}
                    <div className="flex items-center justify-between p-4 bg-slate-50/80 border-b border-slate-100 gap-3">
                      <div
                        className="flex items-center gap-3 min-w-0 flex-1 cursor-pointer select-none"
                        onClick={() =>
                          setCollapsedModules((prev) => ({ ...prev, [m.module_id]: !prev[m.module_id] }))
                        }
                      >
                        <button type="button" className="p-1 rounded text-slate-400 hover:text-slate-700">
                          {isCollapsed ? <ChevronRight size={16} /> : <ChevronDown size={16} />}
                        </button>
                        <span className="w-6 h-6 rounded-md bg-[#2563EB] text-white text-xs font-bold flex items-center justify-center shrink-0">
                          {mIdx + 1}
                        </span>
                        <div className="min-w-0">
                          <h4 className="text-sm font-bold text-slate-900 truncate">{m.title}</h4>
                          <p className="text-[11px] text-slate-500">
                            {chapters.length} {chapters.length === 1 ? "Chapter" : "Chapters"} · Pass Mark {m.pass_mark || 70}%
                          </p>
                        </div>
                      </div>

                      <div className="flex items-center gap-2 shrink-0">
                        <Button
                          variant="primary"
                          size="sm"
                          onClick={(e) => {
                            e.stopPropagation();
                            setAddingChapterToModule(m);
                          }}
                          className="text-xs font-semibold gap-1 bg-[#2563EB] hover:bg-blue-700 text-white"
                        >
                          <Plus size={13} />
                          <span>Insert Chapter</span>
                        </Button>

                        <button
                          type="button"
                          onClick={() => {
                            setEditingModule(m);
                            setIsAddModuleOpen(true);
                          }}
                          className="p-1.5 rounded-lg text-slate-400 hover:text-slate-700 hover:bg-slate-200/50 cursor-pointer"
                          title="Edit Module"
                        >
                          <Edit size={14} />
                        </button>

                        <button
                          type="button"
                          onClick={() => setDeletingModule(m)}
                          className="p-1.5 rounded-lg text-slate-400 hover:text-rose-600 hover:bg-rose-50 cursor-pointer"
                          title="Delete Module"
                        >
                          <Trash2 size={14} />
                        </button>
                      </div>
                    </div>

                    {/* Chapters Accordion Content */}
                    {!isCollapsed && (
                      <div className="divide-y divide-slate-100">
                        {chapters.length === 0 ? (
                          <div className="p-5 text-center text-xs text-slate-400 flex items-center justify-center gap-2">
                            <span>No chapters in this module yet.</span>
                            <button
                              type="button"
                              onClick={() => setAddingChapterToModule(m)}
                              className="text-[#2563EB] font-bold hover:underline cursor-pointer"
                            >
                              + Insert Chapter
                            </button>
                          </div>
                        ) : (
                          chapters.map((ch, chIdx) => {
                            const items = ch.items ?? [];
                            const videoItem = items.find((i: any) => i.item_type === "video");
                            const pdfItem = items.find((i: any) => i.item_type === "pdf" || i.item_type === "document");

                            return (
                              <div
                                key={ch.topic_id}
                                className="flex flex-wrap items-center justify-between p-3.5 pl-11 hover:bg-slate-50/60 transition-colors gap-3"
                              >
                                <div className="flex items-center gap-3 min-w-0">
                                  <span className="text-xs font-mono text-slate-400 font-semibold">
                                    {mIdx + 1}.{chIdx + 1}
                                  </span>
                                  <div className="min-w-0">
                                    <h5 className="text-xs font-bold text-slate-800 truncate">{ch.title}</h5>
                                    <div className="flex items-center gap-3 mt-0.5">
                                      {videoItem ? (
                                        <span className="inline-flex items-center gap-1 text-[11px] font-medium text-blue-700 bg-blue-50 px-2 py-0.5 rounded border border-blue-200">
                                          <Video size={11} /> Video Lecture
                                        </span>
                                      ) : (
                                        <span className="text-[11px] text-slate-400">No video attached</span>
                                      )}
                                      {pdfItem ? (
                                        <span className="inline-flex items-center gap-1 text-[11px] font-medium text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded border border-emerald-200">
                                          <FileText size={11} /> Lecture Notes
                                        </span>
                                      ) : (
                                        <span className="text-[11px] text-slate-400">No PDF notes</span>
                                      )}
                                    </div>
                                  </div>
                                </div>

                                <div className="flex items-center gap-2">
                                  {ch.topic_test_id ? (
                                    <span className="inline-flex items-center gap-1 text-[11px] font-semibold text-emerald-700 bg-emerald-50 px-2.5 py-1 rounded-full border border-emerald-200">
                                      <CheckCircle2 size={12} /> Quiz Ready
                                    </span>
                                  ) : (
                                    <span className="text-[11px] text-slate-400">Quiz pending</span>
                                  )}
                                  <Button
                                    variant="secondary"
                                    size="sm"
                                    onClick={() =>
                                      setManagingChapterTest({
                                        chapter: ch,
                                        moduleTitle: m.title,
                                        moduleId: m.module_id,
                                      })
                                    }
                                    className="text-[11px] px-2.5 py-1 gap-1 text-[#2563EB]"
                                  >
                                    <HelpCircle size={12} />
                                    <span>{ch.topic_test_id ? "Edit Quiz" : "Configure Quiz"}</span>
                                  </Button>
                                </div>
                              </div>
                            );
                          })
                        )}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}

          <div className="flex items-center justify-between pt-4 border-t border-[#E4EAF5]">
            <button
              type="button"
              onClick={() => setCurrentStep(2)}
              className="px-4 py-2 text-xs font-bold text-slate-600 hover:text-navy-950 cursor-pointer"
            >
              ← Back to Pricing
            </button>

            <button
              type="button"
              onClick={() => setCurrentStep(4)}
              className="inline-flex items-center gap-2 rounded-xl bg-brand-600 px-5 py-2.5 text-xs font-bold text-white shadow-xs hover:bg-brand-700 transition-all cursor-pointer"
            >
              <span>Continue to Tests & Assessments</span>
              <Icon name="arrowRight" size={14} />
            </button>
          </div>
        </div>
      )}

      {/* =========================================================================
          STEP 4: TESTS & ASSESSMENTS (Chapter Tests, Module Tests, Final Exam)
          ========================================================================= */}
      {currentStep === 4 && (
        <div className="rounded-2xl border border-[#E4EAF5] bg-white p-6 shadow-card space-y-8">
          <div className="pb-3 border-b border-slate-100">
            <h2 className="text-base font-bold text-navy-950">Tests & Assessments Suite</h2>
            <p className="text-xs text-slate-500 mt-0.5">
              Insert and configure checkpoint chapter quizzes, end-of-module mastery tests, and the comprehensive final certification exam.
            </p>
          </div>

          {/* 1. Chapter Quizzes */}
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-bold text-slate-900 flex items-center gap-2">
                <HelpCircle size={16} className="text-indigo-600" />
                <span>1. Chapter Tests ({modules.flatMap((m) => m.topics ?? []).length} Chapters)</span>
              </h3>
              <span className="text-xs text-slate-500">
                Reinforces concepts immediately after each chapter
              </span>
            </div>

            <div className="divide-y divide-slate-100 border border-slate-200 rounded-xl overflow-hidden">
              {modules.flatMap((m) => (m.topics ?? []).map((t) => ({ ...t, moduleTitle: m.title, moduleId: m.module_id }))).length === 0 ? (
                <div className="p-8 text-center text-xs text-slate-500">
                  No chapters created yet. Please insert modules and chapters in Step 3.
                </div>
              ) : (
                modules.flatMap((m) =>
                  (m.topics ?? []).map((ch, chIdx) => (
                    <div
                      key={ch.topic_id}
                      className="p-3.5 flex flex-wrap items-center justify-between gap-3 bg-white hover:bg-slate-50/50 transition-colors"
                    >
                      <div className="flex items-center gap-3">
                        <div className="w-7 h-7 rounded-lg bg-indigo-50 text-indigo-700 flex items-center justify-center font-bold text-xs shrink-0">
                          Q{chIdx + 1}
                        </div>
                        <div>
                          <span className="text-[10px] font-semibold text-slate-400 uppercase tracking-wider block">
                            {m.title}
                          </span>
                          <h4 className="text-xs font-bold text-slate-900">{ch.title} Test</h4>
                        </div>
                      </div>

                      <div className="flex items-center gap-2">
                        {ch.topic_test_id ? (
                          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[11px] font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200">
                            <CheckCircle2 size={12} /> Configured
                          </span>
                        ) : (
                          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[11px] font-semibold bg-amber-50 text-amber-700 border border-amber-200">
                            Pending
                          </span>
                        )}
                        <Button
                          variant="secondary"
                          size="sm"
                          onClick={() =>
                            setManagingChapterTest({
                              chapter: ch,
                              moduleTitle: m.title,
                              moduleId: m.module_id,
                            })
                          }
                          className="text-xs font-semibold"
                        >
                          Configure Chapter Test
                        </Button>
                      </div>
                    </div>
                  ))
                )
              )}
            </div>
          </div>

          {/* 2. Module Tests */}
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-bold text-slate-900 flex items-center gap-2">
                <ClipboardCheck size={16} className="text-purple-600" />
                <span>2. Module Tests ({modules.length} Modules)</span>
              </h3>
              <span className="text-xs text-slate-500">
                End-of-module assessment required to unlock next module
              </span>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              {modules.length === 0 ? (
                <div className="col-span-2 p-8 text-center text-xs text-slate-500 border border-slate-200 rounded-xl">
                  No modules created yet. Please insert modules in Step 3.
                </div>
              ) : (
                modules.map((m, mIdx) => (
                  <div
                    key={m.module_id}
                    className="p-4 rounded-xl border border-slate-200 bg-white shadow-2xs flex items-center justify-between gap-3"
                  >
                    <div>
                      <span className="text-[10px] font-bold text-purple-700 uppercase tracking-wider block">
                        Module {mIdx + 1}
                      </span>
                      <h4 className="text-xs font-bold text-slate-900 truncate">{m.title} Test</h4>
                      <p className="text-[11px] text-slate-500 mt-0.5">
                        Pass mark: {m.pass_mark || 70}%
                      </p>
                    </div>

                    <div className="flex flex-col items-end gap-1.5 shrink-0">
                      {m.module_test_id ? (
                        <span className="text-[10px] font-bold text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded-full border border-emerald-200">
                          Ready
                        </span>
                      ) : (
                        <span className="text-[10px] font-bold text-amber-700 bg-amber-50 px-2 py-0.5 rounded-full border border-amber-200">
                          Pending
                        </span>
                      )}
                      <Button
                        variant="secondary"
                        size="sm"
                        onClick={() => setManagingModuleTest(m)}
                        className="text-xs font-semibold"
                      >
                        Configure
                      </Button>
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>

          {/* 3. Final Certification Exam */}
          <div className="space-y-4 rounded-xl border border-slate-200 p-5 bg-slate-50/40">
            <div className="flex flex-wrap items-center justify-between gap-2 pb-2 border-b border-slate-200">
              <div className="flex items-center gap-2">
                <ShieldAlert size={18} className="text-[#2563EB]" />
                <h3 className="text-sm font-bold text-slate-900">3. Final Certification Exam & AI Proctoring</h3>
              </div>
              <span className={cn(
                "px-2.5 py-0.5 rounded-full text-xs font-bold",
                finalTestId ? "bg-emerald-50 text-emerald-700 border border-emerald-200" : "bg-amber-50 text-amber-700 border border-amber-200"
              )}>
                {finalTestId ? "Exam Configured & Linked" : "Setup Required"}
              </span>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
              <div className="space-y-3">
                <div>
                  <label className="block text-xs font-bold text-slate-700 mb-1">Exam Title</label>
                  <input
                    type="text"
                    value={examTitle}
                    onChange={(e) => setExamTitle(e.target.value)}
                    placeholder="e.g. Master Python Programming - Certification Exam"
                    className="w-full rounded-xl border border-slate-300 px-3 py-2 text-xs text-slate-900 bg-white focus:outline-none focus:border-[#2563EB]"
                  />
                </div>

                <div className="grid grid-cols-3 gap-2">
                  <div>
                    <label className="block text-xs font-bold text-slate-700 mb-1">Duration (Min)</label>
                    <input
                      type="number"
                      min={10}
                      max={300}
                      value={examDurationMinutes}
                      onChange={(e) => setExamDurationMinutes(Number(e.target.value))}
                      className="w-full rounded-xl border border-slate-300 px-3 py-1.5 text-xs text-slate-900 bg-white focus:outline-none focus:border-[#2563EB]"
                    />
                  </div>
                  <div>
                    <label className="block text-xs font-bold text-slate-700 mb-1">Pass Mark (%)</label>
                    <input
                      type="number"
                      min={10}
                      max={100}
                      value={examPassMark}
                      onChange={(e) => setExamPassMark(Number(e.target.value))}
                      className="w-full rounded-xl border border-slate-300 px-3 py-1.5 text-xs text-slate-900 bg-white focus:outline-none focus:border-[#2563EB]"
                    />
                  </div>
                  <div>
                    <label className="block text-xs font-bold text-slate-700 mb-1">Attempts</label>
                    <input
                      type="number"
                      min={1}
                      max={10}
                      value={examAttempts}
                      onChange={(e) => setExamAttempts(Number(e.target.value))}
                      className="w-full rounded-xl border border-slate-300 px-3 py-1.5 text-xs text-slate-900 bg-white focus:outline-none focus:border-[#2563EB]"
                    />
                  </div>
                </div>
              </div>

              {/* Proctoring Security Toggles */}
              <div className="space-y-2 text-xs">
                <span className="block font-bold text-slate-700 mb-1">AI Proctoring Controls</span>
                <label className="flex items-center justify-between p-2 rounded-lg border border-slate-200 bg-white cursor-pointer hover:bg-slate-50">
                  <div className="flex items-center gap-2">
                    <Camera size={14} className="text-slate-600" />
                    <span className="font-semibold text-slate-800">AI Webcam & Face Verification</span>
                  </div>
                  <input
                    type="checkbox"
                    checked={examCameraRequired}
                    onChange={(e) => setExamCameraRequired(e.target.checked)}
                    className="rounded text-[#2563EB]"
                  />
                </label>
                <label className="flex items-center justify-between p-2 rounded-lg border border-slate-200 bg-white cursor-pointer hover:bg-slate-50">
                  <div className="flex items-center gap-2">
                    <Mic size={14} className="text-slate-600" />
                    <span className="font-semibold text-slate-800">Microphone Audio Monitoring</span>
                  </div>
                  <input
                    type="checkbox"
                    checked={examMicRequired}
                    onChange={(e) => setExamMicRequired(e.target.checked)}
                    className="rounded text-[#2563EB]"
                  />
                </label>
                <label className="flex items-center justify-between p-2 rounded-lg border border-slate-200 bg-white cursor-pointer hover:bg-slate-50">
                  <div className="flex items-center gap-2">
                    <Maximize2 size={14} className="text-slate-600" />
                    <span className="font-semibold text-slate-800">Fullscreen Locked Kiosk Mode</span>
                  </div>
                  <input
                    type="checkbox"
                    checked={examFullscreenRequired}
                    onChange={(e) => setExamFullscreenRequired(e.target.checked)}
                    className="rounded text-[#2563EB]"
                  />
                </label>
              </div>
            </div>

            <div className="flex justify-end pt-2">
              <Button
                variant="primary"
                size="sm"
                onClick={handleSaveFinalExam}
                loading={isSavingFinalExam}
                className="gap-1.5 text-xs font-bold"
              >
                <ShieldAlert size={14} />
                <span>Save Final Exam Settings</span>
              </Button>
            </div>
          </div>

          <div className="flex items-center justify-between pt-4 border-t border-[#E4EAF5]">
            <button
              type="button"
              onClick={() => setCurrentStep(3)}
              className="px-4 py-2 text-xs font-bold text-slate-600 hover:text-navy-950 cursor-pointer"
            >
              ← Back to Modules & Chapters
            </button>

            <button
              type="button"
              onClick={() => setCurrentStep(5)}
              className="inline-flex items-center gap-2 rounded-xl bg-brand-600 px-5 py-2.5 text-xs font-bold text-white shadow-xs hover:bg-brand-700 transition-all cursor-pointer"
            >
              <span>Continue to Review & Publish</span>
              <Icon name="arrowRight" size={14} />
            </button>
          </div>
        </div>
      )}

      {/* =========================================================================
          STEP 5: REVIEW & PUBLISH
          ========================================================================= */}
      {currentStep === 5 && (
        <div className="rounded-2xl border border-[#E4EAF5] bg-white p-6 shadow-card space-y-6">
          <h2 className="text-base font-bold text-navy-950 border-b border-slate-100 pb-3">
            Review Course & Publication
          </h2>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            {/* Summary Box */}
            <div className="md:col-span-2 space-y-5">
              <div className="flex items-start gap-4">
                <div className="flex h-14 w-14 shrink-0 items-center justify-center rounded-2xl bg-blue-50 text-brand-600 font-extrabold text-lg shadow-2xs">
                  {title.slice(0, 2).toUpperCase() || "CR"}
                </div>
                <div>
                  <h3 className="text-lg font-bold text-navy-950">{title || "Untitled Course"}</h3>
                  <p className="text-xs text-slate-500 font-mono mt-0.5">Code: {courseCode || "AUTO-GENERATED"}</p>
                  <p className="text-xs text-slate-600 mt-2 leading-relaxed">
                    {shortDesc || fullDesc || "No description provided."}
                  </p>
                </div>
              </div>

              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 pt-3 border-t border-slate-100 text-xs">
                <div>
                  <span className="text-slate-400 block font-semibold">Category</span>
                  <span className="font-bold text-navy-950">{category}</span>
                </div>
                <div>
                  <span className="text-slate-400 block font-semibold">Instructor</span>
                  <span className="font-bold text-navy-950">{instructor}</span>
                </div>
                <div>
                  <span className="text-slate-400 block font-semibold">Difficulty</span>
                  <span className="font-bold text-navy-950">{difficulty}</span>
                </div>
                <div>
                  <span className="text-slate-400 block font-semibold">Duration</span>
                  <span className="font-bold text-navy-950">{duration}</span>
                </div>
              </div>

              {/* Curriculum Overview */}
              <div className="rounded-xl border border-slate-200 p-4 bg-slate-50/50 space-y-2 text-xs">
                <div className="flex items-center justify-between font-bold text-slate-900 border-b border-slate-200 pb-1.5">
                  <span className="flex items-center gap-1.5">
                    <Layers size={14} className="text-[#2563EB]" />
                    Curriculum Summary
                  </span>
                  <span>{modules.length} Modules · {totalChapters} Chapters</span>
                </div>
                {modules.map((m, idx) => (
                  <div key={m.module_id} className="flex justify-between py-1 text-slate-700">
                    <span>Module {idx + 1}: {m.title}</span>
                    <span className="text-slate-400">{m.topics?.length ?? 0} Chapters</span>
                  </div>
                ))}
              </div>

              {/* Assessments Overview */}
              <div className="rounded-xl border border-slate-200 p-4 bg-slate-50/50 space-y-2 text-xs">
                <div className="flex items-center justify-between font-bold text-slate-900 border-b border-slate-200 pb-1.5">
                  <span className="flex items-center gap-1.5">
                    <ShieldAlert size={14} className="text-[#2563EB]" />
                    Assessments Status
                  </span>
                  <span className="text-emerald-700">Ready</span>
                </div>
                <div className="flex justify-between py-0.5 text-slate-700">
                  <span>Chapter Checkpoint Quizzes</span>
                  <span className="font-bold text-slate-900">
                    {modules.reduce((acc, m) => acc + (m.topics?.filter((t) => t.topic_test_id)?.length ?? 0), 0)} / {totalChapters}
                  </span>
                </div>
                <div className="flex justify-between py-0.5 text-slate-700">
                  <span>Module Tests</span>
                  <span className="font-bold text-slate-900">
                    {modules.filter((m) => m.module_test_id).length} / {modules.length}
                  </span>
                </div>
                <div className="flex justify-between py-0.5 text-slate-700">
                  <span>Final Certification Exam</span>
                  <span className={cn("font-bold", finalTestId ? "text-emerald-700" : "text-amber-700")}>
                    {finalTestId ? "Configured & Active" : "Pending Final Setup"}
                  </span>
                </div>
              </div>
            </div>

            {/* Pricing Summary Cards */}
            <div className="space-y-4">
              <div className="rounded-xl border border-blue-200 bg-blue-50/50 p-4">
                <span className="text-[11px] font-bold text-brand-700 uppercase tracking-wider block">
                  Individual Student
                </span>
                <p className="text-2xl font-extrabold text-navy-950 mt-1">
                  ₹{individualCalc.finalPayable.toLocaleString()}
                </p>
                <p className="text-[11px] text-slate-500 mt-1">Direct buy · {accessValidity} access</p>
              </div>

              <div className="rounded-xl border border-purple-200 bg-purple-50/50 p-4">
                <span className="text-[11px] font-bold text-purple-700 uppercase tracking-wider block">
                  Institutional Bulk
                </span>
                <p className="text-2xl font-extrabold text-navy-950 mt-1">
                  ₹{institutionalCalc.seatPrice.toLocaleString()} <span className="text-xs font-normal text-slate-500">/ student</span>
                </p>
                <p className="text-[11px] text-slate-500 mt-1">
                  {institutionalCalc.students} Students · Quotation: ₹{institutionalCalc.total.toLocaleString()}
                </p>
              </div>

              <div className="rounded-xl border border-emerald-200 bg-emerald-50/60 p-4 space-y-2 text-xs">
                <span className="text-[11px] font-bold text-emerald-800 uppercase tracking-wider block">
                  Publication Status
                </span>
                <p className="text-xs text-emerald-900 font-semibold">
                  Course structure and pricing are validated and ready for students.
                </p>
              </div>
            </div>
          </div>

          <div className="flex flex-wrap items-center justify-between pt-4 border-t border-[#E4EAF5] gap-3">
            <button
              type="button"
              onClick={() => setCurrentStep(4)}
              disabled={isSubmitting}
              className="px-5 py-2 text-xs font-bold text-slate-600 hover:text-navy-950 cursor-pointer"
            >
              ← Back to Assessments
            </button>

            <div className="flex items-center gap-3">
              <button
                type="button"
                onClick={() => navigate(activeCourseId ? `/courses/${activeCourseId}` : "/courses")}
                className="px-4 py-2.5 text-xs font-bold text-slate-700 bg-slate-100 hover:bg-slate-200 rounded-xl transition cursor-pointer"
              >
                Save as Draft & View Workspace
              </button>

              <button
                type="button"
                onClick={handlePublishCourse}
                disabled={isSubmitting}
                className="inline-flex items-center gap-2 rounded-xl bg-emerald-600 px-6 py-2.5 text-xs sm:text-sm font-bold text-white shadow-md hover:bg-emerald-700 transition-all cursor-pointer disabled:opacity-50"
              >
                <Check size={16} />
                <span>{isSubmitting ? "Publishing..." : "Publish Course Now"}</span>
              </button>
            </div>
          </div>
        </div>
      )}

      {/* =========================================================================
          MODALS: ADD/EDIT MODULE, ADD CHAPTER, CHAPTER TEST, MODULE TEST
          ========================================================================= */}
      {isAddModuleOpen && (
        <AddModuleModal
          isOpen={isAddModuleOpen}
          initialData={
            editingModule
              ? {
                  title: editingModule.title,
                  description: editingModule.description || "",
                  position: editingModule.position || 1,
                }
              : undefined
          }
          onClose={() => {
            setIsAddModuleOpen(false);
            setEditingModule(null);
          }}
          onSubmit={handleSaveModule}
        />
      )}

      {deletingModule && (
        <ConfirmModal
          isOpen={Boolean(deletingModule)}
          title="Delete Module"
          description={`Are you sure you want to delete "${deletingModule.title}"? All chapters and questions inside will be permanently removed.`}
          confirmLabel="Delete Module"
          tone="danger"
          onClose={() => setDeletingModule(null)}
          onConfirm={handleDeleteModule}
        />
      )}

      {addingChapterToModule && versionId && activeCourseId && (
        <AddChapterModal
          isOpen={Boolean(addingChapterToModule)}
          moduleTitle={addingChapterToModule.title}
          courseId={activeCourseId}
          moduleId={addingChapterToModule.module_id}
          defaultPosition={(addingChapterToModule.topics?.length ?? 0) + 1}
          onClose={() => setAddingChapterToModule(null)}
          onSubmit={handleSaveChapter}
        />
      )}

      {managingChapterTest && versionId && activeCourseId && (
        <ChapterTestSetupModal
          isOpen={Boolean(managingChapterTest)}
          chapter={managingChapterTest.chapter}
          moduleTitle={managingChapterTest.moduleTitle}
          courseId={activeCourseId}
          versionId={versionId}
          moduleId={managingChapterTest.moduleId}
          onClose={() => setManagingChapterTest(null)}
          onSaved={() => {
            setManagingChapterTest(null);
            refetchVersion();
          }}
        />
      )}

      {managingModuleTest && versionId && activeCourseId && (
        <ModuleTestSetupModal
          isOpen={Boolean(managingModuleTest)}
          courseId={activeCourseId}
          versionId={versionId}
          module={managingModuleTest}
          onClose={() => setManagingModuleTest(null)}
          onSaved={() => {
            setManagingModuleTest(null);
            refetchVersion();
          }}
        />
      )}
    </div>
  );
}
