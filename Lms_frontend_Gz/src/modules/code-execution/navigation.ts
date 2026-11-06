import type { NavItem } from "@/app/navigation";

/** Review and Languages are narrower still and reached from the Problems page itself (see routes.tsx). */
export const codeExecutionNavigation: NavItem[] = [
  { menu: "problems", label: "Coding practice", icon: "terminal", to: "/problems", group: "curriculum", hint: "Solve coding and SQL problems to practise" },
  { menu: "compiler", label: "Compiler", icon: "play", to: "/compiler", group: "curriculum", hint: "Write and run code in your browser" },
  { menu: "my_submissions", label: "My submissions", icon: "upload", to: "/submissions", group: "learn", hint: "Your past code submissions and their results" },
];
