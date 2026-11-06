import { useFormContext, useWatch } from "react-hook-form";

import { useListLanguagesQuery } from "@/modules/code-execution/languages/api/languagesApi";
import type { ProblemFormValues } from "@/modules/code-execution/problems/form/problemForm";
import { Checkbox, Field } from "@/shared/ui";

/** Which languages a student may submit in. Empty means every enabled language is allowed. */
export function AllowedLanguagesField() {
  const { control, setValue } = useFormContext<ProblemFormValues>();
  const selected = useWatch({ control, name: "allowed_languages" });
  const { data: languages } = useListLanguagesQuery();

  const toggle = (code: string) => {
    const next = selected.includes(code) ? selected.filter((item) => item !== code) : [...selected, code];
    setValue("allowed_languages", next, { shouldDirty: true });
  };

  return (
    <Field label="Allowed languages" hint="Leave all unchecked to allow every enabled language.">
      {() => (
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
          {(languages ?? []).map((language) => (
            <Checkbox key={language.code} label={`${language.name} ${language.version}`} checked={selected.includes(language.code)} onChange={() => toggle(language.code)} />
          ))}
        </div>
      )}
    </Field>
  );
}
