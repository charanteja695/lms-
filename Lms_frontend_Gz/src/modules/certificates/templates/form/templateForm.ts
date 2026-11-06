import type { CertificateTemplate, GradeBand, Signatory, TemplateCreateBody, TemplateUpdateBody } from "@/modules/certificates/templates/types";

/** Form state; field names match the API body except course_label (display only) and the string min_percent inputs. */
export interface TemplateFormValues {
  name: string;
  course_id: string;
  course_label: string;
  title_text: string;
  body_text: string;
  footer_text: string;
  accent_color: string;
  signatories: Signatory[];
  grade_bands: Array<{ min_percent: string; label: string }>;
}

export function emptyTemplateForm(): TemplateFormValues {
  return {
    name: "", course_id: "", course_label: "", title_text: "Certificate of Completion", body_text: "", footer_text: "", accent_color: "",
    signatories: [], grade_bands: [],
  };
}

export function templateToForm(template: CertificateTemplate, courseLabel: string): TemplateFormValues {
  return {
    name: template.name,
    course_id: template.course_id ?? "",
    course_label: courseLabel,
    title_text: template.title_text,
    body_text: template.body_text,
    footer_text: template.footer_text ?? "",
    accent_color: template.accent_color,
    signatories: template.signatories,
    grade_bands: template.grade_bands.map((band) => ({ min_percent: String(band.min_percent), label: band.label })),
  };
}

function bands(values: TemplateFormValues): GradeBand[] {
  return values.grade_bands.map((band) => ({ min_percent: Number(band.min_percent), label: band.label }));
}

/** No grade bands entered means "use the service's default bands" (Distinction ≥ 85, Merit ≥ 70, Pass). */
export function toTemplateCreateBody(values: TemplateFormValues): TemplateCreateBody {
  return {
    name: values.name,
    course_id: values.course_id || null,
    title_text: values.title_text,
    body_text: values.body_text || null,
    footer_text: values.footer_text || null,
    accent_color: values.accent_color || null,  // empty: the platform colour (the brand green)
    signatories: values.signatories,
    grade_bands: values.grade_bands.length ? bands(values) : null,
  };
}

export function toTemplateUpdateBody(values: TemplateFormValues): TemplateUpdateBody {
  const body = toTemplateCreateBody(values);
  return {
    name: body.name, title_text: body.title_text, body_text: body.body_text, footer_text: body.footer_text,
    accent_color: body.accent_color, signatories: body.signatories, grade_bands: body.grade_bands,
  };
}

export function isTemplateField(field: string): boolean {
  return /^(name|course_id|title_text|body_text|footer_text|accent_color|signatories|grade_bands)/.test(field);
}
