import { NAVIGATION, type NavItem } from "@/app/navigation";
import { useAuth } from "@/modules/user-management/auth/hooks/useAuth";
import { usePermissions } from "@/modules/user-management/common/permissions/usePermissions";
import { useStudentType } from "@/modules/user-management/auth/hooks/useStudentType";

const RESTRICTED_INDIVIDUAL_MENUS = new Set([
  "my_subscription",
  "my_payment_requests",
  "payment_history",
]);

/** The navigation entries the server lets this person open (feature-level `menu`, user-management's `sections`, or the roles it may see). */
export function useNavItems(): NavItem[] {
  const { role: authRole } = useAuth();
  const { can, canOpen, permissions } = usePermissions();
  const { isResolving, isStudent, isInstitutionStudent } = useStudentType();
  const isAdmin = authRole === "super_admin" || authRole === "admin" || permissions.role === "super_admin" || permissions.role === "admin";

  if (isAdmin) {
    return [
      { section: "dashboard", label: "Dashboard", icon: "dashboard", to: "/", group: "home", hint: "Overview and core analytics" },
      // Course Management - Simplified to exactly 3 items as specified
      { menu: "courses", label: "Overview", icon: "grid", to: "/courses", group: "courses", hint: "Course catalog summary and analytics" },
      { menu: "courses", label: "Create Course", icon: "plus", to: "/courses/new", group: "courses", hint: "Draft a new course, syllabus, and pricing" },
      { menu: "courses", label: "All Courses", icon: "book", to: "/courses?view=all", group: "courses", hint: "View, search, and manage all courses" },
      // Batches & Institutions
      { section: "academics", label: "Batches", icon: "users", to: "/academics/batches", group: "academics", hint: "Cohort batches, student allotments, and schedules" },
      { section: "academics", label: "Academic Structure", icon: "book", to: "/academics", group: "academics", hint: "Departments, programs, and student sections" },
      { section: "academics", label: "Marks & Results", icon: "chart", to: "/results", group: "academics", hint: "Student scores, test performance, and pass rates" },
      { menu: "course_requests", label: "Course Requests", icon: "fileText", to: "/institution/course-management", group: "academics", hint: "Institutional purchase requests and course allocations" },
      { menu: "billing", label: "Subscriptions & Seats", icon: "creditCard", to: "/subscriptions", group: "academics", hint: "Institutional seat allocation, tiers, and licenses" },
      // Career & Placements
      { section: "employers", label: "Hiring Companies", icon: "briefcase", to: "/employers", group: "careers", hint: "Employer partnerships and campus recruiting companies" },
      { menu: "career", label: "Job Management", icon: "monitor", to: "/career", group: "careers", hint: "Job postings, placement drives, and career tracks" },
      { menu: "career", label: "Applications", icon: "fileSpreadsheet", to: "/career", group: "careers", hint: "Student placement applications and interview status" },
      { menu: "ai_interviews", label: "AI Interviewer", icon: "video", to: "/interviews", group: "careers", hint: "AI-powered mock interviews, evaluations, and transcripts" },
      // System Administration
      { section: "admins", label: "User Management", icon: "users", to: "/admins", group: "admin", hint: "Manage administrators, institution heads, staff, and students" },
      { section: "permissions", label: "Role & Permissions", icon: "key", to: "/permissions", group: "admin", hint: "Granular access control, security roles, and permissions" },
      { section: "analytics", label: "Reports", icon: "chart", to: "/analytics", group: "admin", hint: "System-wide analytics, revenue reports, and metrics" },
      { section: "security", label: "Settings", icon: "lock", to: "/account/security", group: "admin", hint: "Platform security, password rules, and system configurations" },
    ];
  }

  return NAVIGATION.filter((i) => {
    // 1. While auth/permissions profile is resolving, prevent flashing restricted individual payment menus
    if (isStudent && isResolving && i.menu && RESTRICTED_INDIVIDUAL_MENUS.has(i.menu)) {
      return false;
    }

    // 2. Institution students must NOT see My Subscription, My Payment Requests, or Payment History
    if (isInstitutionStudent && i.menu && RESTRICTED_INDIVIDUAL_MENUS.has(i.menu)) {
      return false;
    }

    if (i.viewRole) return permissions.users.view_roles.includes(i.viewRole);
    return i.menu ? canOpen(i.menu) : can(i.section);
  }).map((item) => {
    if (permissions.role === "student" && item.menu === "certificates") {
      return { ...item, label: "My Certificates" };
    }
    return item;
  });
}
