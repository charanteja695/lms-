import type { NavItem } from "@/app/navigation";

export const subscriptionsNavigation: NavItem[] = [
  { menu: "course_requests", label: "Course requests", icon: "upload", to: "/course-requests", group: "academics", hint: "Ask for new courses for your institution" },
  { menu: "subscriptions", label: "Subscriptions & Seats", icon: "clock", to: "/subscriptions", group: "academics", hint: "Courses your institution has, with seats and dates" },
];
