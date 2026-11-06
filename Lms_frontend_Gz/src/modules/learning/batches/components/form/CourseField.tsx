import { get, useFormContext, useWatch } from "react-hook-form";

import { usePublishedCourseOptions } from "@/modules/learning/batches/hooks/usePublishedCourseOptions";
import type { BatchFormValues } from "@/modules/learning/batches/form/batchForm";
import { EntityPicker } from "@/shared/ui";

export function CourseField() {
  const { control, setValue, formState } = useFormContext<BatchFormValues>();
  const [id, label] = useWatch({ control, name: ["course_id", "course_label"] });
  return (
    <EntityPicker
      label="Course"
      required
      clearable={false}
      value={id}
      selectedLabel={label}
      useOptions={usePublishedCourseOptions}
      hint="Only published courses can start a batch."
      error={get(formState.errors, "course_id")?.message}
      onChange={(value, text) => {
        setValue("course_id", value, { shouldDirty: true, shouldValidate: true });
        setValue("course_label", text);
      }}
    />
  );
}
