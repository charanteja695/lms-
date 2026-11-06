import { useCan } from "@/modules/user-management/common/permissions/useCan";

/** Mirrors ai-interview-service: students practise and take screenings; employers own screening plans; careers managers own mock plans and see all. */
export function useInterviewRights() {
  const { can, holds, acts } = useCan();
  const isEmployer = holds("interviews.screen");
  return {
    isStudent: acts("ai_interview.view", "interviews.practice"),
    /** Start a new practice interview or a retake. */
    canStart: acts("ai_interview.create", "interviews.practice"),
    isEmployer,
    isCareersManager: can("careers.manage"),
    /** Which plans this person writes: a company's screening plans, or the platform's mock plans. */
    planKind: isEmployer ? ("screening" as const) : ("mock" as const),
  };
}

