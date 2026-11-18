import type { NavItem } from "@/app/navigation";

export const billingNavigation: NavItem[] = [
  { menu: "billing", label: "Billing & Plans", icon: "fileText", to: "/billing", group: "admin", hint: "Invoices, quotes, payments and plans" },
  { menu: "course_requests", label: "Institutional Course Management", icon: "building", to: "/institution/course-management", group: "academics", hint: "Course requests, purchases, subscriptions, and bulk calculator" },
];
