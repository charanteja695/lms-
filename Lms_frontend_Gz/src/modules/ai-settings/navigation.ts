import type { NavItem } from "@/app/navigation";

export const aiSettingsNavigation: NavItem[] = [
  { menu: "ai_settings", label: "AI usage", icon: "sparkles", to: "/ai", group: "admin", hint: "AI usage and limits, models, prompts and the request log" },
];
