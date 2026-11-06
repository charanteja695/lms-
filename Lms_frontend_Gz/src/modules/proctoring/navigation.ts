import type { NavItem } from "@/app/navigation";

export const proctoringNavigation: NavItem[] = [
  { menu: "my_integrity_cases", label: "Exam reviews", icon: "shield", to: "/proctoring/my-cases", group: "exams", hint: "Reviews of your exams, and your appeals" },
  { menu: "proctoring", label: "Progress of Student", icon: "chart", to: "/proctoring/monitor", group: "curriculum", hint: "Student learning progress, course completion, and assessment scores" },
];
