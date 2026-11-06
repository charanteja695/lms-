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
  useReorderModulesMutation,
} from "@/modules/catalog/courses/api/curriculumApi";
import {
  useListQuestionsQuery,
  useCreateQuestionMutation,
  useUpdateQuestionMutation,
  useSubmitQuestionMutation,
  useApproveQuestionMutation,
} from "@/modules/assessments/questions/api/questionsApi";
import {
  useCreateTestMutation,
  useUpdateTestMutation,
  useReplaceSectionsMutation,
  useSubmitTestMutation,
  useApproveTestMutation,
  useGetTestQuery,
} from "@/modules/assessments/tests/api/testsApi";
import { ModuleTestSetupModal } from "@/modules/catalog/courses/components/modals/ModuleTestSetupModal";
import {
  AssessmentQuestionManager,
  type ManagedQuestionItem,
} from "@/modules/catalog/course-tests/components/AssessmentQuestionManager";
import type { McqDraft } from "@/modules/catalog/course-tests/hooks/useTestQuestions";
import { SetupProgress, type SetupStep } from "@/modules/catalog/courses/components/common/SetupProgress";
import { CourseCreationStepper, type StepperStepItem } from "@/modules/catalog/courses/components/common/CourseCreationStepper";
import { CoursePageHeader } from "@/modules/catalog/courses/components/common/CoursePageHeader";
import { AddModuleModal } from "@/modules/catalog/courses/components/modals/AddModuleModal";
import { ConfirmModal } from "@/modules/catalog/courses/components/common/ConfirmModal";
import { Button, Icon, PageLoader } from "@/shared/ui";
import { usePermissions } from "@/modules/user-management/common/permissions/usePermissions";
import { useListEnrollmentsQuery } from "@/modules/learning/enrollments/api/enrollmentsApi";
import { useListBatchesQuery } from "@/modules/learning/batches/api/batchesApi";
import { useNotify } from "@/core/hooks/useNotify";
import { parseCourseSummary, computeCourseStepsStatus } from "@/modules/catalog/courses/utils/courseMetrics";
import { cn } from "@/core/lib/cn";
import type { ModuleDetail } from "@/modules/catalog/courses/curriculumTypes";

type HubTab = "modules" | "overview" | "final_exam" | "students";

export function CourseHubPage() {
  const { permissions } = usePermissions();
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

  const tabParam = (searchParams.get("tab") as HubTab) || "modules";
  const stepParam = searchParams.get("step");

  const [activeTab, setActiveTab] = useState<HubTab>(tabParam);
  const [isAddModuleOpen, setIsAddModuleOpen] = useState(false);
  const [editingModule, setEditingModule] = useState<ModuleDetail | null>(null);
  const [deletingModule, setDeletingModule] = useState<ModuleDetail | null>(null);

  // Sync tab with URL
  useEffect(() => {
    if (tabParam && tabParam !== activeTab) {
      setActiveTab(tabParam);
    }
  }, [tabParam]);

  const handleSelectTab = (tab: HubTab) => {
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
  const [publishCourse] = usePublishCourseMutation();
  const [unpublishCourse] = useUnpublishCourseMutation();
  const [reorderModules] = useReorderModulesMutation();
  const [updateRules, { isLoading: isSavingRules }] = useUpdateRulesMutation();

  // Test Authoring mutations for Final Exam
  const [createTest, { isLoading: isCreatingTest }] = useCreateTestMutation();
  const [updateTest, { isLoading: isUpdatingTest }] = useUpdateTestMutation();
  const [submitTest] = useSubmitTestMutation();
  const [approveTest] = useApproveTestMutation();

  // Load real batches & enrollments for exact enrolled students count
  const { data: batchesData } = useListBatchesQuery({ per_page: 100 });
  const { data: enrollmentsData } = useListEnrollmentsQuery({ status: "active", per_page: 100 });

  const enrolledStudents = useMemo(() => {
    if (!courseId) return [];
    const courseBatches = (batchesData?.items ?? []).filter((b) => b.course_id === courseId);
    const courseBatchIds = new Set(courseBatches.map((b) => b.batch_id));
    return (enrollmentsData?.items ?? []).filter((e) => courseBatchIds.has(e.batch_id));
  }, [courseId, batchesData?.items, enrollmentsData?.items]);

  // Load questions bank to verify approved questions for Step 4 & Final Exam picker
  const { data: questionsData } = useListQuestionsQuery({
    per_page: 100,
  });

  const allApprovedQuestions = useMemo(() => {
    const items = questionsData?.items ?? [];
    return items.filter((q) => q.status === "active");
  }, [questionsData]);

  // Questions matching this course or general
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

  const hasApprovedQuestions = courseApprovedQuestions.length > 0;

  // Final Test detail if already configured
  const finalTestId = versionDetail?.rule?.final_test_id;
  const { data: finalTestDetail, refetch: refetchFinalTest } = useGetTestQuery(finalTestId ?? "", {
    skip: !finalTestId,
  });

  // Final Exam Config State
  const [isConfiguringExam, setIsConfiguringExam] = useState(false);
  const [examTitle, setExamTitle] = useState("");
  const [examDurationMinutes, setExamDurationMinutes] = useState(60);
  const [examPassMark, setExamPassMark] = useState(70);
  const [examAttempts, setExamAttempts] = useState(3);
  const [examCooldownDays, setExamCooldownDays] = useState(1);
  const [examMaxWarnings, setExamMaxWarnings] = useState(3);
  const [examCameraRequired, setExamCameraRequired] = useState(true);
  const [examShuffle, setExamShuffle] = useState(true);
  const [questionPickMode] = useState<"random" | "specific">("random");
  const [examQuestionCount, setExamQuestionCount] = useState(1);
  const [selectedQuestionIds, setSelectedQuestionIds] = useState<string[]>([]);
  const [isRemoveExamModalOpen, setIsRemoveExamModalOpen] = useState(false);

  // Sync Final Exam form values from existing config
  useEffect(() => {
    if (finalTestDetail) {
      setExamTitle(finalTestDetail.title || "");
      setExamDurationMinutes(finalTestDetail.duration_minutes || 60);
      setExamPassMark(finalTestDetail.pass_mark_percent || versionDetail?.rule?.final_pass_mark || 70);
      setExamAttempts(finalTestDetail.max_attempts || versionDetail?.rule?.final_test_attempts || 3);
      setExamCooldownDays(versionDetail?.rule?.final_test_cooldown_days || 1);
      setExamCameraRequired(finalTestDetail.proctoring_level === "strict" || finalTestDetail.proctoring_level === "basic");
      setExamShuffle(Boolean(finalTestDetail.shuffle_questions));
      const testQIds = (finalTestDetail as any).question_ids || [];
      if (testQIds.length > 0) {
        setSelectedQuestionIds(testQIds);
        setExamQuestionCount(testQIds.length);
      }
    } else if (course) {
      setExamTitle(`${course.title} - Final Certification Exam`);
      setExamPassMark(versionDetail?.rule?.final_pass_mark || 70);
      setExamAttempts(versionDetail?.rule?.final_test_attempts || 3);
      setExamCooldownDays(versionDetail?.rule?.final_test_cooldown_days || 1);
      const defaultCount = Math.min(10, Math.max(1, courseApprovedQuestions.length));
      setExamQuestionCount(defaultCount);
    }
  }, [finalTestDetail, course, versionDetail?.rule, courseApprovedQuestions.length]);

  const [managingModuleTest, setManagingModuleTest] = useState<ModuleDetail | null>(null);
  const [finalCustomQuestions, setFinalCustomQuestions] = useState<ManagedQuestionItem[]>([]);
  const [isFinalQuestionsLoaded, setIsFinalQuestionsLoaded] = useState(false);

  const [createQuestion] = useCreateQuestionMutation();
  const [updateQuestion] = useUpdateQuestionMutation();
  const [submitQuestion] = useSubmitQuestionMutation();
  const [approveQuestion] = useApproveQuestionMutation();
  const [replaceSections] = useReplaceSectionsMutation();

  // Load and sync final exam questions
  useEffect(() => {
    if (isFinalQuestionsLoaded || !courseId) return;

    let loaded: ManagedQuestionItem[] = [];
    // 1. Primary: Load directly from final test definition slots in backend
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

    // 2. Fallback: LocalStorage
    if (loaded.length === 0) {
      try {
        const saved = localStorage.getItem(`final_exam_questions_${courseId}`);
        if (saved) {
          const parsed = JSON.parse(saved);
          if (Array.isArray(parsed) && parsed.length > 0) {
            loaded = parsed;
          }
        }
      } catch {}
    }

    // 3. Fallback: course approved questions
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

    if (loaded.length > 0 || !isFinalQuestionsLoaded) {
      setFinalCustomQuestions(loaded);
      setIsFinalQuestionsLoaded(true);
    }
  }, [courseId, isFinalQuestionsLoaded, courseApprovedQuestions, finalTestDetail]);

  const persistFinalQuestions = (newQuestions: ManagedQuestionItem[]) => {
    setFinalCustomQuestions(newQuestions);
    if (courseId) {
      try {
        localStorage.setItem(`final_exam_questions_${courseId}`, JSON.stringify(newQuestions));
      } catch {}
    }
  };

  const handleSaveFinalQuestion = async (draft: McqDraft & { questionType?: string }) => {
    const newItem: ManagedQuestionItem = {
      id: draft.questionId || `final-q-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`,
      text: draft.text,
      questionType: draft.questionType || "mcq_single",
      marks: draft.marks,
      options: draft.options,
      correctAnswer: draft.correct,
      explanation: draft.explanation,
    };

    if (draft.questionId) {
      persistFinalQuestions(
        finalCustomQuestions.map((q) => (q.id === draft.questionId ? newItem : q))
      );
      notify.success("Question updated in Final Exam");
    } else {
      persistFinalQuestions([...finalCustomQuestions, newItem]);
      notify.success("Question added to Final Exam");
    }
  };

  const handleDeleteFinalQuestion = async (questionId?: string, index?: number) => {
    let nextList: ManagedQuestionItem[];
    if (questionId) {
      nextList = finalCustomQuestions.filter((q) => q.id !== questionId);
    } else if (index !== undefined) {
      nextList = finalCustomQuestions.filter((_, idx) => idx !== index);
    } else {
      return;
    }
    persistFinalQuestions(nextList);
    notify.success("Question removed from Final Exam");
  };

  const handleImportFinalDrafts = async (
    drafts: McqDraft[],
    _onProgress: (completed: number, total: number) => void
  ) => {
    const importedItems: ManagedQuestionItem[] = drafts.map((draft, i) => ({
      id: `final-imported-${Date.now()}-${i}`,
      text: draft.text,
      questionType: "mcq_single",
      marks: draft.marks,
      options: draft.options,
      correctAnswer: draft.correct,
      explanation: draft.explanation,
    }));

    persistFinalQuestions([...finalCustomQuestions, ...importedItems]);
    notify.success(`Successfully imported ${drafts.length} questions into Final Exam!`);
  };

  const [draggedModuleIndex, setDraggedModuleIndex] = useState<number | null>(null);

  const modules = useMemo(() => {
    return [...(versionDetail?.modules ?? [])].sort((a, b) => a.position - b.position);
  }, [versionDetail?.modules]);

  const totalChapters = useMemo(() => {
    return modules.reduce((acc, m) => acc + (m.topics?.length ?? 0), 0);
  }, [modules]);

  const parsedSummary = useMemo(() => {
    return parseCourseSummary(course?.summary);
  }, [course?.summary]);

  const isPublished = course?.versions?.some((v) => v.status === "published") && !course.archived_at;

  // Step Completion Status
  const stepsStatus = useMemo(() => {
    return computeCourseStepsStatus(course, versionDetail, hasApprovedQuestions);
  }, [course, versionDetail, hasApprovedQuestions]);

  // Setup Progress Steps
  const setupSteps: SetupStep[] = useMemo(() => {
    return [
      {
        id: 1,
        label: "Course details",
        sublabel: stepsStatus.step1Done ? "Done" : "In progress",
        status: stepsStatus.step1Done ? "done" : "current",
        onClick: () => navigate(`/courses/${courseId}/edit?step=1&from=hub`),
      },
      {
        id: 2,
        label: "Modules",
        sublabel: modules.length > 0 ? `${modules.length} added` : "0 added",
        status: stepsStatus.step2Done ? "done" : stepsStatus.step1Done ? "current" : "pending",
        onClick: () => {
          handleSelectTab("modules");
          if (modules.length === 0) setIsAddModuleOpen(true);
        },
      },
      {
        id: 3,
        label: "Chapters",
        sublabel: totalChapters > 0 ? `${totalChapters} added` : "0 added",
        status: stepsStatus.step3Done ? "done" : stepsStatus.step2Done ? "current" : "pending",
        onClick: () => {
          if (modules.length > 0 && modules[0]) {
            navigate(`/courses/${courseId}/modules/${modules[0].module_id}/chapters?step=3`);
          } else {
            handleSelectTab("modules");
            setIsAddModuleOpen(true);
          }
        },
      },
      {
        id: 4,
        label: "Approve questions",
        sublabel: stepsStatus.step4Done
          ? `${courseApprovedQuestions.length} approved`
          : totalChapters > 0
          ? "Ready to review"
          : "Waiting for chapters",
        status: stepsStatus.step4Done ? "done" : stepsStatus.step3Done ? "current" : "pending",
        onClick: () => navigate(`/courses/${courseId}/questions/review?step=4`),
      },
      {
        id: 5,
        label: "Final exam",
        sublabel: stepsStatus.step5Done
          ? `Configured (${finalTestDetail?.duration_minutes || 60}m)`
          : "Not set",
        status: stepsStatus.step5Done ? "done" : stepsStatus.step4Done ? "current" : "pending",
        onClick: () => {
          handleSelectTab("final_exam");
          setIsConfiguringExam(true);
        },
      },
    ];
  }, [
    stepsStatus,
    modules,
    totalChapters,
    courseApprovedQuestions.length,
    courseId,
    navigate,
    finalTestDetail?.duration_minutes,
  ]);

  const stepperSteps: StepperStepItem[] = useMemo(() => {
    return setupSteps.map((s) => ({
      id: s.id,
      label: s.label,
      sublabel: s.sublabel,
      status: s.status,
      path: undefined,
    }));
  }, [setupSteps]);

  // Handler for drop reordering modules
  const handleDropModule = async (dropIndex: number) => {
    if (draggedModuleIndex === null || draggedModuleIndex === dropIndex) return;
    const reordered = [...modules];
    const [moved] = reordered.splice(draggedModuleIndex, 1);
    if (!moved) return;
    reordered.splice(dropIndex, 0, moved);
    setDraggedModuleIndex(null);

    if (courseId && versionId) {
      try {
        await reorderModules({
          courseId,
          versionId,
          orderedIds: reordered.map((m) => m.module_id),
        }).unwrap();
        notify.success("Module order saved");
      } catch (err: any) {
        notify.apiError(err);
      }
    }
  };

  // Handler for saving Final Exam
  const handleSaveFinalExam = async (e?: React.FormEvent | React.MouseEvent) => {
    if (e) e.preventDefault();
    if (!courseId || !versionId) return;

    // Determine available questions: either custom Final Exam questions or course approved questions
    const hasCustom = finalCustomQuestions.length > 0;
    const hasChapterQuestions = courseApprovedQuestions.length > 0;

    if (!hasCustom && !hasChapterQuestions) {
      notify.error(
        "No questions found for the final exam. Please add questions manually, import questions, or approve chapter questions."
      );
      return;
    }

    const availableCount = hasCustom ? finalCustomQuestions.length : courseApprovedQuestions.length;
    if (!hasCustom && examQuestionCount && availableCount < examQuestionCount) {
      notify.error(
        `Final exam is configured for ${examQuestionCount} questions, but only ${availableCount} question(s) are currently available. Please add more questions or adjust the question count.`
      );
      return;
    }

    try {
      let chosenIds: string[] = [];

      if (hasCustom) {
        // Create any draft questions in question bank
        for (const q of finalCustomQuestions) {
          if (q.id && !q.id.startsWith("final-") && !q.id.startsWith("draft-")) {
            try {
              await updateQuestion({
                questionId: q.id,
                body: {
                  text: q.text,
                  body: { options: q.options || [] },
                  answer_key: { correct: q.correctAnswer || "a" },
                  explanation: q.explanation || null,
                  default_marks: q.marks,
                },
              }).unwrap();
            } catch (uErr) {
              console.warn("Could not update question in bank:", uErr);
            }
            chosenIds.push(q.id);
          } else {
            try {
              const created = await createQuestion({
                question_type: "mcq_single",
                text: q.text,
                body: { options: q.options || [] },
                answer_key: { correct: q.correctAnswer || "a" },
                explanation: q.explanation || null,
                default_marks: q.marks,
                topics: [course?.slug || "final-exam"],
              }).unwrap();

              try {
                await submitQuestion(created.question_id).unwrap();
                await approveQuestion({ questionId: created.question_id }).unwrap();
              } catch {
                // Ignore if already submitted
              }
              chosenIds.push(created.question_id);
            } catch (err) {
              console.warn("Could not create custom question in bank:", err);
            }
          }
        }
      } else if (questionPickMode === "specific" && selectedQuestionIds.length > 0) {
        chosenIds = selectedQuestionIds;
      } else {
        // Random pick from chapter questions
        const count = Math.min(examQuestionCount, courseApprovedQuestions.length);
        const shuffled = [...courseApprovedQuestions].sort(() => 0.5 - Math.random());
        chosenIds = shuffled.slice(0, count).map((q) => q.question_id);
      }

      if (chosenIds.length === 0) {
        notify.error("Please add or select at least 1 question for the final exam.");
        return;
      }

      const slots = chosenIds.map((qid) => ({
        slot_type: "fixed" as const,
        question_id: qid,
        count: 1,
      }));

      let testPublicId = finalTestId;

      if (testPublicId) {
        // Update existing test
        await updateTest({
          testId: testPublicId,
          body: {
            title: examTitle.trim() || `${course?.title || "Course"} - Final Exam`,
            duration_minutes: Number(examDurationMinutes) || 60,
            pass_mark_percent: Number(examPassMark) || 70,
            max_attempts: Number(examAttempts) || 3,
            shuffle_questions: examShuffle,
            proctoring_level: examCameraRequired ? "strict" : "none",
          },
        }).unwrap();

        // Update paper sections with latest questions
        if (slots.length > 0) {
          await replaceSections({
            testId: testPublicId,
            sections: [
              {
                title: "Comprehensive Final Assessment",
                slots,
              },
            ],
          }).unwrap();
        }
      } else {
        // Create new test
        const created = await createTest({
          title: examTitle.trim() || `${course?.title || "Course"} - Final Exam`,
          kind: "final" as const,
          target_id: courseId,
          duration_minutes: Number(examDurationMinutes) || 60,
          pass_mark_percent: Number(examPassMark) || 70,
          max_attempts: Number(examAttempts) || 3,
          shuffle_questions: examShuffle,
          proctoring_level: examCameraRequired ? "strict" : "none",
          sections: [
            {
              title: "Comprehensive Final Assessment",
              slots,
            },
          ],
        }).unwrap();

        testPublicId = created.test_id;

        // Submit and approve test so students can take it immediately
        if (testPublicId) {
          try {
            await submitTest(testPublicId).unwrap();
            await approveTest({ testId: testPublicId }).unwrap();
          } catch {
            // If already submitted/approved, ignore
          }
        }
      }

      // Link to course version rules
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

      notify.success("Final exam configured and linked successfully!");
      setIsConfiguringExam(false);
      refetchVersion();
      if (testPublicId) refetchFinalTest();
    } catch (err: any) {
      notify.apiError(err);
    }
  };

  // Handler for removing Final Exam configuration
  const handleRemoveFinalExam = async () => {
    if (!courseId || !versionId) return;
    try {
      await updateRules({
        courseId,
        versionId,
        body: {
          final_test_id: undefined,
          final_pass_mark: 70,
          final_test_attempts: 3,
          final_test_cooldown_days: 1,
        },
      }).unwrap();
      notify.success("Final exam configuration removed.");
      setIsRemoveExamModalOpen(false);
      setIsConfiguringExam(false);
      refetchVersion();
    } catch (err: any) {
      notify.apiError(err);
    }
  };

  if (isCourseLoading || (versionId && isVersionLoading)) {
    return <PageLoader label="Loading course hub..." />;
  }

  if (isCourseError || !course) {
    return (
      <div className="flex flex-col items-center justify-center p-16 text-center max-w-md mx-auto">
        <div className="w-12 h-12 rounded-full bg-rose-100 text-rose-600 flex items-center justify-center mb-4">
          <Icon name="alertCircle" size={24} />
        </div>
        <h3 className="text-base font-bold text-slate-900 mb-1">Course not found</h3>
        <p className="text-xs text-slate-500 mb-5">
          {(courseError as any)?.data?.message || "The requested course could not be loaded."}
        </p>
        <div className="flex items-center gap-3">
          <button
            type="button"
            onClick={() => {
              refetchCourse();
              refetchVersion();
            }}
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

  const handleSaveModule = async (data: { title: string; description: string; position: number }) => {
    if (!courseId || !versionId) return;
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
    refetchVersion();
  };

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

  const handleTogglePublish = async () => {
    if (!courseId) return;
    if (!isPublished && !stepsStatus.allDone) {
      notify.error(
        `Cannot publish course: ${stepsStatus.missingStepsText.join(", ")} must be completed first.`
      );
      return;
    }

    try {
      if (isPublished) {
        await unpublishCourse(courseId).unwrap();
        notify.success("Course unpublished");
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
    <div className="max-w-6xl mx-auto space-y-6 pb-12">
      {/* 1. Universal Breadcrumbs & Back Navigation */}
      <CoursePageHeader
        breadcrumbs={[
          { label: "Courses", href: "/courses" },
          { label: course.title, current: true },
        ]}
        backHref="/courses"
      />

      {/* 2. 5-Step Stepper for Guided Course Creation */}
      {(!isPublished || stepParam) && (
        <CourseCreationStepper
          courseId={courseId}
          activeStepId={stepParam ? Number(stepParam) : stepsStatus.currentStepId}
          steps={stepperSteps}
          onStepClick={(step) => {
            const matched = setupSteps.find((s) => s.id === step.id);
            if (matched?.onClick) matched.onClick();
          }}
        />
      )}

      {/* 3. Course Header Banner with REAL Metrics */}
      <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-2xs flex flex-wrap items-center justify-between gap-5">
        <div className="flex items-center gap-4 min-w-0">
          <div className="w-24 h-16 rounded-xl bg-gradient-to-br from-slate-800 to-slate-950 flex items-center justify-center text-white shrink-0 shadow-xs">
            <Icon name="book" size={24} />
          </div>
          <div className="min-w-0">
            <div className="flex items-center gap-2">
              <h2 className="text-lg font-bold text-[#0A1530] truncate">{course.title}</h2>
              <span
                className={cn(
                  "px-2.5 py-0.5 rounded-full text-xs font-bold shrink-0",
                  isPublished ? "bg-[#E7F3EC] text-[#00663C]" : "bg-amber-100 text-amber-800"
                )}
              >
                {isPublished ? "Published" : "Draft"}
              </span>
            </div>
            <div className="flex flex-wrap items-center gap-3 text-xs text-slate-500 font-medium mt-1">
              <span className="flex items-center gap-1">
                <Icon name="clock" size={13} /> {parsedSummary.duration}
              </span>
              <span className="flex items-center gap-1">
                <Icon name="layers" size={13} /> {modules.length} {modules.length === 1 ? "module" : "modules"}
              </span>
              <span className="flex items-center gap-1">
                <Icon name="users" size={13} /> {enrolledStudents.length} {enrolledStudents.length === 1 ? "student" : "students"}
              </span>
              <span>Pass mark {parsedSummary.passPercentage}</span>
            </div>
          </div>
        </div>

        {isSuperAdminOrAdmin && (
          <div className="flex items-center gap-2.5 shrink-0">
            <button
              type="button"
              onClick={() => navigate(`/courses/${courseId}/edit?from=hub`)}
              className="px-3.5 py-1.5 rounded-xl border border-slate-300 bg-white text-xs font-semibold text-slate-700 hover:bg-slate-50 cursor-pointer"
            >
              Edit course
            </button>

            <div className="relative group">
              <button
                type="button"
                disabled={!isPublished && !stepsStatus.allDone}
                onClick={handleTogglePublish}
                className={cn(
                  "px-3.5 py-1.5 rounded-xl text-xs font-bold cursor-pointer transition-colors shadow-xs disabled:opacity-50 disabled:cursor-not-allowed",
                  isPublished
                    ? "border border-slate-300 bg-white text-slate-700 hover:bg-slate-50"
                    : "bg-[#00663C] text-white hover:bg-[#00522F]"
                )}
              >
                {isPublished ? "Unpublish" : "Publish course"}
              </button>
              {!isPublished && !stepsStatus.allDone && (
                <div className="absolute right-0 top-full mt-1.5 hidden group-hover:block z-20 w-64 p-2 rounded-xl bg-slate-900 text-white text-[11px] shadow-lg">
                  Complete all 5 steps to publish. Missing: {stepsStatus.missingStepsText.join(", ")}
                </div>
              )}
            </div>
          </div>
        )}
      </div>

      {/* 3. Setup Progress Cards (matching 5 Steps with Click-to-Jump) */}
      <SetupProgress
        steps={setupSteps}
        onStepClick={(step) => {
          if (step.onClick) step.onClick();
        }}
      />

      {/* 4. Hub Tabs Card */}
      <div className="rounded-2xl border border-slate-200 bg-white shadow-2xs overflow-hidden">
        {/* Tabs Bar */}
        <div className="flex border-b border-slate-200 px-5 gap-6">
          {(["modules", "overview", "final_exam", "students"] as const).map((tab) => (
            <button
              key={tab}
              type="button"
              onClick={() => handleSelectTab(tab)}
              className={cn(
                "py-3.5 text-xs font-bold transition-all relative capitalize cursor-pointer",
                activeTab === tab
                  ? "text-[#00663C] after:absolute after:bottom-0 after:left-0 after:right-0 after:h-0.5 after:bg-[#00663C]"
                  : "text-slate-500 hover:text-slate-900"
              )}
            >
              {tab === "final_exam" ? "Final exam" : tab}
            </button>
          ))}
        </div>

        {/* Tab 1: Modules */}
        {activeTab === "modules" && (
          <div>
            <div className="flex flex-wrap items-center justify-between p-5 border-b border-slate-100 bg-slate-50/50 gap-3">
              <p className="text-xs text-slate-500 font-medium">
                Drag to reorder. Students must finish modules in this order.
              </p>
              <div className="flex items-center gap-2">
                {modules.length > 0 && modules[0] && (
                  <button
                    type="button"
                    onClick={() => navigate(`/courses/${courseId}/modules/${modules[0]!.module_id}/chapters?step=3`)}
                    className="inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-xl border border-slate-300 bg-white text-xs font-bold text-slate-700 hover:bg-slate-50 cursor-pointer"
                  >
                    <span>Manage Chapters</span>
                    <Icon name="arrow-right" size={14} />
                  </button>
                )}
                {isSuperAdminOrAdmin && (
                  <button
                    type="button"
                    onClick={() => {
                      setEditingModule(null);
                      setIsAddModuleOpen(true);
                    }}
                    className="inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-xl bg-[#00663C] text-xs font-bold text-white hover:bg-[#00522F] cursor-pointer shadow-xs"
                  >
                    <Icon name="plus" size={14} /> Add module
                  </button>
                )}
              </div>
            </div>

            {modules.length === 0 ? (
              <div className="p-16 text-center">
                <Icon name="layers" size={32} className="mx-auto text-slate-300 mb-2" />
                <h4 className="text-sm font-bold text-slate-800">No modules yet</h4>
                <p className="text-xs text-slate-500 mt-1 mb-4">
                  Step 2: Add your first module to begin organizing chapters and tests.
                </p>
                <button
                  type="button"
                  onClick={() => setIsAddModuleOpen(true)}
                  className="px-4 py-2 rounded-xl bg-[#00663C] text-xs font-bold text-white hover:bg-[#00522F] cursor-pointer"
                >
                  Add module
                </button>
              </div>
            ) : (
              <div className="divide-y divide-slate-100">
                {modules.map((m, idx) => {
                  const chaptersCount = m.topics?.length ?? 0;
                  const isReady = chaptersCount > 0;

                  return (
                    <div
                      key={m.module_id}
                      draggable
                      onDragStart={() => setDraggedModuleIndex(idx)}
                      onDragOver={(e) => e.preventDefault()}
                      onDrop={() => void handleDropModule(idx)}
                      className="flex items-center gap-4 p-4 hover:bg-slate-50/70 transition-colors cursor-move"
                    >
                      <button
                        type="button"
                        className="text-slate-300 hover:text-slate-600 cursor-grab p-1"
                        title="Drag to reorder"
                      >
                        <Icon name="menu" size={16} />
                      </button>

                      <span className="w-7 h-7 rounded-lg bg-slate-100 border border-slate-200 text-slate-700 text-xs font-bold flex items-center justify-center shrink-0">
                        {idx + 1}
                      </span>

                      <div className="min-w-0 flex-1">
                        <h4 className="text-sm font-bold text-[#0A1530] truncate">{m.title}</h4>
                        <p className="text-xs text-slate-500 truncate">
                          {m.description || `${chaptersCount} chapters included`}
                        </p>
                      </div>

                      <div className="w-40 shrink-0 hidden md:block">
                        <div className="flex items-center justify-between text-[11px] text-slate-500 mb-1">
                          <span>{chaptersCount} chapters</span>
                          <b className={cn("font-bold", isReady ? "text-[#00663C]" : "text-slate-400")}>
                            {isReady ? "Ready" : "0%"}
                          </b>
                        </div>
                        <div className="h-1.5 rounded-full bg-slate-100 overflow-hidden">
                          <div
                            className="h-full bg-[#00663C] rounded-full transition-all"
                            style={{ width: isReady ? "100%" : "0%" }}
                          />
                        </div>
                      </div>

                      <div className="flex items-center gap-2 shrink-0">
                        <button
                          type="button"
                          onClick={() => setManagingModuleTest(m)}
                          className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-blue-200 bg-blue-50/70 text-xs font-bold text-[#2563EB] hover:bg-blue-100 cursor-pointer shadow-2xs"
                        >
                          <Icon name="clipboardCheck" size={13} />
                          <span>Module Test</span>
                        </button>

                        <button
                          type="button"
                          onClick={() => navigate(`/courses/${courseId}/modules/${m.module_id}/chapters?step=3`)}
                          className="px-3 py-1.5 rounded-lg border border-slate-200 bg-white text-xs font-semibold text-slate-700 hover:bg-slate-100 cursor-pointer"
                        >
                          Chapters ({chaptersCount})
                        </button>
                        {isSuperAdminOrAdmin && (
                          <>
                            <button
                              type="button"
                              onClick={() => {
                                setEditingModule(m);
                                setIsAddModuleOpen(true);
                              }}
                              className="p-1.5 rounded-lg text-slate-400 hover:text-slate-700 hover:bg-slate-100 cursor-pointer"
                              title="Edit module"
                            >
                              <Icon name="edit" size={15} />
                            </button>
                            <button
                              type="button"
                              onClick={() => setDeletingModule(m)}
                              className="p-1.5 rounded-lg text-slate-400 hover:text-rose-600 hover:bg-rose-50 cursor-pointer"
                              title="Delete module"
                            >
                              <Icon name="trash" size={15} />
                            </button>
                          </>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        )}

        {/* Tab 2: Overview */}
        {activeTab === "overview" && (
          <div className="p-6 space-y-4">
            <h4 className="text-sm font-bold text-[#0A1530]">Course Overview</h4>
            <p className="text-xs text-slate-600 leading-relaxed max-w-2xl">
              {parsedSummary.cleanDescription || course.summary || "No overview provided for this course yet."}
            </p>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 pt-4 border-t border-slate-100">
              <div>
                <span className="text-[11px] text-slate-400 block font-medium">Slug</span>
                <b className="text-xs text-slate-800 font-mono">{course.slug}</b>
              </div>
              <div>
                <span className="text-[11px] text-slate-400 block font-medium">Created</span>
                <b className="text-xs text-slate-800 font-mono">
                  {new Date(course.created_at).toLocaleDateString()}
                </b>
              </div>
              <div>
                <span className="text-[11px] text-slate-400 block font-medium">Versions</span>
                <b className="text-xs text-slate-800 font-mono">{course.versions.length}</b>
              </div>
              <div>
                <span className="text-[11px] text-slate-400 block font-medium">Total Modules</span>
                <b className="text-xs text-slate-800 font-mono">{modules.length}</b>
              </div>
            </div>
          </div>
        )}

        {/* Tab 3: Final Exam Configuration (Full Implementation) */}
        {activeTab === "final_exam" && (
          <div className="p-6 space-y-5">
            <div className="flex flex-wrap items-center justify-between gap-3 pb-3 border-b border-slate-100">
              <div>
                <div className="flex items-center gap-2">
                  <h4 className="text-sm font-bold text-[#0A1530]">Final Proctored Exam</h4>
                  <span
                    className={cn(
                      "px-2.5 py-0.5 rounded-full text-xs font-bold",
                      stepsStatus.step5Done
                        ? "bg-[#E7F3EC] text-[#00663C]"
                        : "bg-amber-100 text-amber-800"
                    )}
                  >
                    {stepsStatus.step5Done ? "Configured & Active" : "Not configured"}
                  </span>
                </div>
                <p className="text-xs text-slate-500 mt-0.5">
                  Proctored exam required for course completion and student certification.
                </p>
              </div>

              {isSuperAdminOrAdmin && (
                <div className="flex items-center gap-2">
                  {stepsStatus.step5Done && !isConfiguringExam && (
                    <button
                      type="button"
                      onClick={() => setIsRemoveExamModalOpen(true)}
                      className="px-3 py-1.5 rounded-xl border border-rose-200 text-xs font-semibold text-rose-600 hover:bg-rose-50 cursor-pointer"
                    >
                      Remove Exam
                    </button>
                  )}
                  <button
                    type="button"
                    onClick={() => setIsConfiguringExam(!isConfiguringExam)}
                    className="px-3.5 py-1.5 rounded-xl border border-slate-300 bg-white text-xs font-semibold text-slate-700 hover:bg-slate-50 cursor-pointer"
                  >
                    {isConfiguringExam ? "Cancel" : stepsStatus.step5Done ? "Edit Configuration" : "Configure Exam"}
                  </button>
                </div>
              )}
            </div>

            {/* Warning if no approved questions available */}
            {!hasApprovedQuestions && (
              <div className="rounded-xl border border-amber-200 bg-amber-50/70 p-4 flex flex-wrap items-center justify-between gap-3">
                <div className="flex items-center gap-3">
                  <div className="w-9 h-9 rounded-xl bg-amber-100 text-amber-800 flex items-center justify-center shrink-0">
                    <Icon name="alertCircle" size={18} />
                  </div>
                  <div>
                    <h5 className="text-xs font-bold text-amber-900">Approve chapter questions first</h5>
                    <p className="text-[11px] text-amber-700 mt-0.5">
                      The final exam draws from approved questions in your question bank. Please approve chapter questions in Step 4.
                    </p>
                  </div>
                </div>
                <button
                  type="button"
                  onClick={() => navigate(`/courses/${courseId}/questions/review?step=4`)}
                  className="px-3.5 py-1.5 rounded-xl bg-amber-700 text-xs font-bold text-white hover:bg-amber-800 cursor-pointer"
                >
                  Go to Step 4 (Approve questions)
                </button>
              </div>
            )}

            {isConfiguringExam ? (
              <div className="p-6 rounded-2xl border border-emerald-200 bg-emerald-50/20 space-y-5">
                <div className="border-b border-emerald-200/60 pb-3">
                  <h5 className="text-sm font-bold text-slate-900">Exam Parameters & Settings</h5>
                  <p className="text-xs text-slate-500 mt-0.5">
                    Configure timing, passing standards, proctoring rules, and question sources.
                  </p>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div>
                    <label className="block text-xs font-bold text-slate-800 mb-1">Exam Title *</label>
                    <input
                      type="text"
                      required
                      value={examTitle}
                      onChange={(e) => setExamTitle(e.target.value)}
                      placeholder="e.g. Python Mastery Certification Exam"
                      className="w-full rounded-xl border border-slate-300 px-3 py-2 text-xs bg-white text-slate-900 focus:border-[#00663C] focus:outline-none"
                    />
                  </div>

                  <div>
                    <label className="block text-xs font-bold text-slate-800 mb-1">Duration (Minutes) *</label>
                    <input
                      type="number"
                      required
                      min={5}
                      max={300}
                      value={examDurationMinutes}
                      onChange={(e) => setExamDurationMinutes(Number(e.target.value))}
                      className="w-full rounded-xl border border-slate-300 px-3 py-2 text-xs bg-white text-slate-900 focus:border-[#00663C] focus:outline-none"
                    />
                  </div>
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                  <div>
                    <label className="block text-xs font-bold text-slate-800 mb-1">Pass Mark (%) *</label>
                    <input
                      type="number"
                      min={10}
                      max={100}
                      value={examPassMark}
                      onChange={(e) => setExamPassMark(Number(e.target.value))}
                      className="w-full rounded-xl border border-slate-300 px-3 py-2 text-xs bg-white text-slate-900 focus:border-[#00663C] focus:outline-none"
                      required
                    />
                  </div>

                  <div>
                    <label className="block text-xs font-bold text-slate-800 mb-1">Allowed Attempts *</label>
                    <input
                      type="number"
                      min={1}
                      max={20}
                      value={examAttempts}
                      onChange={(e) => setExamAttempts(Number(e.target.value))}
                      className="w-full rounded-xl border border-slate-300 px-3 py-2 text-xs bg-white text-slate-900 focus:border-[#00663C] focus:outline-none"
                      required
                    />
                  </div>

                  <div>
                    <label className="block text-xs font-bold text-slate-800 mb-1">Cooldown (Days) *</label>
                    <input
                      type="number"
                      min={0}
                      max={30}
                      value={examCooldownDays}
                      onChange={(e) => setExamCooldownDays(Number(e.target.value))}
                      className="w-full rounded-xl border border-slate-300 px-3 py-2 text-xs bg-white text-slate-900 focus:border-[#00663C] focus:outline-none"
                      required
                    />
                  </div>
                </div>

                {/* Proctoring & Security Rules */}
                <div className="p-4 rounded-xl border border-slate-200 bg-white space-y-3">
                  <h6 className="text-xs font-bold text-slate-900">Proctoring & Exam Integrity</h6>
                  <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                    <label className="flex items-center gap-2.5 cursor-pointer">
                      <input
                        type="checkbox"
                        checked={examCameraRequired}
                        onChange={(e) => setExamCameraRequired(e.target.checked)}
                        className="rounded border-slate-300 text-[#00663C] focus:ring-[#00663C]"
                      />
                      <span className="text-xs text-slate-700 font-semibold">Camera Required</span>
                    </label>

                    <label className="flex items-center gap-2.5 cursor-pointer">
                      <input
                        type="checkbox"
                        checked={examShuffle}
                        onChange={(e) => setExamShuffle(e.target.checked)}
                        className="rounded border-slate-300 text-[#00663C] focus:ring-[#00663C]"
                      />
                      <span className="text-xs text-slate-700 font-semibold">Shuffle Questions</span>
                    </label>

                    <div className="flex items-center gap-2">
                      <span className="text-xs text-slate-700 font-semibold shrink-0">Max Warnings:</span>
                      <input
                        type="number"
                        min={1}
                        max={10}
                        value={examMaxWarnings}
                        onChange={(e) => setExamMaxWarnings(Number(e.target.value))}
                        className="w-16 rounded-lg border border-slate-300 px-2 py-1 text-xs text-slate-900"
                      />
                    </div>
                  </div>
                </div>

                {/* Final Test Questions Management */}
                <div className="space-y-4">
                  <AssessmentQuestionManager
                    questions={finalCustomQuestions}
                    contextTitle={course?.title ? `${course.title} · Final Exam` : "Final Exam"}
                    contextType="final"
                    targetQuestionCount={examQuestionCount}
                    onSaveQuestion={handleSaveFinalQuestion}
                    onDeleteQuestion={handleDeleteFinalQuestion}
                    onImportDrafts={handleImportFinalDrafts}
                  />

                  {/* Optional: Import/Append existing chapter questions */}
                  {courseApprovedQuestions.length > 0 && (
                    <div className="flex flex-wrap items-center justify-between gap-3 p-4 rounded-2xl border border-slate-200 bg-slate-50/70">
                      <div>
                        <h6 className="text-xs font-bold text-slate-800">
                          Import from Chapter Questions
                        </h6>
                        <p className="text-[11px] text-slate-500">
                          {courseApprovedQuestions.length} approved questions available across course chapters.
                        </p>
                      </div>

                      <Button
                        type="button"
                        variant="secondary"
                        size="sm"
                        onClick={() => {
                          const toAdd: ManagedQuestionItem[] = courseApprovedQuestions.map((q) => {
                            const opts = (q as any).options?.map((o: any) => ({
                              id: o.id || "a",
                              text: o.text || "",
                            })) || [];
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
                          persistFinalQuestions([...finalCustomQuestions, ...toAdd]);
                          notify.success(`Added ${toAdd.length} chapter questions to Final Exam!`);
                        }}
                        className="text-xs font-semibold"
                      >
                        + Add All {courseApprovedQuestions.length} Chapter Questions
                      </Button>
                    </div>
                  )}
                </div>

                <div className="flex justify-end gap-2 pt-2 border-t border-emerald-200/60">
                  <button
                    type="button"
                    onClick={() => setIsConfiguringExam(false)}
                    className="px-4 py-2 rounded-xl border border-slate-300 text-xs font-semibold text-slate-700 hover:bg-slate-50 cursor-pointer"
                  >
                    Cancel
                  </button>
                  <button
                    type="button"
                    onClick={handleSaveFinalExam}
                    disabled={
                      isCreatingTest ||
                      isUpdatingTest ||
                      isSavingRules ||
                      (finalCustomQuestions.length === 0 && !hasApprovedQuestions)
                    }
                    className="px-5 py-2 rounded-xl bg-[#00663C] text-xs font-bold text-white hover:bg-[#00522F] disabled:opacity-50 cursor-pointer shadow-xs"
                  >
                    {isCreatingTest || isUpdatingTest || isSavingRules ? "Saving..." : "Save Exam Configuration"}
                  </button>
                </div>
              </div>
            ) : stepsStatus.step5Done ? (
              <div className="space-y-4">
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
                  <div className="p-4 rounded-xl border border-slate-200 bg-slate-50">
                    <span className="text-[11px] text-slate-500 font-medium block">Duration</span>
                    <b className="text-lg font-bold text-[#0A1530]">
                      {finalTestDetail?.duration_minutes || 60} mins
                    </b>
                  </div>
                  <div className="p-4 rounded-xl border border-slate-200 bg-slate-50">
                    <span className="text-[11px] text-slate-500 font-medium block">Pass Mark</span>
                    <b className="text-lg font-bold text-[#0A1530]">
                      {versionDetail?.rule?.final_pass_mark || 70}%
                    </b>
                  </div>
                  <div className="p-4 rounded-xl border border-slate-200 bg-slate-50">
                    <span className="text-[11px] text-slate-500 font-medium block">Attempts Allowed</span>
                    <b className="text-lg font-bold text-[#0A1530]">
                      {versionDetail?.rule?.final_test_attempts || 3}
                    </b>
                  </div>
                  <div className="p-4 rounded-xl border border-slate-200 bg-slate-50">
                    <span className="text-[11px] text-slate-500 font-medium block">Camera Required</span>
                    <b className="text-lg font-bold text-[#00663C]">
                      {finalTestDetail?.proctoring_level !== "none" ? "Yes" : "No"}
                    </b>
                  </div>
                </div>

                <div className="rounded-xl border border-slate-200 bg-white p-4 flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <div className="w-10 h-10 rounded-xl bg-emerald-50 text-[#00663C] flex items-center justify-center">
                      <Icon name="check" size={20} />
                    </div>
                    <div>
                      <h5 className="text-xs font-bold text-slate-900">
                        {finalTestDetail?.title || "Final Certification Exam"}
                      </h5>
                      <p className="text-[11px] text-slate-500 font-mono">
                        Test ID: {finalTestId} · Linked & Active for Students
                      </p>
                    </div>
                  </div>

                  <button
                    type="button"
                    onClick={() => setIsConfiguringExam(true)}
                    className="px-3.5 py-1.5 rounded-xl border border-slate-300 text-xs font-semibold text-slate-700 hover:bg-slate-50 cursor-pointer"
                  >
                    Edit Exam
                  </button>
                </div>
              </div>
            ) : (
              <div className="text-center py-12 border border-dashed border-slate-200 rounded-2xl">
                <Icon name="shield" size={32} className="mx-auto text-slate-300 mb-2" />
                <h4 className="text-sm font-bold text-slate-800">Final exam is not set</h4>
                <p className="text-xs text-slate-500 mt-1 mb-4 max-w-sm mx-auto">
                  Step 5 of 5: Configure the proctored exam with passing score, timer, and webcam rules.
                </p>
                <button
                  type="button"
                  onClick={() => setIsConfiguringExam(true)}
                  className="px-4 py-2 rounded-xl bg-[#00663C] text-xs font-bold text-white hover:bg-[#00522F] cursor-pointer shadow-xs"
                >
                  Configure Final Exam
                </button>
              </div>
            )}
          </div>
        )}

        {/* Tab 4: Students */}
        {activeTab === "students" && (
          <div className="p-6 space-y-4">
            <div className="flex items-center justify-between pb-3 border-b border-slate-100">
              <div>
                <h4 className="text-sm font-bold text-[#0A1530]">Enrolled Students</h4>
                <p className="text-xs text-slate-500">
                  Real student enrollments for batches assigned to this course.
                </p>
              </div>
              <span className="px-3 py-1 rounded-full bg-emerald-50 text-[#00663C] text-xs font-bold">
                {enrolledStudents.length} Active {enrolledStudents.length === 1 ? "Student" : "Students"}
              </span>
            </div>

            {enrolledStudents.length === 0 ? (
              <div className="text-center py-12">
                <Icon name="users" size={32} className="mx-auto text-slate-300 mb-2" />
                <h4 className="text-sm font-bold text-slate-800">No students enrolled yet</h4>
                <p className="text-xs text-slate-500 mt-1 max-w-sm mx-auto">
                  Students will appear here once assigned to batches for this course.
                </p>
              </div>
            ) : (
              <div className="divide-y divide-slate-100 border border-slate-200 rounded-xl overflow-hidden bg-white">
                {enrolledStudents.map((enr, eIdx) => (
                  <div key={enr.enrollment_id || eIdx} className="p-3.5 flex items-center justify-between hover:bg-slate-50/60">
                    <div className="flex items-center gap-3">
                      <div className="w-8 h-8 rounded-full bg-[#E7F3EC] text-[#00663C] font-bold text-xs flex items-center justify-center">
                        {String(eIdx + 1)}
                      </div>
                      <div>
                        <b className="text-xs font-bold text-[#0A1530] block">
                          Student #{enr.student_user_id}
                        </b>
                        <span className="text-[11px] text-slate-400 font-mono">
                          Batch: {enr.batch_id} · Enrolled {new Date(enr.enrolled_at).toLocaleDateString()}
                        </span>
                      </div>
                    </div>
                    <span className="px-2.5 py-0.5 rounded-full text-[11px] font-bold bg-[#E7F3EC] text-[#00663C]">
                      {enr.status}
                    </span>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>

      {/* Modals */}
      <AddModuleModal
        isOpen={isAddModuleOpen}
        initialData={
          editingModule
            ? {
                title: editingModule.title,
                description: editingModule.description || "",
                position: editingModule.position || modules.length + 1,
              }
            : null
        }
        courseTitle={course?.title}
        defaultPosition={modules.length + 1}
        onClose={() => {
          setIsAddModuleOpen(false);
          setEditingModule(null);
        }}
        onSubmit={handleSaveModule}
      />

      <ConfirmModal
        isOpen={Boolean(deletingModule)}
        title="Delete module?"
        description={`Are you sure you want to delete "${deletingModule?.title}"? All chapters inside this module will also be removed.`}
        confirmLabel="Delete"
        tone="danger"
        onConfirm={handleDeleteModule}
        onClose={() => setDeletingModule(null)}
      />

      <ConfirmModal
        isOpen={isRemoveExamModalOpen}
        title="Remove Final Exam Configuration?"
        description="Are you sure you want to remove the final exam from this course? Students will not be able to take the certification exam until a new exam is configured."
        confirmLabel="Remove Exam"
        tone="danger"
        onConfirm={handleRemoveFinalExam}
        onClose={() => setIsRemoveExamModalOpen(false)}
      />

      {/* Module Test Setup Modal */}
      {managingModuleTest && versionId && courseId && (
        <ModuleTestSetupModal
          isOpen={Boolean(managingModuleTest)}
          onClose={() => setManagingModuleTest(null)}
          module={managingModuleTest}
          courseId={courseId}
          versionId={versionId}
          onSaved={() => {
            refetchVersion();
            refetchCourse();
          }}
        />
      )}
    </div>
  );
}
