import type { SelfDeclaredKind } from "@/modules/career/common/types";

export type FieldType = "text" | "month" | "textarea" | "lines" | "list" | "checkbox";

export interface ItemField {
  key: string;
  label: string;
  type: FieldType;
  required?: boolean;
  maxLength?: number;
  hint?: string;
  placeholder?: string;
}

const BULLETS: ItemField = { key: "bullets", label: "Bullet points", type: "lines", hint: "One per line, up to 8, each under 300 characters." };
const START: ItemField = { key: "start_date", label: "Start", type: "month" };
const END: ItemField = { key: "end_date", label: "End", type: "month" };

/** The data each self-declared kind takes (career-service rejects unknown keys and validates the rest). */
export const ITEM_FIELDS: Record<SelfDeclaredKind, ItemField[]> = {
  education: [
    { key: "institution", label: "Institution", type: "text", required: true, maxLength: 160 },
    { key: "degree", label: "Degree", type: "text", required: true, maxLength: 120 },
    { key: "field_of_study", label: "Field of study", type: "text", maxLength: 120 },
    { key: "grade", label: "Grade", type: "text", maxLength: 40, hint: "e.g. 8.6 CGPA" },
    START, END, BULLETS,
  ],
  experience: [
    { key: "company", label: "Company", type: "text", required: true, maxLength: 160 },
    { key: "title", label: "Title", type: "text", required: true, maxLength: 120 },
    { key: "location", label: "Location", type: "text", maxLength: 120 },
    { key: "current", label: "I work here now", type: "checkbox" },
    START, END, BULLETS,
  ],
  project: [
    { key: "name", label: "Name", type: "text", required: true, maxLength: 160 },
    { key: "url", label: "Link", type: "text", maxLength: 300 },
    { key: "technologies", label: "Technologies", type: "list", hint: "Comma separated, up to 20." },
    { key: "description", label: "Description", type: "textarea", maxLength: 1000 },
    START, END, BULLETS,
  ],
  skill: [
    { key: "name", label: "Skill", type: "text", required: true, maxLength: 80, placeholder: "Enter skill name" },
  ],
  achievement: [
    { key: "title", label: "Title", type: "text", required: true, maxLength: 160 },
    { key: "date", label: "Date", type: "month" },
    { key: "description", label: "Description", type: "textarea", maxLength: 1000 },
  ],
};

export type ItemFormValues = Record<string, string | boolean>;

export function toFormValues(kind: SelfDeclaredKind, data: Record<string, unknown> = {}): ItemFormValues {
  return Object.fromEntries(
    ITEM_FIELDS[kind].map((field) => {
      const value = data[field.key];
      if (field.type === "checkbox") return [field.key, Boolean(value)];
      if (field.type === "lines") return [field.key, Array.isArray(value) ? value.join("\n") : ""];
      if (field.type === "list") return [field.key, Array.isArray(value) ? value.join(", ") : ""];
      return [field.key, typeof value === "string" ? value : ""];
    }),
  );
}

/** Form → API `data`; empty fields are left out rather than sent blank. */
export function toItemData(kind: SelfDeclaredKind, values: ItemFormValues): Record<string, unknown> {
  const data: Record<string, unknown> = {};
  for (const field of ITEM_FIELDS[kind]) {
    const value = values[field.key];
    if (field.type === "checkbox") {
      if (value) data[field.key] = true;
    } else if (field.type === "lines" || field.type === "list") {
      const parts = String(value ?? "").split(field.type === "lines" ? "\n" : ",").map((part) => part.trim()).filter(Boolean);
      if (parts.length) data[field.key] = parts;
    } else if (String(value ?? "").trim()) {
      data[field.key] = String(value).trim();
    }
  }
  return data;
}
