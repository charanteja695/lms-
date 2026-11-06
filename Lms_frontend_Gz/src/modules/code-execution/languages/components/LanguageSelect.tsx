import { useListLanguagesQuery } from "@/modules/code-execution/languages/api/languagesApi";
import { Select } from "@/shared/ui";

/** Every enabled language, for the editor's language switcher. Restrict `allowed` for a specific problem. */
export function LanguageSelect({ value, onChange, allowed, disabled }: { value: string; onChange: (code: string) => void; allowed?: string[]; disabled?: boolean }) {
  const { data: languages, isFetching } = useListLanguagesQuery();
  const options = (languages ?? [])
    .filter((language) => !allowed || allowed.includes(language.code))
    .map((language) => ({ value: language.code, label: `${language.name} ${language.version}` }));

  return (
    <Select
      aria-label="Language"
      className="w-48"
      value={value}
      disabled={disabled || isFetching}
      options={options}
      onChange={(event) => onChange(event.target.value)}
    />
  );
}
