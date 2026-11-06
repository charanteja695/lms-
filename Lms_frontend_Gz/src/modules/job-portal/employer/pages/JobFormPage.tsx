import { JobFormErrorBoundary } from "@/modules/job-portal/employer/components/form/JobFormErrorBoundary";
import React, { useEffect, useState, useCallback } from "react";
import { Navigate, useNavigate, useParams, useSearchParams } from "react-router-dom";

import { useNotify } from "@/core/hooks/useNotify";
import { toApiError } from "@/core/lib/apiError";
import { cn } from "@/core/lib/cn";
import {
  useCreateEmployerJobMutation,
  useGetEmployerJobQuery,
  useJobActionMutation,
  useUpdateEmployerJobMutation,
} from "@/modules/job-portal/employer/api/employerJobsApi";
import { JobStep1Details } from "@/modules/job-portal/employer/components/form/JobStep1Details";
import { JobStep2Description } from "@/modules/job-portal/employer/components/form/JobStep2Description";
import { JobEligibilitySection } from "@/modules/job-portal/employer/components/form/JobEligibilitySection";
import { JobApplicationDetailsSection } from "@/modules/job-portal/employer/components/form/JobApplicationDetailsSection";
import { JobPipelineSection } from "@/modules/job-portal/employer/components/form/JobPipelineSection";
import {
  emptyJobForm,
  jobToForm,
  toJobBody,
  type JobFormValues,
} from "@/modules/job-portal/employer/form/jobForm";
import { useJobRights } from "@/modules/job-portal/common/hooks/useJobRights";
import { usePermissions } from "@/modules/user-management/common/permissions/usePermissions";
import { Alert, Button, Icon, PageLoader } from "@/shared/ui";

const STEPS = [
  { id: 1, key: "details", label: "Job details", subtitle: "Basic role information, location & salary" },
  { id: 2, key: "description", label: "Description", subtitle: "Role mission, requirements & responsibilities" },
  { id: 3, key: "requirements", label: "Requirements", subtitle: "Eligibility criteria & educational prerequisites" },
  { id: 4, key: "application", label: "Application", subtitle: "Application methods & recruiter details" },
  { id: 5, key: "hiring-process", label: "Hiring process", subtitle: "Assessment tests & interview pipeline" },
  { id: 6, key: "review", label: "Review", subtitle: "Final verification and publishing" },
] as const;

function JobFormInner() {
  const { jobId } = useParams();
  const { isCareersManager, isStudent } = useJobRights();
  const { permissions } = usePermissions();

  if (isStudent || permissions.role === "student") {
    return <Navigate to="/jobs/board" replace />;
  }

  const navigate = useNavigate();
  const notify = useNotify();
  const { data: job, isLoading, isError } = useGetEmployerJobQuery(jobId ?? "", { skip: !jobId });
  const [create, { isLoading: creating }] = useCreateEmployerJobMutation();
  const [update, { isLoading: updating }] = useUpdateEmployerJobMutation();
  const [jobAction, { isLoading: publishing }] = useJobActionMutation();
  const isAdmin = permissions.role === "super_admin" || permissions.role === "admin" || isCareersManager;

  const [searchParams, setSearchParams] = useSearchParams();
  const presetCompany = searchParams.get("employer_org_id");
  const presetCompanyName = searchParams.get("company_name") || "";

  // Step state synced with URL ?step=X
  const initialStep = Math.min(Math.max(parseInt(searchParams.get("step") || "1", 10) || 1, 1), 6);
  const [currentStep, setCurrentStep] = useState<number>(initialStep);
  const [visitedSteps, setVisitedSteps] = useState<Set<number>>(new Set([1, initialStep]));

  // Form values state with default 30-day deadline
  const [values, setValues] = useState<JobFormValues>(() => {
    const defaultForm = emptyJobForm();
    const defaultDeadline: string = new Date(Date.now() + 30 * 24 * 60 * 60 * 1000).toISOString().split("T")[0] ?? "";
    return {
      ...defaultForm,
      deadline: defaultDeadline,
      company: presetCompany ? { id: presetCompany, label: presetCompanyName } : null,
    };
  });

  // Validation timing: tracked by touched fields and step submission attempts
  const [touchedFields, setTouchedFields] = useState<Record<string, boolean>>({});
  const [attemptedSteps, setAttemptedSteps] = useState<Record<number, boolean>>({});
  const [stepErrors, setStepErrors] = useState<Record<number, Record<string, string>>>({});

  // Auto-save & persistence state
  const [hasUnsavedChanges, setHasUnsavedChanges] = useState(false);
  const [autosaveStatus, setAutosaveStatus] = useState<"saved" | "saving" | "unsaved">("saved");
  const [lastSavedTime, setLastSavedTime] = useState<string>(() => "All changes saved " + new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }));
  const [currentJobId, setCurrentJobId] = useState<string | null>(jobId ?? null);
  const [previewStudentView, setPreviewStudentView] = useState(false);

  // Sync currentStep with URL parameter on browser back / forward
  useEffect(() => {
    const stepParam = Math.min(Math.max(parseInt(searchParams.get("step") || "1", 10) || 1, 1), 6);
    if (stepParam !== currentStep) {
      setCurrentStep(stepParam);
      setVisitedSteps((prev) => new Set([...prev, stepParam]));
    }
  }, [searchParams]);

  // Push new step to URL query parameter
  const updateUrlStep = useCallback(
    (newStep: number) => {
      setSearchParams(
        (prev) => {
          const next = new URLSearchParams(prev);
          next.set("step", String(newStep));
          return next;
        },
        { replace: false }
      );
    },
    [setSearchParams]
  );

  // Load existing job
  useEffect(() => {
    if (job) {
      setValues(jobToForm(job));
      setCurrentJobId(job.job_id);
      setAutosaveStatus("saved");
      setLastSavedTime("All changes saved");
      setHasUnsavedChanges(false);
      setVisitedSteps(new Set([1, 2, 3, 4, 5, 6]));
    }
  }, [job]);

  // Warn on tab close with unsaved changes
  useEffect(() => {
    const handleBeforeUnload = (e: BeforeUnloadEvent) => {
      if (hasUnsavedChanges) {
        e.preventDefault();
        e.returnValue = "";
      }
    };
    window.addEventListener("beforeunload", handleBeforeUnload);
    return () => window.removeEventListener("beforeunload", handleBeforeUnload);
  }, [hasUnsavedChanges]);

  // Track field changes
  const set = useCallback(
    <K extends keyof JobFormValues>(key: K, value: JobFormValues[K]) => {
      setValues((current) => ({ ...current, [key]: value }));
      setHasUnsavedChanges(true);
      setAutosaveStatus("unsaved");

      // Mark touched
      setTouchedFields((prev) => ({ ...prev, [key as string]: true }));

      // Clear field-specific error
      setStepErrors((prev) => {
        const currentErrors = prev[currentStep];
        if (currentErrors && currentErrors[key as string]) {
          const next = { ...currentErrors };
          delete next[key as string];
          return { ...prev, [currentStep]: next };
        }
        return prev;
      });
    },
    [currentStep]
  );

  const locked = Boolean(job && job.applications > 0);

  // Validate specific step
  const validateStep = (stepNumber: number): { valid: boolean; errors: Record<string, string>; firstField?: string } => {
    const errors: Record<string, string> = {};
    let firstField: string | undefined;

    if (stepNumber === 1) {
      if (isAdmin && !currentJobId && !values.company) {
        errors.company = "Hiring company is required";
        if (!firstField) firstField = "field-company";
      }
      if (!values.title.trim()) {
        errors.title = "Job title is required";
        if (!firstField) firstField = "field-title";
      }
      if (values.location_type !== "remote" && !values.locations.trim()) {
        errors.locations = "At least one location is required for on-site/hybrid positions";
        if (!firstField) firstField = "field-locations";
      }
      if (!values.deadline) {
        errors.deadline = "Application deadline is required";
        if (!firstField) firstField = "field-deadline";
      }
      const minVal = parseFloat(values.ctc_min_lakhs);
      const maxVal = parseFloat(values.ctc_max_lakhs);
      if (!values.is_negotiable && !isNaN(minVal) && !isNaN(maxVal) && minVal > maxVal) {
        errors.salary = "Minimum salary cannot exceed maximum salary";
        if (!firstField) firstField = "field-salary";
      }
    } else if (stepNumber === 2) {
      if (!values.about_job.trim() || values.about_job.trim().length < 10) {
        errors.about_job = "About the job description is required (minimum 10 characters)";
        if (!firstField) firstField = "field-about_job";
      }
      if (values.minimum_qualifications.length < 2) {
        errors.minimum_qualifications = "Minimum 2 qualifications are required";
        if (!firstField) firstField = "field-minimum_qualifications";
      }
      if (values.responsibilities.length < 3) {
        errors.responsibilities = "Minimum 3 responsibilities are required";
        if (!firstField) firstField = "field-responsibilities";
      }
    }

    return { valid: Object.keys(errors).length === 0, errors, firstField };
  };

  // Perform draft save
  const saveDraft = async (silent = false): Promise<string | null> => {
    if (!values.title.trim()) {
      if (!silent) notify.error("Please enter a job title to save draft");
      return null;
    }

    // For admin creating a new job, employer organization is required by backend to create the job record
    if (isAdmin && !currentJobId && !values.company?.id) {
      if (!silent) notify.error("Please select a hiring company in Step 1 to save draft to database");
      return null;
    }

    setAutosaveStatus("saving");
    try {
      const body = toJobBody(values);
      const orgId = values.company?.id;

      let savedId = currentJobId;
      if (currentJobId) {
        await update({ jobId: currentJobId, body }).unwrap();
      } else {
        if (orgId) {
          body.employer_org_id = orgId;
        }
        const res = await create(body).unwrap();
        savedId = res.job_id;
        setCurrentJobId(res.job_id);
      }

      setHasUnsavedChanges(false);
      setAutosaveStatus("saved");
      const timeStr = new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
      setLastSavedTime(`All changes saved ${timeStr}`);
      if (!silent) notify.success("Draft saved successfully");
      return savedId;
    } catch (err) {
      setAutosaveStatus("unsaved");
      if (!silent) notify.error(toApiError(err).message || "Failed to save draft");
      return null;
    }
  };

  // Auto-save debounce effect (every 6 seconds if dirty and title exists)
  useEffect(() => {
    if (!hasUnsavedChanges || !values.title.trim()) return;

    const timer = setTimeout(() => {
      void saveDraft(true);
    }, 6000);

    return () => clearTimeout(timer);
  }, [hasUnsavedChanges, values]);

  // Navigate directly to step (no validation required when clicking steps or navigating back/forward)
  const goToStep = (stepNumber: number) => {
    if (stepNumber === currentStep) return;

    // Moving between steps by clicking the stepper does not require validation and does not lose entered data.
    // If unsaved changes exist and title is entered, trigger silent draft save
    if (hasUnsavedChanges && values.title.trim()) {
      void saveDraft(true);
    }

    // Advance immediately
    setCurrentStep(stepNumber);
    setVisitedSteps((prev) => new Set([...prev, stepNumber]));
    updateUrlStep(stepNumber);
    window.scrollTo({ top: 0, behavior: "smooth" });
  };

  // Back to jobs list handler (with auto-save)
  const handleBackToJobs = async () => {
    if (hasUnsavedChanges && values.title.trim()) {
      await saveDraft(true);
      notify.success("Draft saved");
    }
    navigate("/jobs");
  };

  // Next Step click handler
  const handleSaveAndContinue = async () => {
    const validation = validateStep(currentStep);
    if (!validation.valid) {
      setAttemptedSteps((prev) => ({ ...prev, [currentStep]: true }));
      setStepErrors((prev) => ({ ...prev, [currentStep]: validation.errors }));
      if (validation.firstField) {
        const el = document.getElementById(validation.firstField);
        if (el) {
          el.scrollIntoView({ behavior: "smooth", block: "center" });
          (el.querySelector("input, textarea, select") as HTMLElement)?.focus();
        }
      }
      return;
    }

    // Clear errors for current step
    setStepErrors((prev) => {
      const next = { ...prev };
      delete next[currentStep];
      return next;
    });

    // Auto-save draft on step transition
    void saveDraft(true);

    if (currentStep < 6) {
      goToStep(currentStep + 1);
    } else {
      await handlePublish();
    }
  };

  // Check all publishing requirements
  const getPublishingChecklist = () => {
    return [
      {
        id: "title",
        label: "Job role title specified",
        step: 1,
        field: "field-title",
        passed: Boolean(values.title.trim()),
      },
      {
        id: "company",
        label: "Hiring company selected",
        step: 1,
        field: "field-company",
        passed: !isAdmin || Boolean(values.company || currentJobId),
      },
      {
        id: "locations",
        label: "Location added (for non-remote roles)",
        step: 1,
        field: "field-locations",
        passed: values.location_type === "remote" || Boolean(values.locations.trim()),
      },
      {
        id: "deadline",
        label: "Valid application deadline specified",
        step: 1,
        field: "field-deadline",
        passed: Boolean(values.deadline),
      },
      {
        id: "about_job",
        label: "Role overview entered (min 10 characters)",
        step: 2,
        field: "field-about_job",
        passed: (values.about_job || "").trim().length >= 10,
      },
      {
        id: "minimum_qualifications",
        label: "Minimum 2 qualifications specified",
        step: 2,
        field: "field-minimum_qualifications",
        passed: (values.minimum_qualifications || []).length >= 2,
      },
      {
        id: "responsibilities",
        label: "Minimum 3 responsibilities specified",
        step: 2,
        field: "field-responsibilities",
        passed: (values.responsibilities || []).length >= 3,
      },
    ];
  };

  // Publish handler
  const handlePublish = async () => {
    const checklist = getPublishingChecklist();
    const missing = checklist.filter((item) => !item.passed);

    if (missing.length > 0) {
      notify.error(`Please complete all required items before publishing (${missing.length} missing)`);
      return;
    }

    const savedId = await saveDraft(true);
    const targetId = savedId || currentJobId;
    if (!targetId) {
      notify.error("Please enter a title to publish.");
      return;
    }

    try {
      await jobAction({ jobId: targetId, action: "submit" }).unwrap();
      notify.success("Job Opening Published successfully!");
      navigate(`/jobs/${targetId}`);
    } catch (err) {
      notify.error(toApiError(err).message || "Failed to publish job opening");
    }
  };

  // Single-line Enter key handler: prevents accidental submission
  const handleFormKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && (e.target as HTMLElement).tagName === "INPUT") {
      const inputType = (e.target as HTMLInputElement).type;
      if (inputType !== "button" && inputType !== "submit") {
        e.preventDefault();
      }
    }
  };

  if (isLoading) return <PageLoader label="Loading job details..." />;
  if (isError) {
    return (
      <div className="p-8 max-w-xl mx-auto">
        <Alert tone="error">Unable to load job. The opening might have been removed or access is restricted.</Alert>
      </div>
    );
  }

  const activeStepConfig = STEPS.find((s) => s.id === currentStep) || STEPS[0];

  // Only show errors that have been touched or if current step attempted continue
  const allCurrentErrors = stepErrors[currentStep] || {};
  const visibleErrors: Record<string, string> = {};
  for (const [k, err] of Object.entries(allCurrentErrors)) {
    if (touchedFields[k] || attemptedSteps[currentStep]) {
      visibleErrors[k] = err;
    }
  }

  const checklist = getPublishingChecklist();
  const allChecklistPassed = checklist.every((c) => c.passed);
  const isSaving = autosaveStatus === "saving" || creating || updating;

  return (
    <div className="min-h-screen bg-slate-50/50" onKeyDown={handleFormKeyDown}>
      {/* 1. Slim Sticky Header (3-Zone Responsive Layout) */}
      <header className="sticky top-0 z-30 bg-white/95 backdrop-blur-md border-b border-slate-200 shadow-xs">
        <div className="w-full px-4 sm:px-6 h-16 flex items-center justify-between gap-3">
          {/* ZONE 1 (Left): Outlined 40px Back Button + Title + Draft Badge */}
          <div className="flex items-center gap-2.5 shrink-0">
            <button
              type="button"
              onClick={handleBackToJobs}
              aria-label="Back to jobs"
              title="Back to jobs"
              className="h-10 min-[1100px]:w-auto w-10 min-[1100px]:px-3.5 px-0 rounded-xl border border-slate-300 bg-white text-slate-700 hover:bg-slate-50 hover:border-slate-400 focus:outline-none focus:ring-2 focus:ring-emerald-600/30 focus:border-emerald-600 transition-colors flex items-center justify-center gap-2 text-xs font-semibold shrink-0 cursor-pointer shadow-xs"
            >
              <Icon name="arrow-left" className="h-4 w-4 shrink-0 text-slate-600" />
              <span className="hidden min-[1100px]:inline">Back to jobs</span>
            </button>

            <div className="flex items-center gap-2 shrink-0">
              <h1 className="text-sm font-bold text-slate-900 shrink-0">
                {currentJobId ? values.title || "Edit job" : "Create job"}
              </h1>
              <span className="inline-flex items-center px-2 py-0.5 rounded-md text-[11px] font-semibold bg-slate-100 text-slate-600 border border-slate-200 shrink-0">
                {job?.status ? job.status.toUpperCase() : "Draft"}
              </span>
            </div>
          </div>

          {/* ZONE 2 (Center): Stepper (Screen width >= 900px) */}
          <nav
            aria-label="Job Setup Progress"
            className="hidden min-[900px]:flex items-center justify-center flex-1 min-w-0 px-2"
          >
            <div className="flex items-center gap-1 shrink-0">
              {STEPS.map((s, idx) => {
                const isCurrent = currentStep === s.id;
                const isCompleted = visitedSteps.has(s.id) && currentStep > s.id;
                const hasErrors = Boolean(stepErrors[s.id] && Object.keys(stepErrors[s.id] || {}).length > 0);

                return (
                  <div key={s.id} className="flex items-center">
                    <button
                      type="button"
                      onClick={() => goToStep(s.id)}
                      title={`Step ${s.id}: ${s.label}`}
                      className={cn(
                        "flex items-center gap-1.5 rounded-xl text-xs font-semibold transition-all select-none cursor-pointer",
                        isCurrent
                          ? "bg-emerald-600 text-white shadow-sm ring-2 ring-emerald-600/20 px-2.5 py-1"
                          : "h-7 w-7 min-[1350px]:w-auto min-[1350px]:px-2.5 p-0 justify-center",
                        isCompleted && !isCurrent && "text-emerald-700 bg-emerald-50 hover:bg-emerald-100/70",
                        hasErrors && !isCurrent && "text-rose-700 bg-rose-50 hover:bg-rose-100/70 border border-rose-200",
                        !isCurrent && !isCompleted && !hasErrors && "text-slate-600 hover:bg-slate-100 hover:text-slate-900"
                      )}
                    >
                      <span
                        className={cn(
                          "w-5 h-5 rounded-full flex items-center justify-center text-[10px] font-bold shrink-0 transition-colors",
                          isCurrent && "bg-white text-emerald-700",
                          isCompleted && !isCurrent && "bg-emerald-600 text-white",
                          hasErrors && !isCurrent && "bg-rose-600 text-white",
                          !isCurrent && !isCompleted && !hasErrors && "bg-slate-200 text-slate-700"
                        )}
                      >
                        {isCompleted && !isCurrent ? (
                          <Icon name="check" className="h-3 w-3 stroke-[3]" />
                        ) : (
                          s.id
                        )}
                      </span>
                      <span
                        className={cn(
                          "whitespace-nowrap text-xs",
                          isCurrent ? "inline" : "hidden min-[1350px]:inline"
                        )}
                      >
                        {s.label}
                      </span>
                    </button>

                    {idx < STEPS.length - 1 && (
                      <div
                        className={cn(
                          "w-2 lg:w-2.5 h-0.5 mx-0.5 rounded-full transition-colors shrink-0",
                          currentStep > s.id ? "bg-emerald-500" : "bg-slate-200"
                        )}
                      />
                    )}
                  </div>
                );
              })}
            </div>
          </nav>

          {/* ZONE 3 (Right): Autosave Status & Save Draft Button */}
          <div className="flex items-center gap-2.5 shrink-0">
            <div className="flex items-center gap-1.5 text-xs text-slate-500 whitespace-nowrap">
              {autosaveStatus === "saving" ? (
                <>
                  <Icon name="refresh-cw" className="h-3.5 w-3.5 animate-spin text-emerald-600" />
                  <span className="hidden sm:inline text-emerald-700 font-medium">Saving...</span>
                </>
              ) : autosaveStatus === "saved" ? (
                <>
                  <Icon name="check" className="h-3.5 w-3.5 text-emerald-600" />
                  <span className="hidden sm:inline">{lastSavedTime}</span>
                </>
              ) : (
                <span className="hidden sm:inline text-amber-600 font-medium">Unsaved changes</span>
              )}
            </div>

            <Button
              type="button"
              variant="secondary"
              size="sm"
              onClick={() => void saveDraft(false)}
              loading={isSaving}
              disabled={locked || isSaving}
              className="text-xs font-semibold rounded-xl border-slate-300 hover:bg-slate-50 shadow-xs shrink-0 h-9 px-3"
            >
              Save draft
            </Button>
          </div>
        </div>

        {/* Collapsed Stepper Bar for screens < 900px */}
        <div className="min-[900px]:hidden border-t border-slate-100 px-4 py-2 bg-slate-50/90">
          <div className="flex items-center justify-between text-xs mb-1.5">
            <div className="flex items-center gap-2">
              <span className="font-bold text-slate-800">
                Step {currentStep} of 6:{" "}
                <span className="text-emerald-700">{activeStepConfig.label}</span>
              </span>
              <select
                aria-label="Jump to step"
                value={currentStep}
                onChange={(e) => goToStep(Number(e.target.value))}
                className="text-[11px] bg-white border border-slate-300 rounded-lg py-0.5 px-1.5 text-slate-700 font-medium focus:ring-1 focus:ring-emerald-600 focus:outline-none cursor-pointer"
              >
                {STEPS.map((s) => (
                  <option key={s.id} value={s.id}>
                    Step {s.id}: {s.label}
                  </option>
                ))}
              </select>
            </div>
            <span className="text-[11px] text-slate-500 font-medium">
              {Math.round((currentStep / 6) * 100)}%
            </span>
          </div>

          <div className="w-full h-1 bg-slate-200 rounded-full overflow-hidden">
            <div
              className="h-full bg-emerald-600 rounded-full transition-all duration-300"
              style={{ width: `${(currentStep / 6) * 100}%` }}
            />
          </div>
        </div>
      </header>

      {/* 2. Main Centered Content Column (with pt-6 pb-36 for sticky clearance) */}
      <main className="max-w-[760px] mx-auto pt-6 pb-36 px-4 sm:px-6">
        {/* Step Title & Subtitle Banner */}
        <div className="mb-6">
          <div className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs font-bold bg-emerald-50 text-emerald-800 border border-emerald-200 mb-2">
            <span>STEP {activeStepConfig.id} OF 6</span>
          </div>
          <h2 className="text-2xl font-extrabold text-slate-900 tracking-tight">
            {activeStepConfig.label}
          </h2>
          <p className="text-xs sm:text-sm text-slate-500 mt-1">
            {activeStepConfig.subtitle}
          </p>
        </div>

        {/* Error Summary Banner (Shown only on failed continue attempts) */}
        {Object.keys(visibleErrors).length > 0 && (
          <div className="mb-6 p-4 rounded-xl border border-rose-300 bg-rose-50 text-rose-900 space-y-2 animate-in fade-in duration-200">
            <h5 className="text-xs font-bold flex items-center gap-1.5 text-rose-800">
              <Icon name="alert" className="h-4 w-4 text-rose-600" />
              <span>
                {Object.keys(visibleErrors).length}{" "}
                {Object.keys(visibleErrors).length === 1 ? "item needs" : "items need"} your attention before continuing:
              </span>
            </h5>
            <ul className="list-disc pl-5 text-xs space-y-1">
              {Object.entries(visibleErrors).map(([key, msg]) => (
                <li key={key}>
                  <button
                    type="button"
                    onClick={() => {
                      const el = document.getElementById(`field-${key}`);
                      el?.scrollIntoView({ behavior: "smooth", block: "center" });
                      (el?.querySelector("input, textarea, select") as HTMLElement)?.focus();
                    }}
                    className="text-rose-700 font-semibold hover:underline text-left"
                  >
                    {msg}
                  </button>
                </li>
              ))}
            </ul>
          </div>
        )}

        {/* Step Content Component Container */}
        <div className="bg-white rounded-2xl border border-slate-200/90 p-6 sm:p-8 shadow-xs space-y-6">
          {currentStep === 1 && (
            <JobStep1Details
              values={values}
              set={set}
              locked={locked}
              isAdmin={isAdmin}
              errors={visibleErrors}
            />
          )}

          {currentStep === 2 && (
            <JobStep2Description
              values={values}
              set={set}
              locked={locked}
              errors={visibleErrors}
            />
          )}

          {currentStep === 3 && (
            <div className="space-y-6">
              {!values.title.trim() && (
                <div className="p-3.5 rounded-xl border border-slate-200 bg-slate-50 text-slate-700 flex items-center justify-between gap-3 text-xs">
                  <div className="flex items-center gap-2">
                    <Icon name="info" className="h-4 w-4 text-slate-500 shrink-0" />
                    <span>
                      Setting requirements for a new role. You can define eligibility criteria now or complete basic details first.
                    </span>
                  </div>
                  <button
                    type="button"
                    onClick={() => goToStep(1)}
                    className="text-emerald-700 font-bold hover:underline shrink-0 text-xs"
                  >
                    Go to Step 1 &rarr;
                  </button>
                </div>
              )}
              <div className="p-3.5 rounded-xl border border-slate-200 bg-slate-50 text-xs text-slate-600">
                Configure student eligibility requirements including minimum CGPA, eligible graduation years, and course cutoffs.
              </div>
              <JobEligibilitySection values={values} set={set} locked={locked} />
            </div>
          )}

          {currentStep === 4 && (
            <div className="space-y-6">
              <div className="p-3.5 rounded-xl border border-slate-200 bg-slate-50 text-xs text-slate-600">
                Configure application methods, internal LMS tracking, external application links, and recruiter query contact details.
              </div>
              <JobApplicationDetailsSection values={values} set={set} locked={locked} />
            </div>
          )}

          {currentStep === 5 && (
            <div className="space-y-6">
              {isAdmin && !values.company && !currentJobId && (
                <div className="p-3.5 rounded-xl border border-amber-200 bg-amber-50/70 text-amber-900 flex items-start justify-between gap-3 text-xs">
                  <div className="flex items-start gap-2">
                    <Icon name="alert" className="h-4 w-4 text-amber-600 shrink-0 mt-0.5" />
                    <div>
                      <p className="font-semibold">No hiring company selected yet</p>
                      <p className="text-amber-800 text-[11px] mt-0.5">
                        Assessments and AI interview plans are associated with the hiring company. You can configure pipeline rounds now or select a company in Job details.
                      </p>
                    </div>
                  </div>
                  <button
                    type="button"
                    onClick={() => goToStep(1)}
                    className="text-emerald-700 font-bold hover:underline shrink-0 text-xs"
                  >
                    Go to Step 1 &rarr;
                  </button>
                </div>
              )}
              <div className="p-3.5 rounded-xl border border-slate-200 bg-slate-50 text-xs text-slate-600">
                Select required online assessments, AI-driven mock interviews, and HR screening pipeline rounds.
              </div>
              <JobPipelineSection values={values} set={set} locked={locked} />
            </div>
          )}

          {currentStep === 6 && (
            <div className="space-y-6">
              {/* Friendly Empty State Notice when role details are not filled */}
              {!values.title.trim() && (
                <div className="p-4 rounded-xl border border-amber-200 bg-amber-50/80 text-amber-950 space-y-2">
                  <div className="flex items-start justify-between gap-3">
                    <div className="flex items-start gap-2.5">
                      <Icon name="info" className="h-4 w-4 text-amber-600 shrink-0 mt-0.5" />
                      <div>
                        <h5 className="text-xs font-bold">Nothing to show yet. Complete Job details first</h5>
                        <p className="text-xs text-amber-800 mt-0.5">
                          This job opening has not been filled out yet. Start by entering basic role details, then review your progress here before publishing.
                        </p>
                      </div>
                    </div>
                    <Button
                      type="button"
                      variant="secondary"
                      size="sm"
                      onClick={() => goToStep(1)}
                      className="text-xs font-bold rounded-xl border-amber-300 text-amber-900 hover:bg-amber-100 shrink-0"
                    >
                      Complete Step 1 &rarr;
                    </Button>
                  </div>
                </div>
              )}

              {/* Header Info */}
              <div className="p-4 rounded-xl border border-emerald-200 bg-emerald-50/70 text-emerald-950 space-y-2">
                <h4 className="text-sm font-bold flex items-center gap-2">
                  <Icon name="checkCircle" className="h-4 w-4 text-emerald-600" />
                  Review & Publish Job Opening
                </h4>
                <p className="text-xs text-slate-600">
                  Verify your job details below. Click <strong>Publish job opening</strong> to make this role active for eligible students across the GenZ Technologies LMS.
                </p>
              </div>

              {/* Toggle Student View Preview */}
              <div className="flex items-center justify-between p-3.5 rounded-xl border border-slate-200 bg-white">
                <div>
                  <span className="text-xs font-bold text-slate-900 block">Student Board Card Preview</span>
                  <span className="text-[11px] text-slate-500">Preview exactly how candidates see this job listing</span>
                </div>
                <Button
                  type="button"
                  variant={previewStudentView ? "primary" : "secondary"}
                  size="sm"
                  onClick={() => setPreviewStudentView((v) => !v)}
                  className="text-xs font-semibold gap-1.5 rounded-xl"
                >
                  <Icon name="eye" className="h-3.5 w-3.5" />
                  {previewStudentView ? "Hide Preview" : "Show Card Preview"}
                </Button>
              </div>

              {/* Student View Mock Card */}
              {previewStudentView && (
                <div className="p-5 rounded-2xl border-2 border-emerald-500/30 bg-emerald-50/20 space-y-4 animate-in fade-in duration-200">
                  <div className="flex items-start justify-between gap-3">
                    <div className="flex items-center gap-3">
                      <div className="w-12 h-12 rounded-xl bg-emerald-600 text-white font-extrabold text-lg flex items-center justify-center shadow-xs">
                        {(values.company?.label || values.title || "J").charAt(0).toUpperCase()}
                      </div>
                      <div>
                        <h3 className="text-sm font-bold text-slate-900">{values.title || "Job Title"}</h3>
                        <p className="text-xs text-slate-500">{values.company?.label || "Hiring Partner"}</p>
                      </div>
                    </div>
                    <span className="px-2.5 py-1 rounded-lg text-[11px] font-bold bg-emerald-100 text-emerald-800">
                      {values.location_type?.toUpperCase()}
                    </span>
                  </div>

                  <div className="flex flex-wrap items-center gap-2 text-xs text-slate-600">
                    <span className="inline-flex items-center gap-1">
                      <Icon name="map" className="h-3.5 w-3.5 text-slate-400" />
                      {values.locations || "Multiple Locations"}
                    </span>
                    <span>•</span>
                    <span className="inline-flex items-center gap-1">
                      <Icon name="briefcase" className="h-3.5 w-3.5 text-slate-400" />
                      {values.employment_type.replace("_", " ")}
                    </span>
                    <span>•</span>
                    <span className="inline-flex items-center gap-1 text-emerald-700 font-semibold">
                      ₹ {values.ctc_min_lakhs || "3"} - {values.ctc_max_lakhs || "6"} LPA
                    </span>
                  </div>

                  {values.banner_text && (
                    <div className="px-3 py-1.5 rounded-lg bg-amber-50 border border-amber-200 text-amber-800 text-xs font-medium flex items-center gap-2">
                      <Icon name="alert" className="h-3.5 w-3.5 shrink-0 text-amber-600" />
                      <span>{values.banner_text}</span>
                    </div>
                  )}
                </div>
              )}

              {/* Review Section Cards with [Edit Step] jumps */}
              <div className="space-y-3.5">
                {/* 1. Job Details Card */}
                <div className="p-4 rounded-xl border border-slate-200 bg-slate-50/50 space-y-2.5">
                  <div className="flex items-center justify-between border-b border-slate-200/80 pb-2">
                    <span className="text-xs font-bold text-slate-900 flex items-center gap-1.5">
                      <Icon name="briefcase" className="h-3.5 w-3.5 text-emerald-600" />
                      1. Job Details
                    </span>
                    <button
                      type="button"
                      onClick={() => goToStep(1)}
                      className="text-xs font-semibold text-emerald-700 hover:text-emerald-800 hover:underline"
                    >
                      Edit details
                    </button>
                  </div>
                  <div className="grid grid-cols-2 gap-2 text-xs">
                    <div>
                      <span className="text-slate-500 block">Title:</span>
                      <span className="font-semibold text-slate-800">{values.title || "—"}</span>
                    </div>
                    <div>
                      <span className="text-slate-500 block">Work Mode:</span>
                      <span className="font-semibold text-slate-800 capitalize">{values.location_type} • {values.employment_type.replace("_", " ")}</span>
                    </div>
                    <div>
                      <span className="text-slate-500 block">Locations:</span>
                      <span className="font-semibold text-slate-800">{values.locations || "Remote"}</span>
                    </div>
                    <div>
                      <span className="text-slate-500 block">Deadline:</span>
                      <span className="font-semibold text-slate-800">{values.deadline || "—"}</span>
                    </div>
                  </div>
                </div>

                {/* 2. Job Description Card */}
                <div className="p-4 rounded-xl border border-slate-200 bg-slate-50/50 space-y-2.5">
                  <div className="flex items-center justify-between border-b border-slate-200/80 pb-2">
                    <span className="text-xs font-bold text-slate-900 flex items-center gap-1.5">
                      <Icon name="fileText" className="h-3.5 w-3.5 text-emerald-600" />
                      2. Role Description
                    </span>
                    <button
                      type="button"
                      onClick={() => goToStep(2)}
                      className="text-xs font-semibold text-emerald-700 hover:text-emerald-800 hover:underline"
                    >
                      Edit description
                    </button>
                  </div>
                  <div className="grid grid-cols-2 gap-2 text-xs">
                    <div>
                      <span className="text-slate-500 block">Experience Level:</span>
                      <span className="font-semibold text-slate-800 capitalize">{values.experience_level || "Fresher"}</span>
                    </div>
                    <div>
                      <span className="text-slate-500 block">Qualifications:</span>
                      <span className="font-semibold text-slate-800">
                        {values.minimum_qualifications?.length || 0} minimum, {values.preferred_qualifications?.length || 0} preferred
                      </span>
                    </div>
                    <div className="col-span-2">
                      <span className="text-slate-500 block">Responsibilities:</span>
                      <span className="font-semibold text-slate-800">{values.responsibilities?.length || 0} items defined</span>
                    </div>
                  </div>
                </div>

                {/* 3. Requirements Card */}
                <div className="p-4 rounded-xl border border-slate-200 bg-slate-50/50 space-y-2.5">
                  <div className="flex items-center justify-between border-b border-slate-200/80 pb-2">
                    <span className="text-xs font-bold text-slate-900 flex items-center gap-1.5">
                      <Icon name="clipboardCheck" className="h-3.5 w-3.5 text-emerald-600" />
                      3. Requirements & Eligibility
                    </span>
                    <button
                      type="button"
                      onClick={() => goToStep(3)}
                      className="text-xs font-semibold text-emerald-700 hover:text-emerald-800 hover:underline"
                    >
                      Edit requirements
                    </button>
                  </div>
                  <div className="grid grid-cols-2 gap-2 text-xs">
                    <div>
                      <span className="text-slate-500 block">Required Skills:</span>
                      <span className="font-semibold text-slate-800">{values.required_skills || "All skills eligible"}</span>
                    </div>
                    <div>
                      <span className="text-slate-500 block">Min CGPA:</span>
                      <span className="font-semibold text-slate-800">{values.min_cgpa ? `${values.min_cgpa} / 10` : "No minimum"}</span>
                    </div>
                  </div>
                </div>

                {/* 4. Application Details Card */}
                <div className="p-4 rounded-xl border border-slate-200 bg-slate-50/50 space-y-2.5">
                  <div className="flex items-center justify-between border-b border-slate-200/80 pb-2">
                    <span className="text-xs font-bold text-slate-900 flex items-center gap-1.5">
                      <Icon name="mail" className="h-3.5 w-3.5 text-emerald-600" />
                      4. Application Method
                    </span>
                    <button
                      type="button"
                      onClick={() => goToStep(4)}
                      className="text-xs font-semibold text-emerald-700 hover:text-emerald-800 hover:underline"
                    >
                      Edit application
                    </button>
                  </div>
                  <div className="grid grid-cols-2 gap-2 text-xs">
                    <div>
                      <span className="text-slate-500 block">Application Method:</span>
                      <span className="font-semibold text-slate-800 capitalize">{values.application_type} application</span>
                    </div>
                    <div>
                      <span className="text-slate-500 block">Contact Email:</span>
                      <span className="font-semibold text-slate-800">{values.contact_email || "Not specified"}</span>
                    </div>
                  </div>
                </div>

                {/* 5. Pipeline Stages Card */}
                <div className="p-4 rounded-xl border border-slate-200 bg-slate-50/50 space-y-2.5">
                  <div className="flex items-center justify-between border-b border-slate-200/80 pb-2">
                    <span className="text-xs font-bold text-slate-900 flex items-center gap-1.5">
                      <Icon name="layers" className="h-3.5 w-3.5 text-emerald-600" />
                      5. Hiring Pipeline
                    </span>
                    <button
                      type="button"
                      onClick={() => goToStep(5)}
                      className="text-xs font-semibold text-emerald-700 hover:text-emerald-800 hover:underline"
                    >
                      Edit pipeline
                    </button>
                  </div>
                  <div className="grid grid-cols-2 gap-2 text-xs">
                    <div>
                      <span className="text-slate-500 block">Hiring Assessment:</span>
                      <span className="font-semibold text-slate-800">{values.assessment?.label || "None attached"}</span>
                    </div>
                    <div>
                      <span className="text-slate-500 block">HR Interview:</span>
                      <span className="font-semibold text-slate-800">{values.hr_interview ? "Enabled" : "Disabled"}</span>
                    </div>
                  </div>
                </div>
              </div>

              {/* Publishing Checklist */}
              <div className="p-4 rounded-xl border border-slate-200 bg-white space-y-3">
                <h5 className="text-xs font-bold text-slate-800 flex items-center gap-1.5">
                  <Icon name="clipboardCheck" className="h-4 w-4 text-emerald-600" />
                  Publishing Readiness Checklist
                </h5>
                <div className="space-y-2">
                  {checklist.map((item) => (
                    <div key={item.id} className="flex items-center justify-between text-xs py-1">
                      <div className="flex items-center gap-2">
                        {item.passed ? (
                          <Icon name="checkCircle" className="h-4 w-4 text-emerald-600 shrink-0" />
                        ) : (
                          <Icon name="alert" className="h-4 w-4 text-rose-500 shrink-0" />
                        )}
                        <span className={item.passed ? "text-slate-700 font-medium" : "text-rose-700 font-semibold"}>
                          {item.label}
                        </span>
                      </div>
                      {!item.passed && (
                        <button
                          type="button"
                          onClick={() => goToStep(item.step)}
                          className="text-xs text-emerald-600 font-bold hover:underline"
                        >
                          Fix in Step {item.step}
                        </button>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}
        </div>
      </main>

      {/* 3. Sticky Bottom Action Bar */}
      <footer className="sticky bottom-0 z-20 bg-white/95 backdrop-blur-md border-t border-slate-200 py-3 px-4 shadow-lg">
        <div className="max-w-[760px] mx-auto flex items-center justify-between gap-3">
          {/* Left: Outlined Back Button */}
          {currentStep === 1 ? (
            <Button
              type="button"
              variant="secondary"
              size="md"
              onClick={handleBackToJobs}
              className="text-xs font-semibold rounded-xl border-slate-300 gap-1.5 shadow-xs hover:bg-slate-50"
            >
              <Icon name="arrow-left" className="h-3.5 w-3.5" />
              Back to jobs
            </Button>
          ) : (
            <Button
              type="button"
              variant="secondary"
              size="md"
              onClick={() => goToStep(currentStep - 1)}
              className="text-xs font-semibold rounded-xl border-slate-300 gap-1.5 shadow-xs hover:bg-slate-50"
            >
              <Icon name="arrow-left" className="h-3.5 w-3.5" />
              Back
            </Button>
          )}

          {/* Center: Step Indicator */}
          <div className="text-xs text-slate-500 font-medium">
            Step <span className="font-bold text-slate-900">{currentStep}</span> of 6
          </div>

          {/* Right: Save & continue / Publish Button with Double-Click Protection */}
          <Button
            type="button"
            variant="primary"
            size="md"
            loading={publishing || isSaving}
            disabled={publishing || isSaving || (currentStep === 6 && !allChecklistPassed)}
            title={
              currentStep === 6 && !allChecklistPassed
                ? "Complete all required items in the publishing checklist to publish"
                : undefined
            }
            onClick={handleSaveAndContinue}
            className="text-xs font-bold rounded-xl bg-emerald-600 hover:bg-emerald-700 text-white gap-2 shadow-sm min-w-[155px]"
          >
            <span>{currentStep === 6 ? "Publish job opening" : "Save & continue"}</span>
            {currentStep < 6 && <Icon name="arrow-right" className="h-3.5 w-3.5" />}
          </Button>
        </div>
      </footer>
    </div>
  );
}

export function JobFormPage() {
  return (
    <JobFormErrorBoundary>
      <JobFormInner />
    </JobFormErrorBoundary>
  );
}
