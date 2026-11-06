import type { ItemKind, SectionKey } from "@/modules/career/common/types";

export const KIND_LABELS: Record<ItemKind, string> = {
  education: "Education",
  experience: "Experience",
  project: "Projects",
  skill: "Skills",
  achievement: "Achievements",
  certificate: "Certificates",
  course: "Courses completed",
  skill_score: "Assessment scores",
};

/** Singular, for "Add …" buttons and dialog titles. */
export const KIND_SINGULAR: Record<ItemKind, string> = {
  education: "education",
  experience: "experience",
  project: "project",
  skill: "skill",
  achievement: "achievement",
  certificate: "certificate",
  course: "course",
  skill_score: "score",
};

export const SECTION_TITLES: Record<SectionKey, string> = {
  experience: "Experience",
  education: "Education",
  projects: "Projects",
  skills: "Skills",
  certificates: "Certifications",
  courses: "Courses completed",
  skill_scores: "Assessment scores",
  achievements: "Achievements",
};
