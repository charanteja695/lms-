import { FormProvider, useForm } from "react-hook-form";

import { useNotify } from "@/core/hooks/useNotify";
import { applyServerErrors, toApiError } from "@/core/lib/apiError";
import { KIND_SINGULAR } from "@/modules/career/common/labels";
import type { SelfDeclaredKind } from "@/modules/career/common/types";
import { useAddProfileItemMutation, useUpdateProfileItemMutation } from "@/modules/career/profile/api/profileApi";
import { ITEM_FIELDS, toFormValues, toItemData, type ItemFormValues } from "@/modules/career/profile/form/itemFields";
import type { ProfileItem } from "@/modules/career/profile/types";
import { CheckboxField, TextareaField, TextField } from "@/shared/form";
import { Button, Modal } from "@/shared/ui";

/** Add or edit a self-declared item. Server field errors arrive as `data.<field>` and are shown on that field. */
export function ItemDialog({
  kind,
  item,
  existingItems,
  onClose,
}: {
  kind: SelfDeclaredKind;
  item?: ProfileItem;
  existingItems?: ProfileItem[];
  onClose: () => void;
}) {
  const notify = useNotify();
  const form = useForm<ItemFormValues>({ defaultValues: toFormValues(kind, item?.data) });
  const [add, { isLoading: adding }] = useAddProfileItemMutation();
  const [update, { isLoading: updating }] = useUpdateProfileItemMutation();

  const titlePrefix = item ? "Edit" : "Add";
  const titleLabel = kind === "skill" ? "Skill" : KIND_SINGULAR[kind];

  const submit = form.handleSubmit(async (values) => {
    try {
      if (kind === "skill") {
        const skillName = String(values.name ?? "").trim();
        if (!skillName) {
          form.setError("name", { message: "Skill is required" });
          return;
        }

        // Prevent duplicate skills
        const isDuplicate = existingItems?.some(
          (existing) =>
            existing.item_id !== item?.item_id &&
            existing.kind === "skill" &&
            typeof existing.data?.name === "string" &&
            existing.data.name.trim().toLowerCase() === skillName.toLowerCase()
        );
        if (isDuplicate) {
          form.setError("name", { message: `"${skillName}" has already been added.` });
          return;
        }
      }

      const rawData = toItemData(kind, values);
      // Preserve existing category if an already-saved skill had one
      const data = {
        ...(kind === "skill" && item?.data?.category ? { category: item.data.category } : {}),
        ...rawData,
      };

      if (item) await update({ itemId: item.item_id, data }).unwrap();
      else await add({ kind, data }).unwrap();
      notify.success(item ? "Saved" : "Added to your profile");
      onClose();
    } catch (error) {
      const apiError = toApiError(error);
      // "data.bullets.2" → the "bullets" field (one textarea holds every bullet)
      const named = { ...apiError, details: apiError.details.map((detail) => ({ ...detail, field: detail.field?.replace(/^data\./, "").split(".")[0] ?? null })) };
      const unmatched = applyServerErrors(named, form.setError, (field) => ITEM_FIELDS[kind].some((f) => f.key === field));
      if (!apiError.details.length || unmatched.length) notify.apiError(error);
    }
  });

  return (
    <Modal
      open
      onClose={onClose}
      title={`${titlePrefix} ${titleLabel}`}
      size={kind === "skill" ? "md" : "lg"}
      footer={
        <>
          <Button variant="secondary" onClick={onClose} disabled={adding || updating}>
            Cancel
          </Button>
          <Button type="submit" form="career-item-form" loading={adding || updating}>
            Save
          </Button>
        </>
      }
    >
      <FormProvider {...form}>
        <form
          id="career-item-form"
          noValidate
          className={kind === "skill" ? "flex flex-col gap-4 w-full" : "grid gap-4 sm:grid-cols-2"}
          onSubmit={submit}
        >
          {ITEM_FIELDS[kind].map((field) => {
            const wide = field.type === "textarea" || field.type === "lines" || field.type === "list" || field.type === "checkbox" || kind === "skill";
            const className = wide ? "sm:col-span-2 w-full" : undefined;
            if (field.type === "checkbox") return <CheckboxField<ItemFormValues> key={field.key} name={field.key} label={field.label} className={className} />;
            if (field.type === "textarea" || field.type === "lines") {
              return <TextareaField<ItemFormValues> key={field.key} name={field.key} label={field.label} hint={field.hint} rows={field.type === "lines" ? 5 : 3} maxLength={field.type === "lines" ? 2600 : field.maxLength} className={className} />;
            }
            return (
              <TextField<ItemFormValues>
                key={field.key}
                name={field.key}
                label={field.label}
                hint={field.hint}
                required={field.required}
                maxLength={field.maxLength}
                placeholder={field.placeholder}
                rules={field.required ? { required: `${field.label} is required` } : undefined}
                type={field.type === "month" ? "month" : "text"}
                className={className}
              />
            );
          })}
        </form>
      </FormProvider>
    </Modal>
  );
}
