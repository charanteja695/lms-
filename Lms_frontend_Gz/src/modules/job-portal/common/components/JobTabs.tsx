import { useJobRights } from "@/modules/job-portal/common/hooks/useJobRights";
import { SectionTabs, type SectionTab } from "@/shared/ui";

/**
 * Strict Role-Based Navigation Tabs for the Job Portal.
 * Renders role-specific views:
 * - Super Admin & Admin: Manage Jobs, Companies, Placement Drives, Job Approvals
 * - Employer: Jobs, Placement Drives, Company Profile
 * - Institution Head / Staff: Placements, Placement Drives
 * - Student: Find Jobs, My Applications
 */
export function JobTabs() {
  const r = useJobRights();

  let tabs: SectionTab[];

  if (r.isStudent) {
    tabs = [
      { to: "/jobs/board", label: "Find jobs", icon: "search" },
      { to: "/jobs/applications", label: "My applications", icon: "briefcase" },
    ];
  } else if (r.isSuperAdmin || r.isAdmin) {
    tabs = [
      { to: "/jobs/employer", label: "Manage Jobs", icon: "briefcase" },
      { to: "/employers", label: "Companies", icon: "building" },
      { to: "/jobs/drives", label: "Placement drives", icon: "users" },
      { to: "/jobs/admin", label: "Job Approvals", icon: "check" },
    ];
  } else if (r.isEmployer) {
    tabs = [
      { to: "/jobs/employer", label: "Jobs", icon: "briefcase" },
      { to: "/jobs/drives", label: "Placement drives", icon: "users" },
      { to: "/jobs/company", label: "Company profile", icon: "building" },
    ];
  } else if (r.isInstitution) {
    tabs = [
      { to: "/jobs/institution", label: "Placements", icon: "briefcase" },
      { to: "/jobs/drives", label: "Placement drives", icon: "users" },
    ];
  } else {
    tabs = [
      { to: "/jobs/board", label: "Find jobs", icon: "search" },
      { to: "/jobs/applications", label: "My applications", icon: "briefcase" },
    ];
  }

  return <SectionTabs tabs={tabs} />;
}
