import type { BadgeTone } from "@/shared/ui";
import type { CaseSeverity, CaseStatus, SessionStatus } from "@/modules/proctoring/common/types";

export const SESSION_STATUS_LABELS: Record<SessionStatus, string> = {
  precheck: "Pre-check",
  ready: "Ready",
  active: "Active",
  submitted: "Submitted",
  closed: "Closed",
  superseded: "Superseded",
  abandoned: "Abandoned",
};

export const SESSION_STATUS_TONES: Record<SessionStatus, BadgeTone> = {
  precheck: "gray",
  ready: "blue",
  active: "green",
  submitted: "indigo",
  closed: "gray",
  superseded: "amber",
  abandoned: "red",
};

export const CASE_STATUS_LABELS: Record<CaseStatus, string> = {
  open: "Open",
  under_review: "Under review",
  decided: "Decided",
  appealed: "Appealed",
  final: "Final",
};

export const CASE_STATUS_TONES: Record<CaseStatus, BadgeTone> = {
  open: "red",
  under_review: "amber",
  decided: "blue",
  appealed: "purple",
  final: "green",
};

export const CASE_SEVERITY_LABELS: Record<CaseSeverity, string> = { low: "Low", medium: "Medium", high: "High" };

export const CASE_SEVERITY_TONES: Record<CaseSeverity, BadgeTone> = { low: "gray", medium: "amber", high: "red" };
