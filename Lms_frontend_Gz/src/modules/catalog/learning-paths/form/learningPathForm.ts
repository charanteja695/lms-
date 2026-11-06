import { compact, diffForUpdate } from "@/core/lib/query";
import type { LearningPath, LearningPathCreateBody, LearningPathUpdateBody } from "@/modules/catalog/learning-paths/types";

/** Form state for creating/editing a learning path. Field names match the API body. */
export interface LearningPathFormValues {
  title: string;
  slug: string;
  description: string;
}

export function emptyLearningPathForm(): LearningPathFormValues {
  return { title: "", slug: "", description: "" };
}

export function learningPathToForm(path: LearningPath): LearningPathFormValues {
  return { title: path.title, slug: path.slug, description: path.description };
}

export function toLearningPathCreateBody(values: LearningPathFormValues): LearningPathCreateBody {
  return compact(values) as LearningPathCreateBody;
}

export function toLearningPathUpdateBody(initial: LearningPathFormValues, values: LearningPathFormValues): LearningPathUpdateBody {
  const shape = (v: LearningPathFormValues) => ({ title: v.title, description: v.description });
  return (diffForUpdate(shape(initial), shape(values)) ?? {}) as LearningPathUpdateBody;
}

export function isLearningPathField(field: string): boolean {
  return /^(title|slug|description)$/.test(field);
}
