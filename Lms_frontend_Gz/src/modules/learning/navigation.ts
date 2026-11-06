import type { NavItem } from "@/app/navigation";

/** A student's own courses & certifications, or the batches staff run; the server's menu decides which. */
export const learningNavigation: NavItem[] = [
  { menu: "my_learning", label: "My courses", icon: "graduation", to: "/courses/my", group: "learn", hint: "Your enrolled courses, progress and certificates" },
  { menu: "batches", label: "Batches", icon: "layers", to: "/batches", group: "academics", hint: "Groups of students taking a course together" },
];
