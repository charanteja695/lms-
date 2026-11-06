import type { IconName } from "@/shared/ui";
import type { DashboardKey } from "@/modules/analytics/common/types";

export type MetricFormat = "count" | "percent" | "score" | "rupees" | "inr" | "usd";

export interface Metric {
  key: string;
  label: string;
  format?: MetricFormat;
  icon: IconName;
}

export interface DashboardSpec {
  key: DashboardKey;
  label: string;
  /** The API path under /dashboards. */
  path: string;
  description: string;
  metrics: Metric[];
  /** name -> count maps shown as bars. */
  breakdowns: { key: string; label: string }[];
}

/** How each dashboard's totals are laid out. The numbers, and who may see them, come from the server. */
export const DASHBOARDS: DashboardSpec[] = [
  {
    key: "institution", label: "Institution", path: "institution", description: "Enrolments through to placements for one institution.",
    metrics: [
      { key: "enrollments", label: "Enrolments", icon: "users" },
      { key: "topic_completions", label: "Topics completed", icon: "check" },
      { key: "module_completions", label: "Modules completed", icon: "layers" },
      { key: "eligible_for_final", label: "Eligible for final", icon: "graduation" },
      { key: "tests_finalized", label: "Tests finalised", icon: "fileText" },
      { key: "test_pass_rate", label: "Pass rate", format: "percent", icon: "check" },
      { key: "certificates_issued", label: "Certificates issued", icon: "archive" },
      { key: "students_placed", label: "Students placed", icon: "briefcase" },
    ],
    breakdowns: [],
  },
  {
    key: "content", label: "Learning", path: "content", description: "The platform-wide learning funnel.",
    metrics: [
      { key: "enrollments", label: "Enrolments", icon: "users" },
      { key: "topic_completions", label: "Topics completed", icon: "check" },
      { key: "module_completions", label: "Modules completed", icon: "layers" },
      { key: "eligible_for_final", label: "Eligible for final", icon: "graduation" },
      { key: "courses_passed", label: "Courses passed", icon: "check" },
      { key: "courses_failed", label: "Courses failed", icon: "x" },
      { key: "course_pass_rate", label: "Course pass rate", format: "percent", icon: "check" },
      { key: "average_pass_percent", label: "Average pass mark", format: "score", icon: "fileText" },
    ],
    breakdowns: [],
  },
  {
    key: "exam_integrity", label: "Exam integrity", path: "exam-integrity", description: "Attempts, proctoring flags and integrity decisions.",
    metrics: [
      { key: "attempts_finalized", label: "Attempts finalised", icon: "fileText" },
      { key: "average_percent", label: "Average score", format: "score", icon: "check" },
      { key: "integrity_flags", label: "Integrity flags", icon: "alert" },
      { key: "integrity_decisions", label: "Decisions", icon: "shield" },
    ],
    breakdowns: [{ key: "results", label: "Results" }, { key: "flags_by_stage", label: "Flags by stage" }, { key: "decisions_by_outcome", label: "Decisions by outcome" }],
  },
  {
    key: "support", label: "Support", path: "support", description: "Ticket volume, SLA breaches and satisfaction.",
    metrics: [
      { key: "tickets_created", label: "Tickets created", icon: "mail" },
      { key: "status_changes", label: "Status changes", icon: "refresh" },
      { key: "sla_breaches", label: "SLA breaches", icon: "alert" },
      { key: "average_csat", label: "Average CSAT", format: "score", icon: "check" },
    ],
    breakdowns: [{ key: "by_category", label: "Tickets by category" }, { key: "by_status", label: "Changes by status" }, { key: "breaches_by_kind", label: "Breaches by kind" }],
  },
  {
    key: "hiring", label: "Hiring", path: "hiring", description: "Applications, offers, placements and AI interviews.",
    metrics: [
      { key: "placements", label: "Placements", icon: "briefcase" },
      { key: "average_placement_ctc", label: "Average CTC", format: "rupees", icon: "briefcase" },
      { key: "offers_extended", label: "Offers extended", icon: "mail" },
      { key: "offers_accepted", label: "Offers accepted", icon: "check" },
      { key: "offers_declined", label: "Offers declined", icon: "x" },
      { key: "interviews_completed", label: "AI interviews", icon: "video" },
    ],
    breakdowns: [{ key: "applications_by_stage", label: "Applications by stage" }, { key: "ai_recommendations", label: "AI recommendations" }, { key: "human_overrides", label: "Human overrides" }],
  },
  {
    key: "ai_usage", label: "AI usage", path: "ai-usage", description: "AI calls, tokens and cost.",
    metrics: [
      { key: "calls", label: "Calls", icon: "terminal" },
      { key: "total_tokens", label: "Tokens", icon: "layers" },
      { key: "total_cost_cents", label: "Cost", format: "usd", icon: "clock" },
    ],
    breakdowns: [{ key: "by_capability", label: "Calls by capability" }],
  },
  {
    key: "billing", label: "Billing", path: "billing", description: "Invoiced against collected revenue.",
    metrics: [
      { key: "invoiced_amount", label: "Invoiced", format: "inr", icon: "fileText" },
      { key: "paid_amount", label: "Collected", format: "inr", icon: "check" },
      { key: "overdue_amount", label: "Overdue", format: "inr", icon: "alert" },
      { key: "credit_amount", label: "Credit notes", format: "inr", icon: "refresh" },
      { key: "invoices_issued", label: "Invoices issued", icon: "fileText" },
      { key: "invoices_paid", label: "Invoices paid", icon: "check" },
      { key: "plans_activated", label: "Plans activated", icon: "play" },
      { key: "plans_expired", label: "Plans expired", icon: "clock" },
    ],
    breakdowns: [],
  },
];

export const DASHBOARD_BY_KEY = Object.fromEntries(DASHBOARDS.map((d) => [d.key, d])) as Record<DashboardKey, DashboardSpec>;

/** Trailing-day windows offered (the API accepts 1–90). */
export const DAY_OPTIONS = [7, 30, 90].map((d) => ({ value: String(d), label: `Last ${d} days` }));
