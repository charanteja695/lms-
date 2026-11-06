import { useListAssessmentLanguagesQuery } from "@/modules/assessments/common/api/languagesApi";
import { CodeEditor, Select } from "@/shared/ui";

const SQL_DIALECTS = [
  { value: "sqlite", label: "SQLite" },
  { value: "postgresql", label: "PostgreSQL" },
];

export function CodeAnswer({ isSql, allowedLanguages, response, onChange, disabled }: {
  isSql: boolean;
  allowedLanguages?: string[];
  response: Record<string, unknown> | null;
  onChange: (response: Record<string, unknown>) => void;
  disabled: boolean;
}) {
  const { data: languages } = useListAssessmentLanguagesQuery(undefined, { skip: isSql });
  const options = isSql
    ? SQL_DIALECTS
    : (languages ?? []).filter((language) => !allowedLanguages?.length || allowedLanguages.includes(language.code)).map((language) => ({ value: language.code, label: `${language.name} ${language.version}` }));
  const language = (response?.language as string) ?? (isSql ? "sqlite" : (options[0]?.value ?? ""));
  const source = (response?.source as string) ?? "";

  return (
    <div className="space-y-3">
      <Select aria-label={isSql ? "Dialect" : "Language"} className="w-48" value={language} options={options} disabled={disabled} onChange={(event) => onChange({ language: event.target.value, source })} />
      <CodeEditor value={source} onChange={(value) => onChange({ language, source: value })} language={language} rows={16} disabled={disabled} />
    </div>
  );
}
