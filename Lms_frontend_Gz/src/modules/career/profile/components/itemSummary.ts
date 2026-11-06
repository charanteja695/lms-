import type { ProfileItem } from "@/modules/career/profile/types";

const str = (value: unknown) => (typeof value === "string" && value ? value : null);

/** One-line heading and detail for a profile item — the same words career-service puts on a resume. */
export function itemSummary(item: ProfileItem): { heading: string; detail: string | null } {
  const { data, derived } = item;
  const dates = [str(data.start_date), str(data.end_date) ?? (data.current ? "Present" : null)].filter(Boolean).join(" – ") || null;
  switch (item.kind) {
    case "education":
      return { heading: [str(data.degree), str(data.field_of_study)].filter(Boolean).join(", "), detail: [str(data.institution), dates].filter(Boolean).join(" · ") };
    case "experience":
      return { heading: str(data.title) ?? "", detail: [str(data.company), str(data.location), dates].filter(Boolean).join(" · ") };
    case "project":
      return { heading: str(data.name) ?? "", detail: [Array.isArray(data.technologies) ? data.technologies.join(", ") : null, dates].filter(Boolean).join(" · ") || null };
    case "skill":
      return { heading: str(data.name) ?? "", detail: str(data.category) };
    case "achievement":
      return { heading: str(data.title) ?? "", detail: str(data.date) };
    case "certificate":
      return { heading: `${derived.course_title ?? "Course"} — Certificate`, detail: [str(data.grade) && `Grade ${String(data.grade)}`, typeof data.score_percent === "number" && `${data.score_percent}%`].filter(Boolean).join(" · ") || null };
    case "course":
      return { heading: derived.course_title ?? "Course", detail: str(data.completed_at)?.slice(0, 10) ?? null };
    case "skill_score": {
      const percentile = derived.percentile != null ? ` · top ${100 - derived.percentile}% of ${derived.cohort_size}` : "";
      return { heading: derived.course_title ?? "Course", detail: typeof data.best_percent === "number" ? `Best score ${data.best_percent}%${percentile}` : null };
    }
  }
}
