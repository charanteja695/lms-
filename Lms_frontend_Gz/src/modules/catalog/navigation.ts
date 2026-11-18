import type { NavItem } from "@/app/navigation";

export const catalogNavigation: NavItem[] = [
  {
    menu: "courses",
    label: "Overview",
    icon: "grid",
    to: "/courses",
    group: "courses",
    hint: "Course catalog summary and analytics",
  },
  {
    menu: "courses",
    label: "Create Course",
    icon: "plus",
    to: "/courses/new",
    group: "courses",
    hint: "Draft a new course, syllabus, and pricing",
  },
  {
    menu: "courses",
    label: "All Courses",
    icon: "book",
    to: "/courses?view=all",
    group: "courses",
    hint: "View, search, and manage all courses",
  },
];
