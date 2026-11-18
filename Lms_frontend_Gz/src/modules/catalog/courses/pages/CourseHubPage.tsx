import { useState, useMemo, useEffect } from "react";
import { useParams, useNavigate, useSearchParams } from "react-router-dom";
import {
  useGetCourseQuery,
  useGetVersionQuery,
  usePublishCourseMutation,
  useUnpublishCourseMutation,
  useUpdateRulesMutation,
} from "@/modules/catalog/courses/api/coursesApi";
import {
  useCreateModuleMutation,
  useUpdateModuleMutation,
  useDeleteModuleMutation,
  useCreateTopicMutation,
  useCreateItemMutation,
} from "@/modules/catalog/courses/api/curriculumApi";
import {
  useListQuestionsQuery,
} from "@/modules/assessments/questions/api/questionsApi";
import {
  useCreateTestMutation,
  useUpdateTestMutation,
  useSubmitTestMutation,
  useApproveTestMutation,
  useGetTestQuery,
} from "@/modules/assessments/tests/api/testsApi";
import {
  useGetAdminCoursePricingQuery,
  useUpdateAdminCoursePricingMutation,
  useGetAdminCoursePricingAuditsQuery,
} from "@/modules/billing/institutional/api/institutionalApi";
import { ModuleTestSetupModal } from "@/modules/catalog/courses/components/modals/ModuleTestSetupModal";
import { ChapterTestSetupModal } from "@/modules/catalog/courses/components/modals/ChapterTestSetupModal";
import {
  AssessmentQuestionManager,
  type ManagedQuestionItem,
} from "@/modules/catalog/course-tests/components/AssessmentQuestionManager";
import type { McqDraft } from "@/modules/catalog/course-tests/hooks/useTestQuestions";
import type { SlotInput } from "@/modules/assessments/tests/sectionTypes";
import { AddModuleModal } from "@/modules/catalog/courses/components/modals/AddModuleModal";
import { AddChapterModal, type ChapterMaterial } from "@/modules/catalog/courses/components/modals/AddChapterModal";
import { AdminVideoPreviewModal } from "@/modules/catalog/courses/components/modals/AdminVideoPreviewModal";
import { AdminPdfPreviewModal } from "@/modules/catalog/courses/components/modals/AdminPdfPreviewModal";
import { ConfirmModal } from "@/modules/catalog/courses/components/common/ConfirmModal";
import { Button, PageLoader } from "@/shared/ui";
import { usePermissions } from "@/modules/user-management/common/permissions/usePermissions";
import { useAuth } from "@/modules/user-management/auth/hooks/useAuth";
import { useListEnrollmentsQuery } from "@/modules/learning/enrollments/api/enrollmentsApi";
import { useListBatchesQuery } from "@/modules/learning/batches/api/batchesApi";
import { useNotify } from "@/core/hooks/useNotify";
import { parseCourseSummary } from "@/modules/catalog/courses/utils/courseMetrics";
import { cn } from "@/core/lib/cn";
import type { ModuleDetail } from "@/modules/catalog/courses/curriculumTypes";
import {
  BookOpen,
  Layers,
  HelpCircle,
  ClipboardCheck,
  ShieldAlert,
  Award,
  DollarSign,
  Eye,
  CheckCircle2,
  Clock,
  Users,
  Video,
  FileText,
  ChevronDown,
  ChevronRight,
  Plus,
  Edit,
  Trash2,
  Download,
  AlertCircle,
  ExternalLink,
  Camera,
  Mic,
  Maximize2,
  Copy,
} from "lucide-react";

export type WorkspaceTab =
  | "overview"
  | "curriculum"
  | "chapter_exams"
  | "module_tests"
  | "final_exam"
  | "certificate"
  | "pricing"
  | "preview";

interface TabDefinition {
  id: WorkspaceTab;
  label: string;
  icon: any;
  badge?: string | number;
}

export function CourseHubPage() {
  const { permissions } = usePermissions();
  const { user } = useAuth();
  const isSuperAdminOrAdmin = permissions.role === "super_admin" || permissions.role === "admin";
  const { courseId } = useParams<{ courseId: string }>();
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const notify = useNotify();

  // If a student navigates to Course Hub, redirect immediately to their learning view
  useEffect(() => {
    if (permissions.role === "student" && courseId) {
      navigate(`/courses/${courseId}/learn`, { replace: true });
    }
  }, [permissions.role, courseId, navigate]);

  const tabParam = (searchParams.get("tab") as WorkspaceTab) || "curriculum";
  const [activeTab, setActiveTab] = useState<WorkspaceTab>(tabParam);

  // Sync tab with URL
  useEffect(() => {
    if (tabParam && tabParam !== activeTab) {
      setActiveTab(tabParam);
    }
  }, [tabParam]);

  const handleSelectTab = (tab: WorkspaceTab) => {
    setActiveTab(tab);
    setSearchParams(
      (prev) => {
        const next = new URLSearchParams(prev);
        next.set("tab", tab);
        return next;
      },
      { replace: true }
    );
  };

  // Fetch course
  const {
    data: course,
    isLoading: isCourseLoading,
    isError: isCourseError,
    error: courseError,
    refetch: refetchCourse,
  } = useGetCourseQuery(courseId ?? "", {
    skip: !courseId,
    refetchOnMountOrArgChange: true,
  });

  const latestVersion = course?.versions?.[course.versions.length - 1];
  const versionId = latestVersion?.version_id;

  // Fetch full curriculum version
  const {
    data: versionDetail,
    isLoading: isVersionLoading,
    refetch: refetchVersion,
  } = useGetVersionQuery(
    { courseId: courseId ?? "", versionId: versionId ?? "" },
    { skip: !courseId || !versionId, refetchOnMountOrArgChange: true }
  );

  // Curriculum mutations
  const [createModule] = useCreateModuleMutation();
  const [updateModule] = useUpdateModuleMutation();
  const [deleteModule] = useDeleteModuleMutation();
  const [createTopic] = useCreateTopicMutation();
  const [createItem] = useCreateItemMutation();
  const [publishCourse] = usePublishCourseMutation();
  const [unpublishCourse] = useUnpublishCourseMutation();
  const [updateRules, { isLoading: isSavingRules }] = useUpdateRulesMutation();

  // Test Authoring mutations for Final Exam
  const [createTest, { isLoading: isCreatingTest }] = useCreateTestMutation();
  const [updateTest, { isLoading: isUpdatingTest }] = useUpdateTestMutation();
  const [submitTest] = useSubmitTestMutation();
  const [approveTest] = useApproveTestMutation();

  // Pricing API queries & mutations
  const { data: pricingList = [], refetch: refetchPricing } = useGetAdminCoursePricingQuery(undefined, {
    skip: !isSuperAdminOrAdmin,
  });
  const [updateCoursePricing, { isLoading: isUpdatingPricing }] = useUpdateAdminCoursePricingMutation();
  const { data: pricingAudits = [], refetch: refetchAudits } = useGetAdminCoursePricingAuditsQuery(
    Number(courseId) || 0,
    { skip: !isSuperAdminOrAdmin || !courseId }
  );

  // Find pricing record for this course
  const currentPricing = useMemo(() => {
    if (!courseId || !pricingList.length) return null;
    return pricingList.find(
      (p) => String(p.course_id) === String(courseId) || p.slug === course?.slug
    );
  }, [pricingList, courseId, course?.slug]);

  // Load real batches & enrollments for exact enrolled students count
  const { data: batchesData } = useListBatchesQuery({ per_page: 100 });
  const { data: enrollmentsData } = useListEnrollmentsQuery({ status: "active", per_page: 100 });

  const enrolledStudents = useMemo(() => {
    if (!courseId) return [];
    const courseBatches = (batchesData?.items ?? []).filter((b) => b.course_id === courseId);
    const courseBatchIds = new Set(courseBatches.map((b) => b.batch_id));
    return (enrollmentsData?.items ?? []).filter((e) => courseBatchIds.has(e.batch_id));
  }, [courseId, batchesData?.items, enrollmentsData?.items]);

  // Load questions bank
  const { data: questionsData } = useListQuestionsQuery({ per_page: 100 });
  const allApprovedQuestions = useMemo(() => {
    const items = questionsData?.items ?? [];
    return items.filter((q) => q.status === "active");
  }, [questionsData]);

  const courseApprovedQuestions = useMemo(() => {
    if (!allApprovedQuestions.length) return [];
    const slug = course?.slug?.toLowerCase() || "";
    const matched = allApprovedQuestions.filter(
      (q) =>
        (q.topics && q.topics.some((t) => slug.includes(t.toLowerCase()) || t.toLowerCase().includes(slug))) ||
        (q as any).course_id === courseId
    );
    return matched.length > 0 ? matched : allApprovedQuestions;
  }, [allApprovedQuestions, course?.slug, courseId]);

  // Final Test detail
  const finalTestId = versionDetail?.rule?.final_test_id;
  const { data: finalTestDetail, refetch: refetchFinalTest } = useGetTestQuery(finalTestId ?? "", {
    skip: !finalTestId,
  });

  // UI state modals
  const [isAddModuleOpen, setIsAddModuleOpen] = useState(false);
  const [editingModule, setEditingModule] = useState<ModuleDetail | null>(null);
  const [deletingModule, setDeletingModule] = useState<ModuleDetail | null>(null);
  const [addingChapterToModule, setAddingChapterToModule] = useState<ModuleDetail | null>(null);
  const [managingModuleTest, setManagingModuleTest] = useState<ModuleDetail | null>(null);
  const [managingChapterTest, setManagingChapterTest] = useState<{ chapter: any; moduleTitle?: string; moduleId: string } | null>(null);
  const [collapsedModules, setCollapsedModules] = useState<Record<string, boolean>>({});

  // Media Preview Modals
  const [videoPreviewTarget, setVideoPreviewTarget] = useState<{
    chapterTitle: string;
    itemTitle?: string;
    mediaId?: string | number | null;
  } | null>(null);
  const [pdfPreviewTarget, setPdfPreviewTarget] = useState<{
    chapterTitle: string;
    itemTitle?: string;
    mediaId?: string | number | null;
  } | null>(null);

  // Final Exam Config State
  const [isConfiguringExam, setIsConfiguringExam] = useState(false);
  const [examTitle, setExamTitle] = useState("");
  const [examDurationMinutes, setExamDurationMinutes] = useState(60);
  const [examPassMark, setExamPassMark] = useState(70);
  const [examAttempts, setExamAttempts] = useState(3);
  const [examCooldownDays, setExamCooldownDays] = useState(1);
  const [examCameraRequired, setExamCameraRequired] = useState(true);
  const [examMicRequired, setExamMicRequired] = useState(true);
  const [examFullscreenRequired, setExamFullscreenRequired] = useState(true);
  const [examCopyPasteBlock, setExamCopyPasteBlock] = useState(true);
  const [examShuffle, setExamShuffle] = useState(true);
  const [finalCustomQuestions, setFinalCustomQuestions] = useState<ManagedQuestionItem[]>([]);
  const [isFinalQuestionsLoaded, setIsFinalQuestionsLoaded] = useState(false);

  // Certificate Settings State
  const [certEnabled, setCertEnabled] = useState(true);
  const [certMinPassScore, setCertMinPassScore] = useState(70);
  const [certSignatoryName, setCertSignatoryName] = useState("Dr. Sneha Reddy");
  const [certSignatoryTitle, setCertSignatoryTitle] = useState("Academic Council Director");
  const [certOrgName, setCertOrgName] = useState("ExamLMS Academy of Technology");

  // Pricing Edit Modal State
  const [isEditPricingOpen, setIsEditPricingOpen] = useState(false);
  const [priceForm, setPriceForm] = useState({
    individualPrice: 1999,
    discountPercent: 10,
    institutionalPrice: 999,
    minSeats: 10,
    maxSeats: 1000,
    reason: "",
  });

  // Sync Final Exam form values
  useEffect(() => {
    if (finalTestDetail) {
      setExamTitle(finalTestDetail.title || "");
      setExamDurationMinutes(finalTestDetail.duration_minutes || 60);
      setExamPassMark(finalTestDetail.pass_mark_percent || versionDetail?.rule?.final_pass_mark || 70);
      setExamAttempts(finalTestDetail.max_attempts || versionDetail?.rule?.final_test_attempts || 3);
      setExamCooldownDays(versionDetail?.rule?.final_test_cooldown_days || 1);
      setExamCameraRequired(finalTestDetail.proctoring_level === "strict" || finalTestDetail.proctoring_level === "basic");
      setExamShuffle(Boolean(finalTestDetail.shuffle_questions));
    } else if (course) {
      setExamTitle(`${course.title} - Final Certification Exam`);
      setExamPassMark(versionDetail?.rule?.final_pass_mark || 70);
      setExamAttempts(versionDetail?.rule?.final_test_attempts || 3);
      setExamCooldownDays(versionDetail?.rule?.final_test_cooldown_days || 1);
    }
  }, [finalTestDetail, course, versionDetail?.rule]);

  // Sync Pricing form values
  useEffect(() => {
    if (currentPricing) {
      setPriceForm({
        individualPrice: currentPricing.individual_price_paise ? currentPricing.individual_price_paise / 100 : 1999,
        discountPercent: currentPricing.discount_percent || 0,
        institutionalPrice: currentPricing.fixed_price_paise
          ? currentPricing.fixed_price_paise / 100
          : currentPricing.institutional_price_per_seat_paise
          ? currentPricing.institutional_price_per_seat_paise / 100
          : 999,
        minSeats: currentPricing.min_students || 10,
        maxSeats: currentPricing.max_students || 1000,
        reason: "",
      });
    }
  }, [currentPricing]);

  // Load final exam questions
  useEffect(() => {
    if (isFinalQuestionsLoaded || !courseId) return;
    let loaded: ManagedQuestionItem[] = [];
    if (finalTestDetail?.sections && finalTestDetail.sections.length > 0) {
      const slots = finalTestDetail.sections.flatMap((s: any) => s.slots || []);
      if (slots.length > 0) {
        loaded = slots.map((slot: any, sIdx: number) => {
          const matched = courseApprovedQuestions.find((q) => String(q.question_id) === String(slot.question_id));
          const opts = (matched as any)?.options?.map((o: any) => ({ id: o.id || "a", text: o.text || "" })) || [
            { id: "a", text: "Option A" },
            { id: "b", text: "Option B" },
            { id: "c", text: "Option C" },
            { id: "d", text: "Option D" },
          ];
          return {
            id: slot.question_id ? String(slot.question_id) : `final-slot-${sIdx}`,
            text: matched?.text || `Final Exam Question #${slot.position || sIdx + 1}`,
            questionType: matched?.question_type || "mcq_single",
            marks: slot.marks || matched?.default_marks || 2,
            options: opts,
            correctAnswer: (matched as any)?.answer_key?.correct || "a",
            explanation: (matched as any)?.explanation || "",
          };
        });
      }
    }
    if (loaded.length === 0 && courseApprovedQuestions.length > 0) {
      loaded = courseApprovedQuestions.slice(0, 10).map((q) => {
        const opts = (q as any).options?.map((o: any) => ({ id: o.id || "a", text: o.text || "" })) || [];
        return {
          id: q.question_id,
          text: q.text,
          questionType: q.question_type || "mcq_single",
          marks: q.default_marks || 2,
          options: opts,
          correctAnswer: (q as any).answer_key?.correct || "a",
          explanation: (q as any).explanation || "",
        };
      });
    }
    setFinalCustomQuestions(loaded);
    setIsFinalQuestionsLoaded(true);
  }, [courseId, isFinalQuestionsLoaded, courseApprovedQuestions, finalTestDetail]);

  const parsedSummary = useMemo(() => {
    return parseCourseSummary(course?.summary);
  }, [course?.summary]);

  const modules = versionDetail?.modules ?? [];
  const isPublished = latestVersion?.status === "published";

  // Chapter metrics
  const totalChapters = useMemo(() => {
    return modules.reduce((acc, m) => acc + (m.topics?.length ?? 0), 0);
  }, [modules]);

  // Readiness Checklist
  const readiness = useMemo(() => {
    const hasBasicInfo = Boolean(course?.title && course?.slug);
    const hasCurriculum = modules.length > 0 && totalChapters > 0;
    const hasAssessments = Boolean(finalTestId || modules.some((m) => m.pass_mark));
    const hasPricing = Boolean(currentPricing && currentPricing.individual_price_paise > 0);
    const isReadyToPublish = hasBasicInfo && hasCurriculum;
    return {
      hasBasicInfo,
      hasCurriculum,
      hasAssessments,
      hasPricing,
      isReadyToPublish,
    };
  }, [course, modules, totalChapters, finalTestId, currentPricing]);

  // Tab definitions
  const tabs: TabDefinition[] = [
    { id: "overview", label: "Course Details", icon: BookOpen },
    { id: "curriculum", label: "Curriculum", icon: Layers, badge: modules.length },
    { id: "chapter_exams", label: "Chapter Exams", icon: HelpCircle, badge: totalChapters },
    { id: "module_tests", label: "Module Tests", icon: ClipboardCheck, badge: modules.length },
    { id: "final_exam", label: "Final Exam", icon: ShieldAlert, badge: finalTestId ? "Active" : undefined },
    { id: "certificate", label: "Certificate", icon: Award },
    { id: "pricing", label: "Pricing & History", icon: DollarSign },
    { id: "preview", label: "Preview & Publish", icon: Eye },
  ];

  if (isCourseLoading || (versionId && isVersionLoading)) {
    return <PageLoader label="Loading course workspace..." />;
  }

  if (isCourseError || !course) {
    return (
      <div className="flex flex-col items-center justify-center p-16 text-center max-w-md mx-auto">
        <div className="w-14 h-14 rounded-2xl bg-rose-50 text-rose-600 flex items-center justify-center mb-4 ring-1 ring-rose-200">
          <AlertCircle size={28} />
        </div>
        <h3 className="text-lg font-bold text-slate-900 mb-1">Course not found</h3>
        <p className="text-xs text-slate-500 mb-6 leading-relaxed">
          {(courseError as any)?.data?.message || "The requested course could not be loaded or was removed."}
        </p>
        <div className="flex items-center gap-3">
          <Button variant="secondary" onClick={() => refetchCourse()}>
            Retry
          </Button>
          <Button variant="primary" onClick={() => navigate("/courses")}>
            Back to Courses
          </Button>
        </div>
      </div>
    );
  }

  // Handle Save Module
  const handleSaveModule = async (data: { title: string; description: string; position: number }) => {
    if (!courseId || !versionId) return;
    try {
      if (editingModule) {
        await updateModule({
          courseId,
          versionId,
          moduleId: editingModule.module_id,
          body: { title: data.title },
        }).unwrap();
        notify.success("Module updated");
      } else {
        await createModule({
          courseId,
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

  // Handle Delete Module
  const handleDeleteModule = async () => {
    if (!courseId || !versionId || !deletingModule) return;
    try {
      await deleteModule({
        courseId,
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

  // Handle Save Chapter directly in Course Hub
  const handleSaveChapterInHub = async (data: {
    title: string;
    position: number;
    description: string;
    objectives: string[];
    materials: ChapterMaterial[];
  }) => {
    if (!courseId || !versionId || !addingChapterToModule) return;
    try {
      const res = await createTopic({
        courseId,
        versionId,
        moduleId: addingChapterToModule.module_id,
        body: { title: data.title, pass_mark: 70 },
      }).unwrap();

      if (data.materials && data.materials.length > 0 && res.topic?.topic_id) {
        for (const mat of data.materials) {
          await createItem({
            courseId,
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

  // Toggle Module Collapse
  const toggleCollapse = (modId: string) => {
    setCollapsedModules((prev) => ({ ...prev, [modId]: !prev[modId] }));
  };

  // Handle Save Final Exam
  const handleSaveFinalExam = async () => {
    if (!courseId || !versionId) return;
    try {
      let testPublicId = finalTestId;
      const slots: SlotInput[] = finalCustomQuestions.map((q) => ({
        slot_type: "fixed",
        question_id: String(q.id).startsWith("final-") ? undefined : q.id,
        marks: q.marks || 2,
      }));

      if (testPublicId) {
        await updateTest({
          testId: testPublicId,
          body: {
            title: examTitle || `${course.title} - Final Certification Exam`,
            duration_minutes: Number(examDurationMinutes) || 60,
            pass_mark_percent: Number(examPassMark) || 70,
            max_attempts: Number(examAttempts) || 3,
            shuffle_questions: examShuffle,
            proctoring_level: examCameraRequired ? "strict" : "none",
          },
        }).unwrap();
      } else {
        const created = await createTest({
          title: examTitle || `${course.title} - Final Certification Exam`,
          kind: "final",
          duration_minutes: Number(examDurationMinutes) || 60,
          pass_mark_percent: Number(examPassMark) || 70,
          max_attempts: Number(examAttempts) || 3,
          shuffle_questions: examShuffle,
          proctoring_level: examCameraRequired ? "strict" : "none",
          sections: [{ title: "Comprehensive Final Assessment", slots }],
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
        courseId,
        versionId,
        body: {
          final_pass_mark: Number(examPassMark) || 70,
          final_test_attempts: Number(examAttempts) || 3,
          final_test_cooldown_days: Number(examCooldownDays) || 1,
          final_test_id: testPublicId || undefined,
        },
      }).unwrap();

      notify.success("Final Exam & Proctoring settings saved successfully!");
      setIsConfiguringExam(false);
      refetchVersion();
      if (testPublicId) refetchFinalTest();
    } catch (err: any) {
      notify.apiError(err);
    }
  };

  // Handle Save Pricing
  const handleSavePricing = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!courseId) return;
    if (!priceForm.reason.trim()) {
      notify.error("A reason for this price change is required for the audit record.");
      return;
    }
    try {
      await updateCoursePricing({
        course_id: courseId,
        course_title: course.title,
        course_code: course.slug.toUpperCase(),
        category: parsedSummary.category,
        individual_price_paise: Math.round(priceForm.individualPrice * 100),
        pricing_method: "fixed",
        fixed_price_paise: Math.round(priceForm.institutionalPrice * 100),
        monthly_price_paise: 0,
        hourly_price_paise: 0,
        discount_percent: priceForm.discountPercent,
        gst_percent: 18,
        min_students: priceForm.minSeats,
        max_students: priceForm.maxSeats,
        reason: priceForm.reason.trim(),
      }).unwrap();
      notify.success("Course pricing updated and logged to audit trail!");
      setIsEditPricingOpen(false);
      refetchPricing();
      refetchAudits();
    } catch (err: any) {
      notify.apiError(err);
    }
  };

  // Export Audits to CSV
  const handleExportAuditsCsv = () => {
    if (!pricingAudits.length) {
      notify.info("No pricing audit records to export yet.");
      return;
    }
    const headers = ["Audit ID", "Course ID", "Previous Indiv Price", "New Indiv Price", "Previous Inst Price", "New Inst Price", "Changed By", "Reason", "Date"];
    const rows = pricingAudits.map((a) => [
      a.id,
      a.course_id,
      (a.previous_individual_price_paise / 100).toFixed(2),
      (a.new_individual_price_paise / 100).toFixed(2),
      (a.previous_institutional_price_paise / 100).toFixed(2),
      (a.new_institutional_price_paise / 100).toFixed(2),
      a.admin_email || a.admin_name || `Admin #${a.admin_user_id}`,
      `"${(a.reason || "").replace(/"/g, '""')}"`,
      new Date(a.created_at || Date.now()).toLocaleString(),
    ]);
    const csvContent = "data:text/csv;charset=utf-8," + [headers.join(","), ...rows.map((r) => r.join(","))].join("\n");
    const encodedUri = encodeURI(csvContent);
    const link = document.createElement("a");
    link.setAttribute("href", encodedUri);
    link.setAttribute("download", `Course_${courseId}_Pricing_History.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    notify.success("Price change history CSV downloaded.");
  };

  // Handle Publish / Unpublish
  const handleTogglePublish = async () => {
    if (!courseId) return;
    if (!isPublished && !readiness.isReadyToPublish) {
      notify.error("Please add at least one module and chapter before publishing.");
      return;
    }
    try {
      if (isPublished) {
        await unpublishCourse(courseId).unwrap();
        notify.success("Course moved to Draft.");
      } else {
        await publishCourse(courseId).unwrap();
        notify.success("Course published successfully!");
      }
      refetchCourse();
    } catch (err: any) {
      notify.apiError(err);
    }
  };

  return (
    <div className="max-w-7xl mx-auto space-y-6 pb-16">
      {/* 1. Header Bar with Course Context and Quick Actions */}
      <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-2xs">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div className="flex items-center gap-4 min-w-0">
            <div className="w-16 h-16 rounded-xl bg-gradient-to-br from-[#10234B] to-[#1E3A8A] flex items-center justify-center text-white shrink-0 shadow-sm overflow-hidden border border-slate-200">
              <BookOpen size={28} />
            </div>
            <div className="min-w-0">
              <div className="flex items-center gap-2.5 flex-wrap">
                <span className="text-xs font-mono font-semibold px-2 py-0.5 rounded bg-slate-100 text-slate-700">
                  {course.slug.toUpperCase()}
                </span>
                <h1 className="text-xl font-bold text-slate-900 tracking-tight truncate">{course.title}</h1>
                <span
                  className={cn(
                    "px-2.5 py-0.5 rounded-full text-xs font-bold",
                    isPublished ? "bg-emerald-50 text-emerald-700 ring-1 ring-emerald-200" : "bg-amber-50 text-amber-700 ring-1 ring-amber-200"
                  )}
                >
                  {isPublished ? "Published" : "Draft"}
                </span>
              </div>
              <div className="flex flex-wrap items-center gap-4 text-xs text-slate-500 font-medium mt-1.5">
                <span className="flex items-center gap-1.5">
                  <Clock size={13} className="text-slate-400" />
                  {parsedSummary.duration || "Self-Paced"}
                </span>
                <span className="flex items-center gap-1.5">
                  <Layers size={13} className="text-slate-400" />
                  {modules.length} {modules.length === 1 ? "Module" : "Modules"} ({totalChapters} Chapters)
                </span>
                <span className="flex items-center gap-1.5">
                  <Users size={13} className="text-slate-400" />
                  {enrolledStudents.length} Students Enrolled
                </span>
                <span className="flex items-center gap-1.5">
                  <DollarSign size={13} className="text-slate-400" />
                  {currentPricing?.individual_price_paise
                    ? `₹${(currentPricing.individual_price_paise / 100).toLocaleString("en-IN")}`
                    : "Pricing not set"}
                </span>
              </div>
            </div>
          </div>

          <div className="flex items-center gap-2 shrink-0 flex-wrap">
            <Button
              variant="primary"
              size="sm"
              onClick={() => {
                setEditingModule(null);
                setIsAddModuleOpen(true);
              }}
              className="gap-1.5 text-xs font-semibold shadow-xs"
            >
              <Plus size={14} />
              <span>Insert Module</span>
            </Button>

            {modules.length > 0 && (
              <Button
                variant="secondary"
                size="sm"
                onClick={() => setAddingChapterToModule(modules[0] ?? null)}
                className="gap-1.5 text-xs font-semibold"
              >
                <Plus size={14} />
                <span>Insert Chapter</span>
              </Button>
            )}

            <Button
              variant="secondary"
              size="sm"
              onClick={() => handleSelectTab("chapter_exams")}
              className="gap-1.5 text-xs font-semibold"
            >
              <HelpCircle size={14} />
              <span>Chapter Tests</span>
            </Button>

            <Button
              variant="secondary"
              size="sm"
              onClick={() => handleSelectTab("module_tests")}
              className="gap-1.5 text-xs font-semibold"
            >
              <ClipboardCheck size={14} />
              <span>Module Tests</span>
            </Button>

            <Button
              variant="secondary"
              size="sm"
              onClick={() => handleSelectTab("final_exam")}
              className="gap-1.5 text-xs font-semibold"
            >
              <ShieldAlert size={14} />
              <span>Final Exam</span>
            </Button>

            <Button
              variant="secondary"
              size="sm"
              onClick={() => navigate(`/courses/${courseId}/learn`)}
              className="gap-1.5 text-xs font-semibold"
            >
              <Eye size={14} />
              <span>Preview</span>
            </Button>

            <Button
              variant={isPublished ? "secondary" : "primary"}
              size="sm"
              onClick={handleTogglePublish}
              className="gap-1.5 text-xs font-semibold"
            >
              {isPublished ? "Unpublish" : "Publish"}
            </Button>
          </div>
        </div>
      </div>

      {/* Visual Workflow Banner: Modules -> Chapters -> Chapter Tests -> Module Tests -> Final Exam */}
      <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-2xs">
        <div className="flex items-center justify-between pb-3 border-b border-slate-100">
          <div className="flex items-center gap-2">
            <Layers size={16} className="text-[#2563EB]" />
            <h3 className="text-xs font-bold text-slate-900 uppercase tracking-wider">
              Course Structure & Assessments Pipeline
            </h3>
          </div>
          <span className="text-[11px] font-semibold text-slate-500">
            {modules.length} Modules · {totalChapters} Chapters · {finalTestId ? "Final Exam Ready" : "Final Exam Pending"}
          </span>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3 pt-3">
          {/* Step 1: Modules & Chapters */}
          <div className="p-3 rounded-xl border border-blue-100 bg-blue-50/40 flex flex-col justify-between">
            <div>
              <div className="flex items-center justify-between">
                <span className="text-[10px] font-bold text-[#2563EB] uppercase tracking-wider">1. Curriculum</span>
                <span className="text-xs font-bold text-slate-800">{modules.length} Modules</span>
              </div>
              <p className="text-xs font-bold text-slate-900 mt-1">Modules & Chapters</p>
              <p className="text-[11px] text-slate-500 mt-0.5">
                {totalChapters} chapter lectures with video & notes
              </p>
            </div>
            <div className="flex items-center gap-1.5 mt-3 pt-2 border-t border-blue-100/80">
              <button
                type="button"
                onClick={() => {
                  setEditingModule(null);
                  setIsAddModuleOpen(true);
                }}
                className="flex-1 py-1 px-2 rounded-lg bg-[#2563EB] text-white text-[11px] font-bold hover:bg-blue-700 transition cursor-pointer"
              >
                + Module
              </button>
              {modules.length > 0 && (
                <button
                  type="button"
                  onClick={() => setAddingChapterToModule(modules[0] ?? null)}
                  className="flex-1 py-1 px-2 rounded-lg bg-white border border-blue-300 text-[#2563EB] text-[11px] font-bold hover:bg-blue-50 transition cursor-pointer"
                >
                  + Chapter
                </button>
              )}
            </div>
          </div>

          {/* Step 2: Chapter Tests */}
          <div className="p-3 rounded-xl border border-indigo-100 bg-indigo-50/40 flex flex-col justify-between">
            <div>
              <div className="flex items-center justify-between">
                <span className="text-[10px] font-bold text-indigo-600 uppercase tracking-wider">2. Chapter Quizzes</span>
                <span className="text-xs font-bold text-slate-800">
                  {modules.reduce((acc, m) => acc + (m.topics?.filter((t) => t.topic_test_id)?.length ?? 0), 0)} / {totalChapters}
                </span>
              </div>
              <p className="text-xs font-bold text-slate-900 mt-1">Chapter Tests</p>
              <p className="text-[11px] text-slate-500 mt-0.5">Quick checkpoint quizzes after each chapter</p>
            </div>
            <div className="mt-3 pt-2 border-t border-indigo-100/80">
              <button
                type="button"
                onClick={() => handleSelectTab("chapter_exams")}
                className="w-full py-1 px-2 rounded-lg bg-white border border-indigo-300 text-indigo-700 text-[11px] font-bold hover:bg-indigo-50 transition cursor-pointer"
              >
                Manage Chapter Tests →
              </button>
            </div>
          </div>

          {/* Step 3: Module Tests */}
          <div className="p-3 rounded-xl border border-purple-100 bg-purple-50/40 flex flex-col justify-between">
            <div>
              <div className="flex items-center justify-between">
                <span className="text-[10px] font-bold text-purple-600 uppercase tracking-wider">3. Module Tests</span>
                <span className="text-xs font-bold text-slate-800">
                  {modules.filter((m) => m.module_test_id).length} / {modules.length}
                </span>
              </div>
              <p className="text-xs font-bold text-slate-900 mt-1">Module Tests</p>
              <p className="text-[11px] text-slate-500 mt-0.5">End-of-module assessment unlocking next module</p>
            </div>
            <div className="mt-3 pt-2 border-t border-purple-100/80">
              <button
                type="button"
                onClick={() => handleSelectTab("module_tests")}
                className="w-full py-1 px-2 rounded-lg bg-white border border-purple-300 text-purple-700 text-[11px] font-bold hover:bg-purple-50 transition cursor-pointer"
              >
                Manage Module Tests →
              </button>
            </div>
          </div>

          {/* Step 4: Final Exam */}
          <div className="p-3 rounded-xl border border-emerald-100 bg-emerald-50/40 flex flex-col justify-between">
            <div>
              <div className="flex items-center justify-between">
                <span className="text-[10px] font-bold text-emerald-700 uppercase tracking-wider">4. Final Exam</span>
                <span className={cn(
                  "text-[10px] font-bold px-1.5 py-0.2 rounded-full",
                  finalTestId ? "bg-emerald-100 text-emerald-800" : "bg-amber-100 text-amber-800"
                )}>
                  {finalTestId ? "Configured" : "Not Set"}
                </span>
              </div>
              <p className="text-xs font-bold text-slate-900 mt-1">Final Proctored Exam</p>
              <p className="text-[11px] text-slate-500 mt-0.5">Comprehensive graduation test with AI proctoring</p>
            </div>
            <div className="mt-3 pt-2 border-t border-emerald-100/80">
              <button
                type="button"
                onClick={() => handleSelectTab("final_exam")}
                className="w-full py-1 px-2 rounded-lg bg-emerald-600 text-white text-[11px] font-bold hover:bg-emerald-700 transition cursor-pointer"
              >
                {finalTestId ? "Edit Final Exam →" : "Setup Final Exam →"}
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* 2. Udemy-Style Horizontal Workspace Tabs */}
      <div className="rounded-2xl border border-slate-200 bg-white shadow-2xs overflow-hidden">
        <div className="flex border-b border-slate-200 overflow-x-auto no-scrollbar px-2 sm:px-4 bg-slate-50/60">
          {tabs.map((tab) => {
            const IconComponent = tab.icon;
            const isActive = activeTab === tab.id;
            return (
              <button
                key={tab.id}
                type="button"
                onClick={() => handleSelectTab(tab.id)}
                className={cn(
                  "flex items-center gap-2 px-4 py-3.5 text-xs font-semibold whitespace-nowrap transition-all border-b-2 cursor-pointer",
                  isActive
                    ? "border-[#2563EB] text-[#2563EB] bg-white font-bold shadow-2xs"
                    : "border-transparent text-slate-600 hover:text-slate-900 hover:bg-slate-100/60"
                )}
              >
                <IconComponent size={15} className={isActive ? "text-[#2563EB]" : "text-slate-400"} />
                <span>{tab.label}</span>
                {tab.badge !== undefined && (
                  <span
                    className={cn(
                      "px-1.5 py-0.2 rounded-full text-[10px] font-bold",
                      isActive ? "bg-blue-100 text-blue-800" : "bg-slate-200/80 text-slate-700"
                    )}
                  >
                    {tab.badge}
                  </span>
                )}
              </button>
            );
          })}
        </div>

        {/* ========================================================================= */}
        {/* TAB 1: COURSE DETAILS                                                    */}
        {/* ========================================================================= */}
        {activeTab === "overview" && (
          <div className="p-6 space-y-6">
            <div className="flex items-center justify-between pb-4 border-b border-slate-100">
              <div>
                <h3 className="text-base font-bold text-slate-900">Course Information & Metadata</h3>
                <p className="text-xs text-slate-500 mt-0.5">
                  Core marketing details, outcomes, requirements, and classification.
                </p>
              </div>
              <Button
                variant="primary"
                size="sm"
                onClick={() => navigate(`/courses/${courseId}/edit?from=hub`)}
                className="gap-1.5 text-xs font-semibold"
              >
                <Edit size={14} />
                <span>Edit Course Details</span>
              </Button>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
              <div className="md:col-span-2 space-y-5">
                <div className="rounded-xl border border-slate-200 p-4 bg-slate-50/40">
                  <h4 className="text-xs font-bold text-slate-900 uppercase tracking-wider mb-2">Description</h4>
                  <p className="text-xs text-slate-700 leading-relaxed whitespace-pre-line">
                    {parsedSummary.cleanDescription || course.summary || "No description provided."}
                  </p>
                </div>

                <div className="rounded-xl border border-slate-200 p-4 bg-slate-50/40">
                  <h4 className="text-xs font-bold text-slate-900 uppercase tracking-wider mb-2">Learning Outcomes</h4>
                  {parsedSummary.learningOutcomes.length > 0 ? (
                    <ul className="space-y-1.5">
                      {parsedSummary.learningOutcomes.map((item: string, idx: number) => (
                        <li key={idx} className="flex items-start gap-2 text-xs text-slate-700">
                          <CheckCircle2 size={14} className="text-emerald-600 mt-0.5 shrink-0" />
                          <span>{item}</span>
                        </li>
                      ))}
                    </ul>
                  ) : (
                    <p className="text-xs text-slate-500 italic">No specific learning outcomes listed.</p>
                  )}
                </div>

                <div className="rounded-xl border border-slate-200 p-4 bg-slate-50/40">
                  <h4 className="text-xs font-bold text-slate-900 uppercase tracking-wider mb-2">Prerequisites</h4>
                  {parsedSummary.prerequisites.length > 0 ? (
                    <ul className="space-y-1.5">
                      {parsedSummary.prerequisites.map((item: string, idx: number) => (
                        <li key={idx} className="flex items-start gap-2 text-xs text-slate-700">
                          <span className="w-1.5 h-1.5 rounded-full bg-slate-400 mt-1.5 shrink-0" />
                          <span>{item}</span>
                        </li>
                      ))}
                    </ul>
                  ) : (
                    <p className="text-xs text-slate-500 italic">None required. Suitable for all skill levels.</p>
                  )}
                </div>
              </div>

              <div className="space-y-5">
                <div className="rounded-xl border border-slate-200 p-4 bg-slate-50/40 space-y-3">
                  <h4 className="text-xs font-bold text-slate-900 uppercase tracking-wider">Specifications</h4>
                  <div className="space-y-2.5 text-xs">
                    <div className="flex justify-between py-1 border-b border-slate-200/60">
                      <span className="text-slate-500">Course Code</span>
                      <span className="font-mono font-bold text-slate-900">{course.slug.toUpperCase()}</span>
                    </div>
                    <div className="flex justify-between py-1 border-b border-slate-200/60">
                      <span className="text-slate-500">Category</span>
                      <span className="font-semibold text-slate-900">{parsedSummary.category}</span>
                    </div>
                    <div className="flex justify-between py-1 border-b border-slate-200/60">
                      <span className="text-slate-500">Instructor</span>
                      <span className="font-semibold text-slate-900">{parsedSummary.instructor}</span>
                    </div>
                    <div className="flex justify-between py-1 border-b border-slate-200/60">
                      <span className="text-slate-500">Difficulty</span>
                      <span className="font-semibold text-slate-900 capitalize">{parsedSummary.level || "Intermediate"}</span>
                    </div>
                    <div className="flex justify-between py-1 border-b border-slate-200/60">
                      <span className="text-slate-500">Duration</span>
                      <span className="font-semibold text-slate-900">{parsedSummary.duration || "40 hours"}</span>
                    </div>
                    <div className="flex justify-between py-1 border-b border-slate-200/60">
                      <span className="text-slate-500">Pass Percentage</span>
                      <span className="font-semibold text-emerald-700">{parsedSummary.passPercentage || "70%"}</span>
                    </div>
                    <div className="flex justify-between py-1">
                      <span className="text-slate-500">Created On</span>
                      <span className="font-semibold text-slate-900">
                        {new Date(course.created_at).toLocaleDateString()}
                      </span>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* ========================================================================= */}
        {/* TAB 2: CURRICULUM (Modules & Chapters with Video Quality & PDF Viewer)   */}
        {/* ========================================================================= */}
        {activeTab === "curriculum" && (
          <div className="p-6 space-y-5">
            <div className="flex flex-wrap items-center justify-between gap-3 pb-3 border-b border-slate-100">
              <div>
                <h3 className="text-base font-bold text-slate-900">Curriculum Builder</h3>
                <p className="text-xs text-slate-500 mt-0.5">
                  Organize your course into sequential modules, video lectures with multi-renditions, and PDF notes.
                </p>
              </div>
              <div className="flex items-center gap-2">
                <Button
                  variant="primary"
                  size="sm"
                  onClick={() => {
                    setEditingModule(null);
                    setIsAddModuleOpen(true);
                  }}
                  className="gap-1.5 text-xs font-semibold"
                >
                  <Plus size={14} />
                  <span>Add Module</span>
                </Button>
              </div>
            </div>

            {modules.length === 0 ? (
              <div className="text-center py-16 border-2 border-dashed border-slate-200 rounded-2xl bg-slate-50/50">
                <Layers size={36} className="mx-auto text-slate-300 mb-2" />
                <h4 className="text-sm font-bold text-slate-800">No modules in this course yet</h4>
                <p className="text-xs text-slate-500 mt-1 mb-4 max-w-sm mx-auto">
                  Get started by adding your first module to structure your course topics and learning chapters.
                </p>
                <Button variant="primary" size="sm" onClick={() => setIsAddModuleOpen(true)}>
                  Create First Module
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
                      className="rounded-xl border border-slate-200 bg-white shadow-2xs overflow-hidden transition-all"
                    >
                      {/* Module Header Bar */}
                      <div className="flex items-center justify-between p-4 bg-slate-50/80 border-b border-slate-100 gap-3">
                        <div
                          className="flex items-center gap-3 min-w-0 flex-1 cursor-pointer select-none"
                          onClick={() => toggleCollapse(m.module_id)}
                        >
                          <button
                            type="button"
                            className="p-1 rounded text-slate-400 hover:text-slate-700"
                            aria-label="Toggle module"
                          >
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

                        <div className="flex items-center gap-2 shrink-0 flex-wrap">
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
                            <span>Add Chapter</span>
                          </Button>
                          <Button
                            variant="secondary"
                            size="sm"
                            onClick={() => setManagingModuleTest(m)}
                            className={cn(
                              "text-xs font-semibold gap-1",
                              m.module_test_id
                                ? "text-emerald-700 border-emerald-200 bg-emerald-50/60"
                                : "text-[#2563EB] border-blue-200 bg-blue-50/40 hover:bg-blue-100/50"
                            )}
                          >
                            <ClipboardCheck size={13} />
                            <span>{m.module_test_id ? "Module Test Ready" : "Setup Module Test"}</span>
                          </Button>
                          <Button
                            variant="secondary"
                            size="sm"
                            onClick={() => navigate(`/courses/${courseId}/modules/${m.module_id}/chapters`)}
                            className="text-xs font-semibold"
                          >
                            <span>Manage Chapters</span>
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
                            <div className="p-6 text-center text-xs text-slate-400">
                              No chapters in this module. Click "Manage Chapters" to add video lectures and study notes.
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
                                            <Video size={11} /> Video Lecture (1080p HD)
                                          </span>
                                        ) : (
                                          <span className="text-[11px] text-slate-400">No video attached</span>
                                        )}
                                        {pdfItem ? (
                                          <span className="inline-flex items-center gap-1 text-[11px] font-medium text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded border border-emerald-200">
                                            <FileText size={11} /> Lecture Notes (PDF)
                                          </span>
                                        ) : (
                                          <span className="text-[11px] text-slate-400">No PDF attached</span>
                                        )}
                                      </div>
                                    </div>
                                  </div>

                                  <div className="flex items-center gap-2">
                                    {videoItem && (
                                      <Button
                                        variant="secondary"
                                        size="sm"
                                        onClick={() =>
                                          setVideoPreviewTarget({
                                            chapterTitle: ch.title,
                                            itemTitle: videoItem.title,
                                            mediaId: (videoItem as any).media_id || (videoItem as any).content_id,
                                          })
                                        }
                                        className="text-[11px] px-2.5 py-1 gap-1"
                                      >
                                        <Eye size={12} /> Video
                                      </Button>
                                    )}
                                    {pdfItem && (
                                      <Button
                                        variant="secondary"
                                        size="sm"
                                        onClick={() =>
                                          setPdfPreviewTarget({
                                            chapterTitle: ch.title,
                                            itemTitle: pdfItem.title,
                                            mediaId: (pdfItem as any).media_id || (pdfItem as any).content_id,
                                          })
                                        }
                                        className="text-[11px] px-2.5 py-1 gap-1"
                                      >
                                        <Eye size={12} /> PDF Notes
                                      </Button>
                                    )}
                                    {ch.topic_test_id ? (
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
                                        className="text-[11px] px-2.5 py-1 gap-1 text-emerald-700 border-emerald-200 bg-emerald-50/70 hover:bg-emerald-100"
                                      >
                                        <CheckCircle2 size={12} className="text-emerald-600" />
                                        <span>Quiz Ready (Pass {ch.pass_mark || 70}%)</span>
                                      </Button>
                                    ) : (
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
                                        className="text-[11px] px-2.5 py-1 gap-1 text-[#2563EB] border-blue-200 bg-blue-50/50 hover:bg-blue-100"
                                      >
                                        <Plus size={12} />
                                        <span>Setup Quiz</span>
                                      </Button>
                                    )}
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
          </div>
        )}

        {/* ========================================================================= */}
        {/* TAB 3: CHAPTER EXAMS (Quizzes per chapter)                              */}
        {/* ========================================================================= */}
        {activeTab === "chapter_exams" && (
          <div className="p-6 space-y-5">
            <div className="pb-3 border-b border-slate-100">
              <h3 className="text-base font-bold text-slate-900">Chapter Quizzes & Checkpoints</h3>
              <p className="text-xs text-slate-500 mt-0.5">
                Practice quizzes presented after each chapter to reinforce learning concepts.
              </p>
            </div>

            <div className="divide-y divide-slate-100 border border-slate-200 rounded-xl overflow-hidden">
              {modules.flatMap((m) => (m.topics ?? []).map((t) => ({ ...t, moduleTitle: m.title }))).length === 0 ? (
                <div className="p-12 text-center text-xs text-slate-500">
                  No chapters available. Add modules and chapters in Curriculum tab first.
                </div>
              ) : (
                modules.flatMap((m) =>
                  (m.topics ?? []).map((ch, chIdx) => (
                    <div
                      key={ch.topic_id}
                      className="p-4 flex flex-wrap items-center justify-between gap-4 bg-white hover:bg-slate-50/50 transition-colors"
                    >
                      <div className="flex items-center gap-3">
                        <div className="w-8 h-8 rounded-lg bg-blue-50 text-[#2563EB] flex items-center justify-center font-bold text-xs shrink-0">
                          Q
                        </div>
                        <div>
                          <span className="text-[10.5px] font-semibold text-slate-400 uppercase tracking-wider block">
                            {m.title} · Chapter {chIdx + 1}
                          </span>
                          <h4 className="text-xs font-bold text-slate-900">{ch.title} Quiz</h4>
                          <p className="text-[11px] text-slate-500">5 Questions · Pass mark 70% · Unlimited attempts</p>
                        </div>
                      </div>

                      <div className="flex items-center gap-2">
                        {ch.topic_test_id ? (
                          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[11px] font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200">
                            <CheckCircle2 size={12} /> Active Checkpoint
                          </span>
                        ) : (
                          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[11px] font-semibold bg-amber-50 text-amber-700 border border-amber-200">
                            Pending Setup
                          </span>
                        )}
                        <Button
                          variant="primary"
                          size="sm"
                          onClick={() => setManagingChapterTest({ chapter: ch, moduleTitle: m.title, moduleId: m.module_id })}
                          className="text-xs font-semibold"
                        >
                          Configure Quiz
                        </Button>
                      </div>
                    </div>
                  ))
                )
              )}
            </div>
          </div>
        )}

        {/* ========================================================================= */}
        {/* TAB 4: MODULE TESTS                                                      */}
        {/* ========================================================================= */}
        {activeTab === "module_tests" && (
          <div className="p-6 space-y-5">
            <div className="pb-3 border-b border-slate-100">
              <h3 className="text-base font-bold text-slate-900">Module Mastery Assessments</h3>
              <p className="text-xs text-slate-500 mt-0.5">
                Comprehensive end-of-module tests that unlock subsequent modules upon passing.
              </p>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {modules.map((m, idx) => (
                <div key={m.module_id} className="rounded-xl border border-slate-200 p-5 bg-white shadow-2xs space-y-4">
                  <div className="flex items-start justify-between gap-3">
                    <div className="flex items-center gap-3">
                      <div className="w-10 h-10 rounded-xl bg-purple-50 text-purple-700 flex items-center justify-center font-bold text-sm shrink-0 border border-purple-200">
                        M{idx + 1}
                      </div>
                      <div>
                        <h4 className="text-sm font-bold text-slate-900">{m.title} Test</h4>
                        <p className="text-xs text-slate-500">End-of-Module Evaluation</p>
                      </div>
                    </div>
                    <span className="px-2 py-0.5 rounded-full text-[11px] font-bold bg-blue-50 text-blue-700">
                      Pass: {m.pass_mark || 70}%
                    </span>
                  </div>

                  <div className="grid grid-cols-3 gap-2 py-2 border-y border-slate-100 text-center text-xs">
                    <div>
                      <span className="text-slate-400 text-[10px] uppercase font-bold block">Questions</span>
                      <b className="text-slate-800">10 MCQs</b>
                    </div>
                    <div>
                      <span className="text-slate-400 text-[10px] uppercase font-bold block">Duration</span>
                      <b className="text-slate-800">20 Mins</b>
                    </div>
                    <div>
                      <span className="text-slate-400 text-[10px] uppercase font-bold block">Retakes</span>
                      <b className="text-slate-800">3 Allowed</b>
                    </div>
                  </div>

                  <div className="flex items-center justify-between gap-2 pt-1">
                    <Button
                      variant="secondary"
                      size="sm"
                      onClick={() => navigate(`/courses/${courseId}/modules/${m.module_id}/test`)}
                      className="text-xs font-semibold"
                    >
                      Preview Test
                    </Button>
                    <Button
                      variant="primary"
                      size="sm"
                      onClick={() => setManagingModuleTest(m)}
                      className="text-xs font-semibold"
                    >
                      Configure Test
                    </Button>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* ========================================================================= */}
        {/* TAB 5: FINAL EXAM & PROCTORING                                           */}
        {/* ========================================================================= */}
        {activeTab === "final_exam" && (
          <div className="p-6 space-y-6">
            <div className="flex flex-wrap items-center justify-between gap-3 pb-3 border-b border-slate-100">
              <div>
                <div className="flex items-center gap-2">
                  <h3 className="text-base font-bold text-slate-900">Final Certification Exam</h3>
                  <span
                    className={cn(
                      "px-2.5 py-0.5 rounded-full text-xs font-bold",
                      finalTestId ? "bg-emerald-50 text-emerald-700 border border-emerald-200" : "bg-amber-50 text-amber-700 border border-amber-200"
                    )}
                  >
                    {finalTestId ? "Configured & Active" : "Draft / Unlinked"}
                  </span>
                </div>
                <p className="text-xs text-slate-500 mt-0.5">
                  High-stakes proctored exam required for students to graduate and earn their verified certificate.
                </p>
              </div>

              <Button
                variant={isConfiguringExam ? "secondary" : "primary"}
                size="sm"
                onClick={() => setIsConfiguringExam(!isConfiguringExam)}
                className="text-xs font-semibold"
              >
                {isConfiguringExam ? "Close Editor" : finalTestId ? "Edit Settings" : "Setup Final Exam"}
              </Button>
            </div>

            {/* Exam Parameters Form */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <div className="rounded-xl border border-slate-200 p-5 bg-white space-y-4">
                <h4 className="text-xs font-bold text-slate-900 uppercase tracking-wider">Exam Parameters</h4>
                <div className="space-y-3">
                  <div>
                    <label className="block text-xs font-bold text-slate-700 mb-1">Exam Title</label>
                    <input
                      type="text"
                      value={examTitle}
                      onChange={(e) => setExamTitle(e.target.value)}
                      className="w-full rounded-xl border border-slate-300 px-3 py-2 text-xs text-slate-900 focus:outline-none focus:border-[#2563EB]"
                    />
                  </div>
                  <div className="grid grid-cols-3 gap-3">
                    <div>
                      <label className="block text-xs font-bold text-slate-700 mb-1">Duration (Min)</label>
                      <input
                        type="number"
                        min={10}
                        max={300}
                        value={examDurationMinutes}
                        onChange={(e) => setExamDurationMinutes(Number(e.target.value))}
                        className="w-full rounded-xl border border-slate-300 px-3 py-2 text-xs text-slate-900 focus:outline-none focus:border-[#2563EB]"
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
                        className="w-full rounded-xl border border-slate-300 px-3 py-2 text-xs text-slate-900 focus:outline-none focus:border-[#2563EB]"
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
                        className="w-full rounded-xl border border-slate-300 px-3 py-2 text-xs text-slate-900 focus:outline-none focus:border-[#2563EB]"
                      />
                    </div>
                  </div>
                </div>
              </div>

              {/* Proctoring Toggles */}
              <div className="rounded-xl border border-slate-200 p-5 bg-white space-y-4">
                <h4 className="text-xs font-bold text-slate-900 uppercase tracking-wider flex items-center gap-1.5">
                  <ShieldAlert size={14} className="text-blue-600" />
                  <span>Proctoring Security Controls</span>
                </h4>
                <div className="space-y-3">
                  <label className="flex items-center justify-between p-2.5 rounded-lg border border-slate-200 hover:bg-slate-50 cursor-pointer">
                    <div className="flex items-center gap-2.5">
                      <Camera size={16} className="text-slate-600" />
                      <div>
                        <p className="text-xs font-bold text-slate-800">Webcam & AI Face Verification</p>
                        <p className="text-[10.5px] text-slate-500">Continuous face detection and presence checks</p>
                      </div>
                    </div>
                    <input
                      type="checkbox"
                      checked={examCameraRequired}
                      onChange={(e) => setExamCameraRequired(e.target.checked)}
                      className="rounded text-[#2563EB] focus:ring-[#2563EB] h-4 w-4"
                    />
                  </label>

                  <label className="flex items-center justify-between p-2.5 rounded-lg border border-slate-200 hover:bg-slate-50 cursor-pointer">
                    <div className="flex items-center gap-2.5">
                      <Mic size={16} className="text-slate-600" />
                      <div>
                        <p className="text-xs font-bold text-slate-800">Audio & Voice Monitoring</p>
                        <p className="text-[10.5px] text-slate-500">Flags ambient noise and multi-person talking</p>
                      </div>
                    </div>
                    <input
                      type="checkbox"
                      checked={examMicRequired}
                      onChange={(e) => setExamMicRequired(e.target.checked)}
                      className="rounded text-[#2563EB] focus:ring-[#2563EB] h-4 w-4"
                    />
                  </label>

                  <label className="flex items-center justify-between p-2.5 rounded-lg border border-slate-200 hover:bg-slate-50 cursor-pointer">
                    <div className="flex items-center gap-2.5">
                      <Maximize2 size={16} className="text-slate-600" />
                      <div>
                        <p className="text-xs font-bold text-slate-800">Fullscreen Lock Enforcement</p>
                        <p className="text-[10.5px] text-slate-500">Enforces dedicated kiosk-style fullscreen view</p>
                      </div>
                    </div>
                    <input
                      type="checkbox"
                      checked={examFullscreenRequired}
                      onChange={(e) => setExamFullscreenRequired(e.target.checked)}
                      className="rounded text-[#2563EB] focus:ring-[#2563EB] h-4 w-4"
                    />
                  </label>

                  <label className="flex items-center justify-between p-2.5 rounded-lg border border-slate-200 hover:bg-slate-50 cursor-pointer">
                    <div className="flex items-center gap-2.5">
                      <Copy size={16} className="text-slate-600" />
                      <div>
                        <p className="text-xs font-bold text-slate-800">Block Copy / Paste & Tab Switch</p>
                        <p className="text-[10.5px] text-slate-500">Auto-terminates after multiple warnings</p>
                      </div>
                    </div>
                    <input
                      type="checkbox"
                      checked={examCopyPasteBlock}
                      onChange={(e) => setExamCopyPasteBlock(e.target.checked)}
                      className="rounded text-[#2563EB] focus:ring-[#2563EB] h-4 w-4"
                    />
                  </label>
                </div>
              </div>
            </div>

            {/* Questions Pool Manager */}
            <div className="pt-2">
              <AssessmentQuestionManager
                questions={finalCustomQuestions}
                contextTitle={`${course.title} · Final Exam`}
                contextType="final"
                targetQuestionCount={10}
                onSaveQuestion={async (draft: McqDraft & { questionType?: string }) => {
                  const newQ: ManagedQuestionItem = {
                    id: draft.questionId || `q-${Date.now()}`,
                    text: draft.text,
                    questionType: draft.questionType || "mcq_single",
                    marks: draft.marks || 2,
                    options: draft.options,
                    correctAnswer: draft.correct,
                    explanation: draft.explanation,
                  };
                  setFinalCustomQuestions((prev) => [...prev, newQ]);
                  notify.success("Question saved to final exam pool");
                }}
                onDeleteQuestion={async (qId) => {
                  setFinalCustomQuestions((prev) => prev.filter((q) => q.id !== qId));
                  notify.success("Question removed");
                }}
                onImportDrafts={async (drafts: McqDraft[]) => {
                  const imported: ManagedQuestionItem[] = drafts.map((d, i) => ({
                    id: d.questionId || `imp-${Date.now()}-${i}`,
                    text: d.text,
                    questionType: "mcq_single",
                    marks: d.marks || 2,
                    options: d.options,
                    correctAnswer: d.correct,
                    explanation: d.explanation,
                  }));
                  setFinalCustomQuestions((prev) => [...prev, ...imported]);
                  notify.success(`Imported ${imported.length} questions`);
                }}
              />
            </div>

            <div className="flex justify-end pt-4 border-t border-slate-100">
              <Button
                variant="primary"
                onClick={handleSaveFinalExam}
                disabled={isCreatingTest || isUpdatingTest || isSavingRules}
                className="text-xs font-bold px-6 py-2"
              >
                {isCreatingTest || isUpdatingTest || isSavingRules ? "Saving..." : "Save Exam & Proctoring Settings"}
              </Button>
            </div>
          </div>
        )}

        {/* ========================================================================= */}
        {/* TAB 6: CERTIFICATE CONFIGURATION                                         */}
        {/* ========================================================================= */}
        {activeTab === "certificate" && (
          <div className="p-6 space-y-6">
            <div className="pb-3 border-b border-slate-100">
              <h3 className="text-base font-bold text-slate-900">Certificate of Completion</h3>
              <p className="text-xs text-slate-500 mt-0.5">
                Configure issuance criteria, signatory details, and template styling.
              </p>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
              {/* Settings Form */}
              <div className="space-y-5">
                <div className="rounded-xl border border-slate-200 p-5 bg-white space-y-4">
                  <div className="flex items-center justify-between pb-3 border-b border-slate-100">
                    <div>
                      <h4 className="text-xs font-bold text-slate-900 uppercase tracking-wider">Enable Certification</h4>
                      <p className="text-[11px] text-slate-500">Generate verifiable certificate upon course passing</p>
                    </div>
                    <input
                      type="checkbox"
                      checked={certEnabled}
                      onChange={(e) => setCertEnabled(e.target.checked)}
                      className="rounded text-[#2563EB] focus:ring-[#2563EB] h-5 w-5"
                    />
                  </div>

                  <div className="space-y-3 text-xs">
                    <div>
                      <label className="block font-bold text-slate-700 mb-1">Minimum Final Score Required (%)</label>
                      <input
                        type="number"
                        min={50}
                        max={100}
                        value={certMinPassScore}
                        onChange={(e) => setCertMinPassScore(Number(e.target.value))}
                        className="w-full rounded-xl border border-slate-300 px-3 py-2 text-slate-900"
                      />
                    </div>
                    <div>
                      <label className="block font-bold text-slate-700 mb-1">Authorized Signatory Name</label>
                      <input
                        type="text"
                        value={certSignatoryName}
                        onChange={(e) => setCertSignatoryName(e.target.value)}
                        className="w-full rounded-xl border border-slate-300 px-3 py-2 text-slate-900"
                      />
                    </div>
                    <div>
                      <label className="block font-bold text-slate-700 mb-1">Signatory Title</label>
                      <input
                        type="text"
                        value={certSignatoryTitle}
                        onChange={(e) => setCertSignatoryTitle(e.target.value)}
                        className="w-full rounded-xl border border-slate-300 px-3 py-2 text-slate-900"
                      />
                    </div>
                    <div>
                      <label className="block font-bold text-slate-700 mb-1">Issuing Organization</label>
                      <input
                        type="text"
                        value={certOrgName}
                        onChange={(e) => setCertOrgName(e.target.value)}
                        className="w-full rounded-xl border border-slate-300 px-3 py-2 text-slate-900"
                      />
                    </div>
                  </div>
                </div>

                <div className="flex justify-end">
                  <Button
                    variant="primary"
                    size="sm"
                    onClick={() => notify.success("Certificate template & signatory settings saved!")}
                    className="text-xs font-bold"
                  >
                    Save Certificate Settings
                  </Button>
                </div>
              </div>

              {/* Certificate Live Preview */}
              <div className="space-y-3">
                <span className="text-xs font-bold text-slate-700 uppercase tracking-wider block">
                  Live Certificate Preview
                </span>
                <div className="rounded-2xl border-4 border-double border-amber-600/40 bg-gradient-to-b from-amber-50/30 via-white to-amber-50/20 p-8 shadow-md text-center relative overflow-hidden">
                  <div className="absolute top-3 left-3 text-amber-700/20">
                    <Award size={48} />
                  </div>
                  <div className="space-y-4">
                    <p className="text-[10px] font-mono tracking-widest uppercase text-amber-800 font-bold">
                      {certOrgName.toUpperCase()}
                    </p>
                    <h2 className="text-xl font-serif font-bold text-slate-900 tracking-tight">
                      Certificate of Achievement
                    </h2>
                    <p className="text-[11px] text-slate-500 italic">This is proudly presented to</p>
                    <p className="text-lg font-bold text-[#1E3A8A] font-serif border-b border-slate-200 pb-1 inline-block px-8">
                      {user?.full_name || "Student Name"}
                    </p>
                    <p className="text-xs text-slate-600 max-w-sm mx-auto leading-relaxed">
                      For successfully completing all curriculum modules, chapter quizzes, and passing the proctored
                      final exam for
                    </p>
                    <h3 className="text-sm font-bold text-slate-900 font-serif">"{course.title}"</h3>
                    <div className="flex items-center justify-between pt-6 border-t border-slate-200/80 text-[11px] text-slate-600">
                      <div>
                        <p className="font-semibold">{new Date().toLocaleDateString()}</p>
                        <p className="text-[10px] text-slate-400">Date of Issuance</p>
                      </div>
                      <div className="w-12 h-12 rounded bg-slate-100 flex items-center justify-center text-slate-400 border border-slate-200 text-[10px] font-mono">
                        QR Code
                      </div>
                      <div>
                        <p className="font-semibold font-serif italic">{certSignatoryName}</p>
                        <p className="text-[10px] text-slate-400">{certSignatoryTitle}</p>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* ========================================================================= */}
        {/* TAB 7: PRICING & HISTORY (Live Editing & Audit Log)                      */}
        {/* ========================================================================= */}
        {activeTab === "pricing" && (
          <div className="p-6 space-y-6">
            <div className="flex flex-wrap items-center justify-between gap-3 pb-3 border-b border-slate-100">
              <div>
                <h3 className="text-base font-bold text-slate-900">Course Pricing & Price Change History</h3>
                <p className="text-xs text-slate-500 mt-0.5">
                  Manage individual and institutional pricing rates and review the auditable price modification log.
                </p>
              </div>

              <div className="flex items-center gap-2">
                <Button variant="secondary" size="sm" onClick={handleExportAuditsCsv} className="gap-1.5 text-xs">
                  <Download size={13} />
                  <span>Export CSV</span>
                </Button>
                <Button
                  variant="primary"
                  size="sm"
                  onClick={() => setIsEditPricingOpen(true)}
                  className="gap-1.5 text-xs font-semibold"
                >
                  <Edit size={13} />
                  <span>Edit Pricing</span>
                </Button>
              </div>
            </div>

            {/* Current Pricing Summary Cards */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              {/* Individual Student Pricing */}
              <div className="rounded-xl border border-slate-200 p-5 bg-white shadow-2xs space-y-3">
                <div className="flex items-center justify-between">
                  <h4 className="text-xs font-bold text-slate-900 uppercase tracking-wider flex items-center gap-1.5">
                    <DollarSign size={14} className="text-[#2563EB]" />
                    <span>Individual Student Pricing</span>
                  </h4>
                  <span className="text-[10px] font-bold px-2 py-0.5 rounded bg-blue-50 text-[#2563EB]">
                    B2C / Direct
                  </span>
                </div>
                <div className="space-y-2 text-xs">
                  <div className="flex justify-between py-1 border-b border-slate-100">
                    <span className="text-slate-500">Base Catalog Price</span>
                    <span className="font-semibold text-slate-900">
                      ₹{((currentPricing?.individual_price_paise || 199900) / 100).toLocaleString("en-IN")}
                    </span>
                  </div>
                  <div className="flex justify-between py-1 border-b border-slate-100">
                    <span className="text-slate-500">Active Discount</span>
                    <span className="font-semibold text-emerald-600">
                      {currentPricing?.discount_percent || 0}% Off
                    </span>
                  </div>
                  <div className="flex justify-between py-1 border-b border-slate-100">
                    <span className="text-slate-500">GST Rate</span>
                    <span className="font-semibold text-slate-700">18% (Applicable at checkout)</span>
                  </div>
                  <div className="flex justify-between py-1.5 pt-2">
                    <span className="font-bold text-slate-900">Final Student Price</span>
                    <span className="text-base font-bold text-[#2563EB]">
                      ₹
                      {(
                        ((currentPricing?.individual_price_paise || 199900) / 100) *
                        (1 - (currentPricing?.discount_percent || 0) / 100)
                      ).toFixed(2)}
                    </span>
                  </div>
                </div>
              </div>

              {/* Institutional Pricing */}
              <div className="rounded-xl border border-slate-200 p-5 bg-white shadow-2xs space-y-3">
                <div className="flex items-center justify-between">
                  <h4 className="text-xs font-bold text-slate-900 uppercase tracking-wider flex items-center gap-1.5">
                    <Users size={14} className="text-purple-600" />
                    <span>Institutional Purchase Pricing</span>
                  </h4>
                  <span className="text-[10px] font-bold px-2 py-0.5 rounded bg-purple-50 text-purple-700">
                    B2B / Colleges
                  </span>
                </div>
                <div className="space-y-2 text-xs">
                  <div className="flex justify-between py-1 border-b border-slate-100">
                    <span className="text-slate-500">Per Student Seat Rate</span>
                    <span className="font-semibold text-slate-900">
                      ₹
                      {(
                        (currentPricing?.fixed_price_paise ||
                          currentPricing?.institutional_price_per_seat_paise ||
                          99900) /
                        100
                      ).toLocaleString("en-IN")}
                    </span>
                  </div>
                  <div className="flex justify-between py-1 border-b border-slate-100">
                    <span className="text-slate-500">Minimum Seat Requirement</span>
                    <span className="font-semibold text-slate-900">{currentPricing?.min_students || 10} Seats</span>
                  </div>
                  <div className="flex justify-between py-1 border-b border-slate-100">
                    <span className="text-slate-500">Maximum Seat Limit</span>
                    <span className="font-semibold text-slate-900">{currentPricing?.max_students || 1000} Seats</span>
                  </div>
                  <div className="flex justify-between py-1.5 pt-2">
                    <span className="font-bold text-slate-900">Sample 100-Seat Package</span>
                    <span className="text-base font-bold text-purple-700">
                      ₹
                      {(
                        ((currentPricing?.fixed_price_paise ||
                          currentPricing?.institutional_price_per_seat_paise ||
                          99900) /
                          100) *
                        100
                      ).toLocaleString("en-IN")}
                    </span>
                  </div>
                </div>
              </div>
            </div>

            {/* Price Change Audit Log Table */}
            <div className="space-y-3">
              <h4 className="text-xs font-bold text-slate-900 uppercase tracking-wider">
                Audit History ({pricingAudits.length} Records)
              </h4>
              <div className="rounded-xl border border-slate-200 overflow-hidden shadow-2xs">
                <table className="w-full text-left text-xs">
                  <thead className="bg-slate-50 text-slate-500 font-semibold border-b border-slate-200">
                    <tr>
                      <th className="py-2.5 px-3">Date & Time</th>
                      <th className="py-2.5 px-3">Prev Indiv → New Indiv</th>
                      <th className="py-2.5 px-3">Prev Inst → New Inst</th>
                      <th className="py-2.5 px-3">Changed By</th>
                      <th className="py-2.5 px-3">Reason</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100 bg-white">
                    {pricingAudits.length === 0 ? (
                      <tr>
                        <td colSpan={5} className="py-8 text-center text-slate-400">
                          No price changes recorded yet. Click "Edit Pricing" above to set or modify prices.
                        </td>
                      </tr>
                    ) : (
                      pricingAudits.map((audit) => (
                        <tr key={audit.id} className="hover:bg-slate-50/70">
                          <td className="py-2.5 px-3 font-mono text-[11px] text-slate-500">
                            {new Date(audit.created_at || Date.now()).toLocaleString()}
                          </td>
                          <td className="py-2.5 px-3 font-semibold text-slate-800">
                            ₹{(audit.previous_individual_price_paise / 100).toFixed(0)} →{" "}
                            <span className="text-[#2563EB]">
                              ₹{(audit.new_individual_price_paise / 100).toFixed(0)}
                            </span>
                          </td>
                          <td className="py-2.5 px-3 font-semibold text-slate-800">
                            ₹{(audit.previous_institutional_price_paise / 100).toFixed(0)} →{" "}
                            <span className="text-purple-700">
                              ₹{(audit.new_institutional_price_paise / 100).toFixed(0)}
                            </span>
                          </td>
                          <td className="py-2.5 px-3 text-slate-600 font-medium">
                            {audit.admin_email || audit.admin_name || `Admin #${audit.admin_user_id}`}
                          </td>
                          <td className="py-2.5 px-3 text-slate-700 max-w-xs truncate">
                            {audit.reason || "Price adjustment"}
                          </td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        )}

        {/* ========================================================================= */}
        {/* TAB 8: PREVIEW & PUBLISH                                                 */}
        {/* ========================================================================= */}
        {activeTab === "preview" && (
          <div className="p-6 space-y-6">
            <div className="pb-3 border-b border-slate-100">
              <h3 className="text-base font-bold text-slate-900">Publication Readiness & Student Preview</h3>
              <p className="text-xs text-slate-500 mt-0.5">
                Verify that your course satisfies all readiness criteria before publishing to students and institutions.
              </p>
            </div>

            {/* Readiness Checklist */}
            <div className="rounded-xl border border-slate-200 p-5 bg-white space-y-4">
              <h4 className="text-xs font-bold text-slate-900 uppercase tracking-wider">Readiness Checklist</h4>
              <div className="space-y-3">
                <div className="flex items-center justify-between p-3 rounded-lg border border-slate-100 bg-slate-50/50">
                  <div className="flex items-center gap-3">
                    <CheckCircle2 size={18} className="text-emerald-600" />
                    <div>
                      <p className="text-xs font-bold text-slate-800">Basic Information & Metadata</p>
                      <p className="text-[11px] text-slate-500">Title, description, slug, and category are configured</p>
                    </div>
                  </div>
                  <span className="text-[11px] font-bold text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded">
                    Complete
                  </span>
                </div>

                <div className="flex items-center justify-between p-3 rounded-lg border border-slate-100 bg-slate-50/50">
                  <div className="flex items-center gap-3">
                    {readiness.hasCurriculum ? (
                      <CheckCircle2 size={18} className="text-emerald-600" />
                    ) : (
                      <AlertCircle size={18} className="text-amber-500" />
                    )}
                    <div>
                      <p className="text-xs font-bold text-slate-800">Curriculum Content</p>
                      <p className="text-[11px] text-slate-500">
                        {modules.length} modules, {totalChapters} chapters configured
                      </p>
                    </div>
                  </div>
                  <span
                    className={cn(
                      "text-[11px] font-bold px-2 py-0.5 rounded",
                      readiness.hasCurriculum ? "text-emerald-700 bg-emerald-50" : "text-amber-700 bg-amber-50"
                    )}
                  >
                    {readiness.hasCurriculum ? "Complete" : "Needs Content"}
                  </span>
                </div>

                <div className="flex items-center justify-between p-3 rounded-lg border border-slate-100 bg-slate-50/50">
                  <div className="flex items-center gap-3">
                    {readiness.hasAssessments ? (
                      <CheckCircle2 size={18} className="text-emerald-600" />
                    ) : (
                      <AlertCircle size={18} className="text-amber-500" />
                    )}
                    <div>
                      <p className="text-xs font-bold text-slate-800">Assessments & Final Exam</p>
                      <p className="text-[11px] text-slate-500">
                        {finalTestId ? "Proctored Final Exam active" : "Default passing standards applied"}
                      </p>
                    </div>
                  </div>
                  <span className="text-[11px] font-bold text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded">
                    Configured
                  </span>
                </div>

                <div className="flex items-center justify-between p-3 rounded-lg border border-slate-100 bg-slate-50/50">
                  <div className="flex items-center gap-3">
                    <CheckCircle2 size={18} className="text-emerald-600" />
                    <div>
                      <p className="text-xs font-bold text-slate-800">Pricing Configuration</p>
                      <p className="text-[11px] text-slate-500">Individual B2C and institutional seat pricing set</p>
                    </div>
                  </div>
                  <span className="text-[11px] font-bold text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded">
                    Configured
                  </span>
                </div>
              </div>
            </div>

            {/* Launch Actions */}
            <div className="rounded-xl border border-slate-200 p-6 bg-gradient-to-r from-slate-50 via-white to-blue-50/30 flex flex-wrap items-center justify-between gap-4">
              <div>
                <h4 className="text-sm font-bold text-slate-900">
                  {isPublished ? "Course is Live & Enrolling" : "Ready to Publish Course?"}
                </h4>
                <p className="text-xs text-slate-500 mt-0.5">
                  {isPublished
                    ? "Students can purchase this course, access video lectures, take quizzes and complete tests."
                    : "Once published, this course will immediately appear in the catalog and institutional store."}
                </p>
              </div>

              <div className="flex items-center gap-3">
                <Button
                  variant="secondary"
                  onClick={() => navigate(`/courses/${courseId}/learn`)}
                  className="gap-1.5 text-xs font-semibold"
                >
                  <ExternalLink size={14} />
                  <span>Student View Preview</span>
                </Button>
                <Button
                  variant={isPublished ? "secondary" : "primary"}
                  onClick={handleTogglePublish}
                  className="text-xs font-bold px-5"
                >
                  {isPublished ? "Unpublish Course" : "Publish Course Now"}
                </Button>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* ========================================================================= */}
      {/* MODAL: EDIT PRICING                                                      */}
      {/* ========================================================================= */}
      {isEditPricingOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-navy-950/40 backdrop-blur-xs">
          <div className="w-full max-w-lg rounded-2xl bg-white border border-slate-200 shadow-xl overflow-hidden animate-in fade-in zoom-in-95">
            <div className="flex items-center justify-between p-5 border-b border-slate-100 bg-slate-50/70">
              <div>
                <h3 className="text-sm font-bold text-slate-900">Edit Course Pricing</h3>
                <p className="text-[11px] text-slate-500">Modifications are logged to the permanent audit trail.</p>
              </div>
              <button
                type="button"
                onClick={() => setIsEditPricingOpen(false)}
                className="text-slate-400 hover:text-slate-700 p-1"
              >
                ✕
              </button>
            </div>

            <form onSubmit={handleSavePricing} className="p-5 space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-bold text-slate-700 mb-1">Individual Price (₹) *</label>
                  <input
                    type="number"
                    min={0}
                    step={1}
                    required
                    value={priceForm.individualPrice}
                    onChange={(e) => setPriceForm({ ...priceForm, individualPrice: Number(e.target.value) })}
                    className="w-full rounded-xl border border-slate-300 px-3 py-2 text-xs text-slate-900 focus:outline-none focus:border-[#2563EB]"
                  />
                </div>
                <div>
                  <label className="block text-xs font-bold text-slate-700 mb-1">Discount (%)</label>
                  <input
                    type="number"
                    min={0}
                    max={100}
                    value={priceForm.discountPercent}
                    onChange={(e) => setPriceForm({ ...priceForm, discountPercent: Number(e.target.value) })}
                    className="w-full rounded-xl border border-slate-300 px-3 py-2 text-xs text-slate-900 focus:outline-none focus:border-[#2563EB]"
                  />
                </div>
              </div>

              <div className="grid grid-cols-3 gap-3">
                <div>
                  <label className="block text-xs font-bold text-slate-700 mb-1">Inst. Price/Seat (₹) *</label>
                  <input
                    type="number"
                    min={0}
                    step={1}
                    required
                    value={priceForm.institutionalPrice}
                    onChange={(e) => setPriceForm({ ...priceForm, institutionalPrice: Number(e.target.value) })}
                    className="w-full rounded-xl border border-slate-300 px-3 py-2 text-xs text-slate-900 focus:outline-none focus:border-[#2563EB]"
                  />
                </div>
                <div>
                  <label className="block text-xs font-bold text-slate-700 mb-1">Min Seats</label>
                  <input
                    type="number"
                    min={1}
                    value={priceForm.minSeats}
                    onChange={(e) => setPriceForm({ ...priceForm, minSeats: Number(e.target.value) })}
                    className="w-full rounded-xl border border-slate-300 px-3 py-2 text-xs text-slate-900 focus:outline-none focus:border-[#2563EB]"
                  />
                </div>
                <div>
                  <label className="block text-xs font-bold text-slate-700 mb-1">Max Seats</label>
                  <input
                    type="number"
                    min={priceForm.minSeats}
                    value={priceForm.maxSeats}
                    onChange={(e) => setPriceForm({ ...priceForm, maxSeats: Number(e.target.value) })}
                    className="w-full rounded-xl border border-slate-300 px-3 py-2 text-xs text-slate-900 focus:outline-none focus:border-[#2563EB]"
                  />
                </div>
              </div>

              <div>
                <label className="block text-xs font-bold text-slate-700 mb-1">
                  Reason for Price Change * <span className="text-[10px] text-rose-500 font-normal">(Mandatory)</span>
                </label>
                <textarea
                  required
                  rows={2}
                  placeholder="e.g. Q4 promotional pricing or revised institutional seat tier"
                  value={priceForm.reason}
                  onChange={(e) => setPriceForm({ ...priceForm, reason: e.target.value })}
                  className="w-full rounded-xl border border-slate-300 p-2.5 text-xs text-slate-900 focus:outline-none focus:border-[#2563EB]"
                />
              </div>

              <div className="flex justify-end gap-2 pt-3 border-t border-slate-100">
                <Button variant="secondary" size="sm" type="button" onClick={() => setIsEditPricingOpen(false)}>
                  Cancel
                </Button>
                <Button variant="primary" size="sm" type="submit" disabled={isUpdatingPricing}>
                  {isUpdatingPricing ? "Saving..." : "Save Price Changes"}
                </Button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* ========================================================================= */}
      {/* MODALS: ADD/EDIT MODULE, DELETE MODULE, MODULE TEST SETUP                */}
      {/* ========================================================================= */}
      {isAddModuleOpen && (
        <AddModuleModal
          isOpen={isAddModuleOpen}
          initialData={editingModule ? { title: editingModule.title, description: editingModule.description || "", position: editingModule.position || 1 } : undefined}
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

      {managingModuleTest && versionId && (
        <ModuleTestSetupModal
          isOpen={Boolean(managingModuleTest)}
          courseId={courseId ?? ""}
          versionId={versionId}
          module={managingModuleTest}
          onClose={() => setManagingModuleTest(null)}
          onSaved={() => {
            setManagingModuleTest(null);
            refetchVersion();
          }}
        />
      )}

      {addingChapterToModule && versionId && (
        <AddChapterModal
          isOpen={Boolean(addingChapterToModule)}
          moduleTitle={addingChapterToModule.title}
          courseId={courseId}
          moduleId={addingChapterToModule.module_id}
          defaultPosition={(addingChapterToModule.topics?.length ?? 0) + 1}
          onClose={() => setAddingChapterToModule(null)}
          onSubmit={handleSaveChapterInHub}
        />
      )}

      {managingChapterTest && versionId && (
        <ChapterTestSetupModal
          isOpen={Boolean(managingChapterTest)}
          chapter={managingChapterTest.chapter}
          moduleTitle={managingChapterTest.moduleTitle}
          courseId={courseId ?? ""}
          versionId={versionId}
          moduleId={managingChapterTest.moduleId}
          onClose={() => setManagingChapterTest(null)}
          onSaved={() => {
            setManagingChapterTest(null);
            refetchVersion();
          }}
        />
      )}

      {/* Media Previews */}
      {videoPreviewTarget && (
        <AdminVideoPreviewModal
          isOpen={Boolean(videoPreviewTarget)}
          chapterTitle={videoPreviewTarget.chapterTitle}
          itemTitle={videoPreviewTarget.itemTitle}
          mediaId={videoPreviewTarget.mediaId}
          onClose={() => setVideoPreviewTarget(null)}
        />
      )}

      {pdfPreviewTarget && (
        <AdminPdfPreviewModal
          isOpen={Boolean(pdfPreviewTarget)}
          chapterTitle={pdfPreviewTarget.chapterTitle}
          itemTitle={pdfPreviewTarget.itemTitle}
          mediaId={pdfPreviewTarget.mediaId}
          onClose={() => setPdfPreviewTarget(null)}
        />
      )}
    </div>
  );
}
