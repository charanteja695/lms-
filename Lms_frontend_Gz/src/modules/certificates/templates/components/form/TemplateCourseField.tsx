import { get, useFormContext, useWatch } from "react-hook-form";

import { useCourseOptions } from "@/modules/catalog/common/hooks/useCourseOptions";
import type { TemplateFormValues } from "@/modules/certificates/templates/form/templateForm";
import { EntityPicker } from "@/shared/ui";

/** Empty = the platform default template. The course can't change after creation (PATCH has no course_id). */
export function TemplateCourseField({ disabled }: { disabled: boolean }) {
  const { control, setValue, formState } = useFormContext<TemplateFormValues>();
  const [id, label] = useWatch({ control, name: ["course_id", "course_label"] });
  return (
    <EntityPicker
      label="Course"
      value={id}
      selectedLabel={label}
      disabled={disabled}
      useOptions={useCourseOptions}
      placeholder="Platform default (all courses)"
      hint={disabled ? "Fixed once the template is created." : "Leave empty for the platform default, used by any course without its own active template."}
      error={get(formState.errors, "course_id")?.message}
      onChange={(value, text) => {
        setValue("course_id", value, { shouldDirty: true });
        setValue("course_label", text);
      }}
    />
  );
}
