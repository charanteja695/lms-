import { employersNavigation, userManagementNavigation } from "@/modules/user-management/navigation";
import type { MenuKey, Section } from "@/modules/user-management/common/permissions/types";
import type { ManagedRole } from "@/modules/user-management/common/types";
import { billingNavigation } from "@/modules/billing/navigation";
import { analyticsNavigation } from "@/modules/analytics/navigation";
import { aiInterviewNavigation } from "@/modules/ai-interview/navigation";
import { aiSettingsNavigation } from "@/modules/ai-settings/navigation";
import { aiTutorNavigation } from "@/modules/ai-tutor/navigation";
import { assessmentsNavigation } from "@/modules/assessments/navigation";
import { careerNavigation } from "@/modules/career/navigation";
import { catalogNavigation } from "@/modules/catalog/navigation";
import { mediaNavigation } from "@/modules/media/navigation";
import { storeNavigation } from "@/modules/store/navigation";
import { certificatesNavigation } from "@/modules/certificates/navigation";
import { codeExecutionNavigation } from "@/modules/code-execution/navigation";
import { jobPortalNavigation } from "@/modules/job-portal/navigation";
import { learningNavigation } from "@/modules/learning/navigation";
import { proctoringNavigation } from "@/modules/proctoring/navigation";
import { supportNavigation } from "@/modules/support/navigation";
import { subscriptionsNavigation } from "@/modules/subscriptions/navigation";
import type { IconName } from "@/shared/ui";

/** Sidebar headings, in display order. A heading shows only when this person has something under it. */
export const NAV_GROUPS = [
  { key: "home", label: null },
  { key: "users", label: "User Management" },
  { key: "learn", label: "Academic Learning" },
  { key: "exams", label: "Exams & Certifications" },
  { key: "curriculum", label: "Curriculum & Authoring" },
  { key: "academics", label: "Batches & Institutions" },
  { key: "careers", label: "Career & Placements" },
  { key: "admin", label: "System Administration" },
  { key: "help", label: "Support & Help" },
] as const;

export type NavGroup = (typeof NAV_GROUPS)[number]["key"];

/**
 * One sidebar entry. Who sees it is the server's decision: a `menu` entry (feature level, `permissions.menu`) or,
 * for user-management's own screens, a `section` (`permissions.sections`). This only gives it a label, icon, place and path.
 */
export type NavItem = {
  to: string;
  label: string;
  icon: IconName;
  group: NavGroup;
  /** One plain line: what this screen is for (shown on the home page). */
  hint: string;
  /** A people screen of one role: shown only when the server lets this person see that role (`users.view_roles`). */
  viewRole?: ManagedRole;
} & ({ menu: MenuKey; section?: never } | { section: Section; menu?: never });

/** Every entry, in display order within its group; each module contributes its own. */
export const NAVIGATION: NavItem[] = [
  { section: "dashboard", label: "Home", icon: "dashboard", to: "/", group: "home", hint: "Your starting point" },
  ...learningNavigation,
  ...catalogNavigation,
  ...mediaNavigation,
  ...storeNavigation,
  ...aiTutorNavigation,
  ...assessmentsNavigation,
  ...proctoringNavigation,
  ...codeExecutionNavigation,
  ...certificatesNavigation,
  ...employersNavigation,
  ...careerNavigation,
  ...jobPortalNavigation,
  ...aiInterviewNavigation,
  ...userManagementNavigation,
  ...subscriptionsNavigation,
  ...billingNavigation,
  ...analyticsNavigation,
  ...aiSettingsNavigation,
  ...supportNavigation,
];
