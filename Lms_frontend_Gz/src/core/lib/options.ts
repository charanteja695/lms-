import type { Option } from "@/shared/ui";

export function toOptions<T extends string>(labels: Record<T, string>, only?: readonly T[]): Option<T>[] {
  const keys = (only ?? (Object.keys(labels) as T[])) as T[];
  return keys.map((value) => ({ value, label: labels[value] }));
}
