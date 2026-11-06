import type { ApplicationStatus } from "@/modules/job-portal/common/types";

/** job-portal's TERMINAL_STATUSES: nothing moves an application on from these. */
export const TERMINAL_STATUSES: ReadonlySet<ApplicationStatus> = new Set(["rejected", "offer_declined", "placed", "withdrawn"]);
