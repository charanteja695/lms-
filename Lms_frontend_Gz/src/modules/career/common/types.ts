/** Mirrors career-service's enums (see docs/API.md). */
export type ItemKind = "education" | "experience" | "project" | "skill" | "achievement" | "certificate" | "course" | "skill_score";

export type SelfDeclaredKind = "education" | "experience" | "project" | "skill" | "achievement";

export type SectionKey = "experience" | "education" | "projects" | "skills" | "certificates" | "courses" | "skill_scores" | "achievements";

export const SELF_DECLARED_KINDS: readonly SelfDeclaredKind[] = ["education", "experience", "project", "skill", "achievement"];

export const SECTION_KIND: Record<SectionKey, ItemKind> = {
  experience: "experience",
  education: "education",
  projects: "project",
  skills: "skill",
  certificates: "certificate",
  courses: "course",
  skill_scores: "skill_score",
  achievements: "achievement",
};

/** A rendered resume (career-service builds it from a draft or freezes it in a version). */
export interface ResumeDocument {
  personal: { name: string; email: string | null; headline: string | null; phone: string | null; location: string | null; links: { label: string; url: string }[] };
  summary: string | null;
  sections: {
    key: SectionKey;
    title: string;
    entries: { item_id: string; kind: ItemKind; verified: boolean; heading: string; subheading: string | null; dates: string | null; location: string | null; bullets: string[] }[];
  }[];
}
