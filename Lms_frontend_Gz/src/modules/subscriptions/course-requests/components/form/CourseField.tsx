import { get, useFormContext, useWatch } from "react-hook-form";

import { usePublishedCourseOptions } from "@/modules/subscriptions/course-requests/hooks/usePublishedCourseOptions";
import type { CourseRequestFormValues } from "@/modules/subscriptions/course-requests/form/courseRequestForm";
import { EntityPicker } from "@/shared/ui";

export function CourseField() {
  const { control, setValue, formState } = useFormContext<CourseRequestFormValues>();
  const [id, label] = useWatch({ control, name: ["course_id", "course_label"] });
  return (
    <EntityPicker
      label="Course"
      required
      clearable={false}
      value={id}
      selectedLabel={label}
      useOptions={usePublishedCourseOptions}
      hint="Only published courses can be requested."
      error={get(formState.errors, "course_id")?.message}
      onChange={(value, text) => {
        setValue("course_id", value, { shouldDirty: true, shouldValidate: true });
        setValue("course_label", text);
      }}
    />
  );
}
